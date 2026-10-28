"""Opt-in MariaDB integration tests. Run only against a disposable schema imported from the reviewed legacy dump.

These tests are intentionally not auto-discovered by the fast no-database suite.
Set STOKIT_RUN_MARIADB_INTEGRATION=1 and invoke `manage.py test accounts.mariadb_integration`.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from accounts.hashers import hash_password
from accounts.models import UserDeviceSession
from accounts.services import create_session, authenticate_token, revoke_session, SessionLimitReached, hash_token
from legacydb.models import LegacyUser

RUN = os.environ.get('STOKIT_RUN_MARIADB_INTEGRATION') == '1'

@override_settings(MAX_ACTIVE_SESSIONS=3)
class MariaDBSessionLimitTests(TransactionTestCase):
    databases = {'default'}

    def setUp(self):
        if not RUN:
            self.skipTest('Set STOKIT_RUN_MARIADB_INTEGRATION=1 after provisioning a disposable MariaDB schema.')
        self.user = LegacyUser.objects.create(username='session-test-user', password=hash_password('Test-password-123'),
            email='session-test@example.invalid', fullname='Session Integration', token='', latitude='', longitude='')

    def tearDown(self):
        if RUN and hasattr(self, 'user'):
            UserDeviceSession.objects.filter(user_id=self.user.pk).delete()
            LegacyUser.objects.filter(pk=self.user.pk).delete()

    def test_first_three_sessions_allowed_fourth_rejected_without_revoking_existing(self):
        tokens = [create_session(self.user.pk) for _ in range(3)]
        with self.assertRaises(SessionLimitReached):
            create_session(self.user.pk)
        for token in tokens:
            self.assertIsNotNone(authenticate_token(token))
        self.assertEqual(UserDeviceSession.objects.active().filter(user_id=self.user.pk).count(), 3)

    def test_revocation_and_expiry_only_invalidate_target_session(self):
        first = create_session(self.user.pk); second = create_session(self.user.pk)
        first_session = UserDeviceSession.objects.get(token_hash=hash_token(first))
        revoke_session(first_session.pk)
        self.assertIsNone(authenticate_token(first))
        self.assertIsNotNone(authenticate_token(second))
        second_session = UserDeviceSession.objects.get(token_hash=hash_token(second))
        UserDeviceSession.objects.filter(pk=second_session.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertIsNone(authenticate_token(second))

    def test_concurrent_login_attempts_never_create_more_than_three_sessions(self):
        def attempt(_):
            close_old_connections()
            try:
                return create_session(self.user.pk)
            except SessionLimitReached:
                return None
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(attempt, range(8)))
        accepted=[token for token in results if token]
        self.assertEqual(len(accepted), 3)
        self.assertEqual(UserDeviceSession.objects.active().filter(user_id=self.user.pk).count(), 3)
