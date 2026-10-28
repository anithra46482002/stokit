"""Opt-in DB/API integration tests; run only against a disposable MariaDB schema containing legacy tables.
Set STOKIT_RUN_MARIADB_INTEGRATION=1 and invoke `manage.py test legacy_api.mariadb_integration`.
"""
import os
import re
from datetime import timedelta
from django.core import mail
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from accounts.hashers import hash_password, verify_php_password
from accounts.models import PasswordResetOTP, UserDeviceSession
from legacydb.models import LegacyUser

RUN = os.environ.get('STOKIT_RUN_MARIADB_INTEGRATION') == '1'

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PASSWORD_RESET_OTP_TTL_SECONDS=600, PASSWORD_RESET_OTP_MAX_ATTEMPTS=5)
class MariaDBPasswordResetTests(TransactionTestCase):
    databases = {'default'}

    def setUp(self):
        if not RUN:
            self.skipTest('Set STOKIT_RUN_MARIADB_INTEGRATION=1 after provisioning a disposable MariaDB schema.')
        mail.outbox = []
        self.user = LegacyUser.objects.create(username='reset-test-user', password=hash_password('Old-password-123'),
            email='reset-test@example.invalid', fullname='Reset Integration', token='', latitude='', longitude='')
        self.client.defaults['HTTP_HOST'] = 'localhost'

    def tearDown(self):
        if RUN and hasattr(self, 'user'):
            PasswordResetOTP.objects.filter(user_id=self.user.pk).delete()
            UserDeviceSession.objects.filter(user_id=self.user.pk).delete()
            LegacyUser.objects.filter(pk=self.user.pk).delete()

    def request_code(self):
        response = self.client.post('/api/acc/', data={'email': self.user.email}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        match = re.search(r'\b(\d{6})\b', mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_unknown_account_generic_response_and_request_rate_limit(self):
        unknown = self.client.post('/api/acc/', data={'email': 'unknown@example.invalid'}, content_type='application/json')
        self.assertEqual(unknown.json(), {'success': True, 'message': 'If the account is eligible, reset instructions will be sent.'})
        for _ in range(3): self.request_code()
        before = len(mail.outbox)
        fourth = self.client.post('/api/acc/', data={'email': self.user.email}, content_type='application/json')
        self.assertEqual(fourth.json(), unknown.json())
        self.assertEqual(len(mail.outbox), before)

    def test_expired_otp_is_rejected(self):
        code = self.request_code()
        PasswordResetOTP.objects.filter(user_id=self.user.pk, consumed_at__isnull=True).update(expires_at=timezone.now()-timedelta(seconds=1))
        response = self.client.post('/api/acc/reset', data={'email':self.user.email,'otp':code,'new_password':'New-password-123'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_attempt_limit_consumes_otp(self):
        code = self.request_code()
        wrong = '000000' if code != '000000' else '000001'
        for _ in range(5):
            response = self.client.post('/api/acc/reset', data={'email':self.user.email,'otp':wrong,'new_password':'New-password-123'}, content_type='application/json')
            self.assertEqual(response.status_code, 400)
        record = PasswordResetOTP.objects.filter(user_id=self.user.pk).latest('created_at')
        self.assertEqual(record.attempts, 5)
        self.assertIsNotNone(record.consumed_at)

    def test_successful_reset_updates_hash_and_otp_cannot_be_reused(self):
        code = self.request_code()
        response = self.client.post('/api/acc/reset', data={'email':self.user.email,'otp':code,'new_password':'New-password-123'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.user.refresh_from_db()
        self.assertTrue(verify_php_password('New-password-123', self.user.password))
        reused = self.client.post('/api/acc/reset', data={'email':self.user.email,'otp':code,'new_password':'Another-password-123'}, content_type='application/json')
        self.assertEqual(reused.status_code, 400)
        login = self.client.post('/api/login', data={'username':self.user.username,'password':'New-password-123'}, content_type='application/json')
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()['success'])

import json
from accounts.services import create_session
from accounts.models import CheckoutPayload

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class FlutterRemainingEndpointTests(TransactionTestCase):
    databases = {'default'}

    def setUp(self):
        if not RUN:
            self.skipTest('Set STOKIT_RUN_MARIADB_INTEGRATION=1 after provisioning a disposable MariaDB schema.')
        self.user = LegacyUser.objects.create(username='legacy-api-test-user', password=hash_password('Test-password-123'),
            email='legacy-api-test@example.invalid', fullname='Legacy API Integration', token='', latitude='', longitude='')
        self.token = create_session(self.user.pk)

    def tearDown(self):
        if RUN and hasattr(self, 'user'):
            CheckoutPayload.objects.filter(user_id=self.user.pk).delete()
            UserDeviceSession.objects.filter(user_id=self.user.pk).delete()
            LegacyUser.objects.filter(pk=self.user.pk).delete()

    def test_save_check_stores_real_payload_and_preserves_legacy_response_keys(self):
        payload = {'cart': [{'product_id': 17, 'quantity': 2}], 'notes': 'test'}
        response = self.client.post('/api/saveCheck', data=json.dumps(payload), content_type='application/json', HTTP_AUTHORIZATION='Bearer '+self.token)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {'success', 'message', 'file', 'oder_id'})
        self.assertTrue(body['success'])
        saved = CheckoutPayload.objects.get(user_id=self.user.pk, legacy_order_id=body['oder_id'])
        self.assertEqual(saved.payload, payload)
        self.assertTrue(body['file'].startswith('ck/checkout_'))

    def test_save_check_rejects_empty_json_payload(self):
        response = self.client.post('/api/saveCheck', data='{}', content_type='application/json', HTTP_AUTHORIZATION='Bearer '+self.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': False, 'message': 'Invalid JSON'})

    def test_coabout_keeps_source_link_contract(self):
        response = self.client.get('/api/coabout', HTTP_AUTHORIZATION='Bearer '+self.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True, 'links': {'terms_and_conditions':'https://www.example.com','about_us':'https://www.example.com/about'}})

    def test_targets_returns_user_scoped_real_assignments_without_sample_data(self):
        response = self.client.get('/api/targets', HTTP_AUTHORIZATION='Bearer '+self.token)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['user_info']['username'], self.user.username)
        self.assertEqual(body['targets'], [])
