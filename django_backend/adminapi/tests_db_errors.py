"""Database-FREE tests for safe database error logging and the Cart Discount error responses."""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import mock
from django.db import InterfaceError, OperationalError, ProgrammingError
from django.test import SimpleTestCase

from adminapi import cart_discount, db_errors


def driver_error(wrapper, message, sqlstate=None):
    """A Django-wrapped driver error whose cause carries SQLSTATE metadata."""
    error = wrapper(message)
    if sqlstate:
        cause = RuntimeError("simulated database driver cause")
        cause.sqlstate = sqlstate
        error.__cause__ = cause
    return error


class ClassificationTests(SimpleTestCase):
    def test_sqlstates_map_to_stable_categories(self):
        cases = [
            (driver_error(ProgrammingError, "relation does not exist", "42P01"), "table_missing"),
            (driver_error(ProgrammingError, "permission denied", "42501"), "permission_denied"),
            (driver_error(OperationalError, "database does not exist", "3D000"), "database_missing"),
            (driver_error(OperationalError, "password authentication failed", "28P01"), "authentication_failed"),
            (driver_error(OperationalError, "connection failure", "08006"), "database_unavailable"),
            (driver_error(OperationalError, "server shutting down", "57P01"), "database_unavailable"),
            (OperationalError("connection refused"), "database_unavailable"),
            (InterfaceError("connection already closed"), "database_unavailable"),
            (driver_error(ProgrammingError, "syntax error", "42601"), "database_error"),
        ]
        for error, expected in cases:
            with self.subTest(expected=expected, message=str(error)):
                self.assertEqual(db_errors.classify(error)[0], expected)


class ScrubTests(SimpleTestCase):
    def test_configured_password_and_credential_patterns_are_removed(self):
        fake_settings = SimpleNamespace(DATABASES={"default": {"PASSWORD": "s3cr3tpw"}})
        with mock.patch.object(db_errors, "settings", fake_settings):
            text = db_errors.scrub("failed for s3cr3tpw password=hunter2 url postgresql://user:topsecret@host/db token=abc")
        for leaked in ("s3cr3tpw", "hunter2", "topsecret", "token=abc"):
            self.assertNotIn(leaked, text)

    def test_only_driver_messages_are_logged_never_other_exception_text(self):
        with self.assertLogs("adminapi.db", level="ERROR") as logs:
            db_errors.log_db_error("Example", ValueError("customer@example.invalid 9999999999"))
        output = "\n".join(logs.output)
        self.assertIn("type=ValueError", output)
        self.assertNotIn("customer@example.invalid", output)
        self.assertNotIn("9999999999", output)

    def test_only_first_line_of_driver_message_is_logged(self):
        error = driver_error(ProgrammingError, "duplicate key\nDETAIL: Key (email)=(a@example.invalid) exists", "23505")
        with self.assertLogs("adminapi.db", level="ERROR") as logs:
            db_errors.log_db_error("Example", error)
        output = "\n".join(logs.output)
        self.assertIn("sqlstate=23505", output)
        self.assertNotIn("a@example.invalid", output)


class CartDiscountErrorResponseTests(SimpleTestCase):
    def _get_with_error(self, error):
        manager = mock.Mock()
        manager.filter.side_effect = error
        with mock.patch.object(cart_discount.CartDiscountSettings, "objects", manager):
            return cart_discount.CartDiscountSettingsView().get(mock.Mock())

    def test_missing_table_is_reported_specifically_and_logged(self):
        error = driver_error(ProgrammingError, 'relation "admin_cart_discount_settings" does not exist\nLINE 1: SELECT', "42P01")
        with self.assertLogs("adminapi.db", level="ERROR") as logs:
            response = self._get_with_error(error)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "table_missing")
        self.assertIn("not initialized", response.data["detail"])
        output = "\n".join(logs.output)
        self.assertIn("category=table_missing", output)
        self.assertIn("sqlstate=42P01", output)

    def test_connection_errors_are_not_reported_as_missing_storage(self):
        with self.assertLogs("adminapi.db", level="ERROR"):
            response = self._get_with_error(OperationalError("connection refused"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "database_unavailable")
        self.assertNotIn("not initialized", response.data["detail"])

    def test_authentication_failure_response_has_no_credentials(self):
        error = driver_error(OperationalError, "FATAL: password authentication failed for user postgres", "28P01")
        with self.assertLogs("adminapi.db", level="ERROR"):
            response = self._get_with_error(error)
        self.assertEqual(response.data["code"], "authentication_failed")
        self.assertNotIn("postgres", response.data["detail"].lower().replace("postgresql", ""))

    def test_save_failure_states_nothing_was_saved_and_logs(self):
        manager = mock.Mock()
        manager.select_for_update.return_value.filter.side_effect = driver_error(ProgrammingError, "permission denied", "42501")
        request = mock.Mock(data={"enabled": True, "minimum_subtotal": "10", "fixed_discount_amount": "2"})
        with mock.patch.object(cart_discount.CartDiscountSettings, "objects", manager), \
                mock.patch.object(cart_discount.transaction, "atomic", return_value=nullcontext()), \
                self.assertLogs("adminapi.db", level="ERROR"):
            response = cart_discount.CartDiscountSettingsView().put(request)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "permission_denied")
        self.assertIn("No settings were confirmed saved.", response.data["detail"])

    def test_successful_read_still_returns_defaults_when_row_is_missing(self):
        manager = mock.Mock()
        manager.filter.return_value.first.return_value = None
        with mock.patch.object(cart_discount.CartDiscountSettings, "objects", manager):
            response = cart_discount.CartDiscountSettingsView().get(mock.Mock())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"enabled": False, "minimum_subtotal": "0.00",
                                         "fixed_discount_amount": "0.00", "updated_at": None})
