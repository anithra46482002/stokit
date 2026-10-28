"""Database-free regression tests for the Flutter-compatible password reset request."""
import json
from contextlib import nullcontext
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, SimpleTestCase

from legacy_api import views_reset


class RequestResetTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.post(
            "/api/acc/",
            data=json.dumps({"email": "reset-user@example.invalid"}),
            content_type="application/json",
        )

    def test_unknown_identity_returns_generic_response_without_creating_otp(self):
        manager = mock.Mock()
        manager.filter.return_value.first.side_effect = [None, None]
        with mock.patch.object(views_reset.LegacyUser, "objects", manager), \
                mock.patch.object(views_reset.PasswordResetOTP, "objects") as otp_manager, \
                mock.patch.object(views_reset, "send_mail") as send_mail:
            response = views_reset.request_reset(self.request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), views_reset.GENERIC)
        otp_manager.create.assert_not_called()
        send_mail.assert_not_called()

    def test_known_identity_uses_resolved_locked_user_and_defined_timestamp(self):
        user = SimpleNamespace(pk=17, email="reset-user@example.invalid")
        locked_user = SimpleNamespace(pk=17, email="reset-user@example.invalid")
        user_manager = mock.Mock()
        user_manager.filter.return_value.first.return_value = user
        user_manager.select_for_update.return_value.filter.return_value.first.return_value = locked_user
        otp_manager = mock.Mock()
        otp_manager.filter.return_value.count.return_value = 0
        fixed_now = datetime(2026, 10, 15, 12, 0, 0)

        with mock.patch.object(views_reset.LegacyUser, "objects", user_manager), \
                mock.patch.object(views_reset.PasswordResetOTP, "objects", otp_manager), \
                mock.patch.object(views_reset.transaction, "atomic", return_value=nullcontext()), \
                mock.patch.object(views_reset.timezone, "now", return_value=fixed_now), \
                mock.patch.object(views_reset.secrets, "randbelow", return_value=123456), \
                mock.patch.object(views_reset, "send_mail") as send_mail:
            response = views_reset.request_reset(self.request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), views_reset.GENERIC)
        user_manager.filter.assert_called_once_with(email="reset-user@example.invalid")
        user_manager.select_for_update.return_value.filter.assert_called_once_with(pk=17)
        otp_manager.create.assert_called_once()
        created = otp_manager.create.call_args.kwargs
        self.assertEqual(created["user_id"], 17)
        self.assertEqual(created["created_at"], fixed_now)
        self.assertEqual(created["expires_at"], fixed_now + timedelta(seconds=views_reset.settings.PASSWORD_RESET_OTP_TTL_SECONDS))
        send_mail.assert_called_once()
        self.assertEqual(send_mail.call_args.args[3], [locked_user.email])
        self.assertNotIn("123456", response.content.decode("utf-8"))
