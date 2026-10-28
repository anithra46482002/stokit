"""Database-FREE authentication, ownership and safe-error regression tests (Task 1A).

Evidence level: UNIT / REGRESSION. The real view functions and the real URL configuration are
executed; only the SQL helper layer, the ORM managers and the mailer are replaced by test doubles.
These tests do NOT prove behaviour against PostgreSQL data (see the Task 1A report: DB-backed
integration tests are BLOCKED until an approved isolated database exists).
No real credentials, tokens or OTPs are used; every identity below is synthetic.
"""
import json
from contextlib import nullcontext
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

from django.db import OperationalError
from django.test import Client, RequestFactory, SimpleTestCase

from accounts import services
from accounts.hashers import hash_password
from config.tests_postgres_only import load_settings
from legacy_api import (views_auth, views_cart, views_favorites, views_orders, views_reset)
from legacy_api.common import SESSION_EXPIRED
from legacy_api.urls import urlpatterns

USER = {"id": 7, "username": "alice", "email": "alice@example.invalid", "fullname": "Alice",
        "phone": "111", "address": "a"}
SESSION = SimpleNamespace(pk=11, user_id=7)
TOKEN = "a" * 64
BEARER = {"HTTP_AUTHORIZATION": "Bearer " + TOKEN}
PUBLIC_ROUTES = {"login", "banner", "acc/", "acc/reset", "contactus"}  # registered with auth=False
PASSWORD = "correct-horse-battery-1"
rf = RequestFactory()


def authed(user=USER):
    return mock.patch("accounts.services.authenticate_token", return_value=(SESSION, user))


def post(path, body=None, raw=None, **extra):
    data = raw if raw is not None else json.dumps(body if body is not None else {})
    return rf.post(path, data=data, content_type="application/json", **extra)


def body_of(response):
    return json.loads(response.content)


# --------------------------------------------------------------------------- bearer / gate
class BearerParsingTests(SimpleTestCase):
    def test_missing_malformed_and_wrong_scheme_headers_yield_empty_token(self):
        for header in (None, "", "Bearer", "Bearer   ", "Basic abc", "Token abc", "abc"):
            with self.subTest(header=header):
                self.assertEqual(services.parse_bearer(header or ""), "")

    def test_well_formed_header_is_trimmed(self):
        self.assertEqual(services.parse_bearer("Bearer   tok  "), "tok")


class ProtectedRouteGateTests(SimpleTestCase):
    """Every non-public /api/ route rejects an unauthenticated call BEFORE any method check or DB access."""

    def setUp(self):
        self.client = Client()
        self.routes = [str(p.pattern) for p in urlpatterns]

    def test_route_inventory_is_complete(self):
        self.assertEqual(len(self.routes), 33)
        self.assertTrue(PUBLIC_ROUTES <= set(self.routes))

    def test_protected_routes_return_exact_legacy_401_for_every_method_without_token(self):
        for route in self.routes:
            if route in PUBLIC_ROUTES:
                continue
            for method in ("GET", "POST", "PUT", "DELETE", "OPTIONS"):
                with self.subTest(route=route, method=method):
                    response = self.client.generic(method, "/api/" + route)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(body_of(response), SESSION_EXPIRED)

    def test_protected_routes_reject_malformed_and_unknown_tokens(self):
        headers = ("Bearer", "Basic abc", "Bearer " + "0" * 64, "Bearer not-a-real-token")
        for route in self.routes:
            if route in PUBLIC_ROUTES:
                continue
            for header in headers:
                with self.subTest(route=route, header=header), \
                        mock.patch("accounts.services.authenticate_token", return_value=None):
                    response = self.client.generic("POST", "/api/" + route, HTTP_AUTHORIZATION=header)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(body_of(response), SESSION_EXPIRED)

    def test_401_body_never_contains_the_presented_token(self):
        with mock.patch("accounts.services.authenticate_token", return_value=None):
            response = self.client.post("/api/profile", HTTP_AUTHORIZATION="Bearer " + TOKEN)
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(TOKEN, response.content.decode())

    def test_public_routes_do_not_require_a_token(self):
        with mock.patch("legacy_api.views_catalog.fetchone", return_value={"total": 0}), \
                mock.patch("legacy_api.views_catalog.fetchall", return_value=[]):
            self.assertEqual(self.client.get("/api/banner").status_code, 200)
        self.assertEqual(self.client.get("/api/contactus").status_code, 200)
        self.assertEqual(self.client.post("/api/login", "{}", content_type="application/json").status_code, 200)
        self.assertEqual(self.client.post("/api/acc/", "{}", content_type="application/json").status_code, 200)
        self.assertEqual(self.client.post("/api/acc/reset", "{}", content_type="application/json").status_code, 400)


class AuthenticateTokenTests(SimpleTestCase):
    def test_empty_token_never_queries_sessions(self):
        with mock.patch.object(services, "UserDeviceSession") as model:
            self.assertIsNone(services.authenticate_token(""))
            self.assertIsNone(services.authenticate_token(None))
        model.objects.active.assert_not_called()

    def test_unknown_revoked_expired_or_tampered_token_is_rejected_and_only_hash_is_queried(self):
        with mock.patch.object(services, "UserDeviceSession") as model:
            model.objects.active.return_value.filter.return_value.first.return_value = None
            self.assertIsNone(services.authenticate_token(TOKEN))
        model.objects.active.return_value.filter.assert_called_once_with(token_hash=services.hash_token(TOKEN))
        self.assertNotEqual(services.hash_token(TOKEN), TOKEN)

    def test_session_of_deleted_account_is_dead(self):
        session = SimpleNamespace(pk=1, user_id=9, last_activity_at=datetime.now())
        with mock.patch.object(services, "UserDeviceSession") as model, \
                mock.patch.object(services, "LegacyUser") as users:
            model.objects.active.return_value.filter.return_value.first.return_value = session
            users.objects.filter.return_value.values.return_value.first.return_value = None
            self.assertIsNone(services.authenticate_token(TOKEN))

    def test_activity_touch_only_updates_unrevoked_session_and_only_when_stale(self):
        now = datetime(2026, 10, 19, 12, 0, 0)
        stale = SimpleNamespace(pk=1, user_id=7, last_activity_at=now - timedelta(hours=1))
        fresh = SimpleNamespace(pk=2, user_id=7, last_activity_at=now)
        for session, expect_update in ((stale, True), (fresh, False)):
            with self.subTest(pk=session.pk), mock.patch.object(services, "UserDeviceSession") as model, \
                    mock.patch.object(services, "LegacyUser") as users, \
                    mock.patch.object(services.timezone, "now", return_value=now):
                model.objects.active.return_value.filter.return_value.first.return_value = session
                users.objects.filter.return_value.values.return_value.first.return_value = dict(USER)
                result = services.authenticate_token(TOKEN)
                self.assertEqual(result[1]["username"], "alice")
                self.assertEqual(model.objects.filter.called, expect_update)
                if expect_update:
                    model.objects.filter.assert_called_once_with(pk=1, revoked_at__isnull=True)

    def test_revoke_session_is_idempotent_and_conditional(self):
        with mock.patch.object(services, "UserDeviceSession") as model:
            services.revoke_session(5, reason="logout")
        model.objects.filter.assert_called_once_with(pk=5, revoked_at__isnull=True)


# --------------------------------------------------------------------------- login
class LoginTests(SimpleTestCase):
    def _login(self, body=None, raw=None, fetch=None):
        request = post("/api/login", body, raw=raw)
        with mock.patch.object(views_auth, "fetchone", return_value=fetch) as fetchone:
            response = views_auth.login(request)
        return response, fetchone

    def test_missing_or_empty_fields_are_http_200_failures_without_db_lookup(self):
        for body in ({}, {"username": "alice"}, {"password": "x"}, {"username": "  ", "password": "x"},
                     {"username": "alice", "password": ""}, [], "text", None):
            with self.subTest(body=body):
                response, fetchone = self._login(raw=json.dumps(body))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(body_of(response), {"success": False, "message": "Username and password are required"})
                fetchone.assert_not_called()

    def test_malformed_json_is_treated_as_missing_fields(self):
        response, fetchone = self._login(raw="{not json")
        self.assertEqual(body_of(response)["message"], "Username and password are required")
        fetchone.assert_not_called()

    def test_unknown_user_and_wrong_password_are_indistinguishable(self):
        stored = {"id": 7, "username": "alice", "email": "e", "fullname": "f", "password": hash_password(PASSWORD)}
        unknown, _ = self._login({"username": "nobody", "password": PASSWORD}, fetch=None)
        wrong, _ = self._login({"username": "alice", "password": "wrong-password-1"}, fetch=stored)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(wrong.status_code, 200)
        self.assertEqual(body_of(unknown), body_of(wrong))
        self.assertEqual(body_of(wrong), {"success": False, "message": "Invalid username or password"})

    def test_valid_login_response_shape_and_no_secret_leak(self):
        stored = {"id": 7, "username": "alice", "email": "alice@example.invalid", "fullname": "Alice",
                  "password": hash_password(PASSWORD)}
        with mock.patch("accounts.services.create_session", return_value=TOKEN) as create:
            response, _ = self._login({"username": " alice ", "password": PASSWORD}, fetch=stored)
        self.assertEqual(response.status_code, 200)
        body = body_of(response)
        self.assertEqual(set(body), {"success", "message", "token", "user"})
        self.assertIs(body["success"], True)
        self.assertEqual(body["message"], "Login successful")
        self.assertEqual(set(body["user"]), {"id", "username", "email", "fullname"})
        self.assertIsInstance(body["user"]["id"], int)
        text = response.content.decode()
        self.assertNotIn(PASSWORD, text)
        self.assertNotIn("$argon2", text)
        create.assert_called_once()

    def test_legacy_bcrypt_hash_is_accepted(self):
        import bcrypt
        legacy = "$2y$" + bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()[4:]
        stored = {"id": 7, "username": "alice", "email": "e", "fullname": "f", "password": legacy}
        with mock.patch("accounts.services.create_session", return_value=TOKEN):
            response, _ = self._login({"username": "alice", "password": PASSWORD}, fetch=stored)
        self.assertIs(body_of(response)["success"], True)

    def test_session_limit_is_an_ordinary_http_200_failure_without_token(self):
        stored = {"id": 7, "username": "alice", "email": "e", "fullname": "f", "password": hash_password(PASSWORD)}
        with mock.patch("accounts.services.create_session", side_effect=services.SessionLimitReached()):
            response, _ = self._login({"username": "alice", "password": PASSWORD}, fetch=stored)
        self.assertEqual(response.status_code, 200)
        body = body_of(response)
        self.assertIs(body["success"], False)
        self.assertIn("session", body["message"].lower())
        self.assertNotIn("token", body)

    def test_form_encoded_credentials_are_still_accepted(self):
        stored = {"id": 7, "username": "alice", "email": "e", "fullname": "f", "password": hash_password(PASSWORD)}
        request = rf.post("/api/login", {"username": "alice", "password": PASSWORD})
        with mock.patch.object(views_auth, "fetchone", return_value=stored), \
                mock.patch("accounts.services.create_session", return_value=TOKEN):
            self.assertIs(body_of(views_auth.login(request))["success"], True)

    def test_nul_byte_credentials_are_rejected_without_reaching_the_database(self):
        """REGRESSION (D3): PostgreSQL text parameters cannot contain NUL; this must not become an HTTP 500."""
        for body in ({"username": "ali\x00ce", "password": PASSWORD}, {"username": "alice", "password": "pw\x00x"}):
            with self.subTest(body=body):
                response, fetchone = self._login(body)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(body_of(response), {"success": False, "message": "Invalid username or password"})
                fetchone.assert_not_called()


# --------------------------------------------------------------------------- logout / profile / geocode
class LogoutTests(SimpleTestCase):
    def test_logout_revokes_only_the_presented_session(self):
        with authed(), mock.patch("accounts.services.revoke_session") as revoke:
            response = views_auth.logout(post("/api/logout", **BEARER))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body_of(response), {"success": True, "message": "Logout successful"})
        revoke.assert_called_once_with(11, reason="logout")

    def test_revoked_token_is_rejected_on_reuse(self):
        with mock.patch("accounts.services.authenticate_token", return_value=None):
            response = views_auth.logout(post("/api/logout", **BEARER))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(body_of(response), SESSION_EXPIRED)


class ProfileTests(SimpleTestCase):
    ROW = {"profile_picture": None, "shop_name": "S", "fullname": "Alice", "address": "1 Rd", "city": "Kochi",
           "created_at": datetime(2026, 1, 2), "username": "alice", "phone": "111", "email": "alice@example.invalid",
           "status": "ACTIVE", "vip_discount": "N", "vip_percentage": 0, "store_maped": "N",
           "password": "$argon2id$secret-hash", "token": "legacy-token-value"}

    def test_profile_shape_and_no_credential_fields(self):
        with authed(), mock.patch.object(views_auth, "fetchone", return_value=dict(self.ROW)):
            response = views_auth.profile(rf.get("/api/profile", **BEARER))
        body = body_of(response)
        self.assertEqual(set(body), {"success", "profile"})
        self.assertEqual(set(body["profile"]), {
            "profile_picture_url", "shop_name", "owner", "location", "account_created_on", "username", "mobile",
            "email", "account_status", "VIP", "VIP_per", "store_maped"})
        self.assertEqual(body["profile"]["account_status"], "active")
        self.assertIsInstance(body["profile"]["VIP_per"], float)
        text = response.content.decode()
        self.assertNotIn("secret-hash", text)
        self.assertNotIn("legacy-token-value", text)

    def test_profile_is_scoped_to_the_authenticated_user_not_the_request_body(self):
        request = post("/api/profile", {"username": "mallory", "id": 99}, **BEARER)
        with authed(), mock.patch.object(views_auth, "fetchone", return_value=dict(self.ROW)) as fetchone:
            views_auth.profile(request)
        self.assertEqual(fetchone.call_args.args[1], ["alice"])


class GeocodeTests(SimpleTestCase):
    def _call(self, body=None, raw=None, current=None, method="post"):
        request = post("/api/geocode", body, raw=raw, **BEARER) if method == "post" else rf.get("/api/geocode", **BEARER)
        with authed(), mock.patch.object(views_auth, "fetchone", return_value=current), \
                mock.patch.object(views_auth, "execute", return_value=1) as execute:
            return views_auth.geocode(request), execute

    def test_non_post_is_405(self):
        response, execute = self._call(method="get")
        self.assertEqual(response.status_code, 405)
        execute.assert_not_called()

    def test_missing_or_php_empty_coordinates_are_400(self):
        for body in ({}, {"latitude": "1"}, {"latitude": "", "longitude": "2"}, {"latitude": 0, "longitude": 5},
                     {"latitude": "0", "longitude": "5"}, {"latitude": None, "longitude": 1}):
            with self.subTest(body=body):
                response, execute = self._call(body)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(body_of(response), {"status": "error", "message": "Latitude and longitude are required."})
                execute.assert_not_called()

    def test_location_update_is_written_only_for_the_authenticated_user(self):
        current = {"latitude": "", "longitude": "", "store_maped": "N"}
        response, execute = self._call({"latitude": 9.93, "longitude": "76.26", "username": "mallory"}, current=current)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body_of(response), {"status": "success", "message": "Location updated successfully."})
        self.assertEqual(execute.call_args.args[1], ["9.93", "76.26", "alice"])

    def test_unchanged_location_keeps_legacy_200_error_shape(self):
        current = {"latitude": "9.93", "longitude": "76.26", "store_maped": "Y"}
        response, _ = self._call({"latitude": "9.93", "longitude": "76.26"}, current=current)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body_of(response), {"status": "error", "message": "User not found or location already up to date."})

    def test_non_scalar_oversized_or_non_finite_coordinates_are_400_and_not_written(self):
        """REGRESSION (D4): users.latitude/longitude are varchar(125); garbage must not reach the database."""
        bad = ({"latitude": {"a": 1}, "longitude": "1"}, {"latitude": [1], "longitude": "1"},
               {"latitude": True, "longitude": "1"}, {"latitude": "9" * 126, "longitude": "1"},
               {"latitude": "1", "longitude": "1\x00"})
        for body in bad:
            with self.subTest(body=str(body)[:40]):
                response, execute = self._call(body)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(body_of(response)["status"], "error")
                execute.assert_not_called()
        response, execute = self._call(raw='{"latitude": NaN, "longitude": 1}')
        self.assertEqual(response.status_code, 400)
        execute.assert_not_called()


# --------------------------------------------------------------------------- password reset
NOW = datetime(2026, 10, 19, 12, 0, 0)


def _record(otp="123456", user_id=17, **over):
    base = dict(otp_hash=views_reset._otp_digest(user_id, otp), expires_at=NOW + timedelta(minutes=5),
                attempts=0, consumed_at=None, verified_at=None, save=mock.Mock())
    base.update(over)
    return SimpleNamespace(**base)


class _ResetHarness:
    def invoke(self, body, record=None, user=SimpleNamespace(pk=17, email="u@example.invalid")):
        users, otps = mock.Mock(), mock.Mock()
        users.filter.return_value.first.return_value = user
        otps.select_for_update.return_value.filter.return_value.order_by.return_value.first.return_value = record
        with mock.patch.object(views_reset.LegacyUser, "objects", users), \
                mock.patch.object(views_reset.PasswordResetOTP, "objects", otps), \
                mock.patch.object(views_reset.transaction, "atomic", return_value=nullcontext()), \
                mock.patch.object(views_reset.timezone, "now", return_value=NOW):
            response = views_reset.reset_password(post("/api/acc/reset", body))
        return response, users, otps


class ResetConfirmTests(_ResetHarness, SimpleTestCase):
    GOOD = {"email": "u@example.invalid", "otp": "123456", "new_password": "new-secret-pass-1"}
    INVALID = {"success": False, "message": "Invalid or expired reset code"}

    def test_get_is_405(self):
        self.assertEqual(views_reset.reset_password(rf.get("/api/acc/reset")).status_code, 405)

    def test_malformed_payloads_are_400_and_never_look_up_a_user(self):
        """REGRESSION (D2): a JSON list/number/bool must not be stringified into a password or identity."""
        cases = [
            {}, {"email": "u@example.invalid"},
            {**self.GOOD, "otp": "12345"}, {**self.GOOD, "otp": "12345a"}, {**self.GOOD, "otp": "1234567"},
            {**self.GOOD, "new_password": "short"},
            {**self.GOOD, "new_password": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
            {**self.GOOD, "new_password": {"a": "b" * 12}},
            {**self.GOOD, "new_password": 1234567890},
            {**self.GOOD, "new_password": None},
            {**self.GOOD, "email": None, "username": None},
            {**self.GOOD, "email": ["u@example.invalid"]},
            {**self.GOOD, "email": "u\x00@example.invalid"},
        ]
        for body in cases:
            with self.subTest(body=str(body)[:60]):
                response, users, otps = self.invoke(body, record=_record())
                self.assertEqual(response.status_code, 400)
                self.assertEqual(body_of(response), {"success": False, "message": "Invalid reset request"})
                users.filter.assert_not_called()
                otps.select_for_update.assert_not_called()

    def test_unknown_user_no_record_expired_and_exhausted_attempts_share_one_generic_400(self):
        max_attempts = views_reset.settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS
        scenarios = {
            "unknown user": dict(user=None, record=None),
            "no active otp": dict(record=None),
            "expired": dict(record=_record(expires_at=NOW - timedelta(seconds=1))),
            "expires exactly now": dict(record=_record(expires_at=NOW)),
            "attempts exhausted": dict(record=_record(attempts=max_attempts)),
        }
        for name, kw in scenarios.items():
            with self.subTest(name):
                response, _, _ = self.invoke(self.GOOD, **kw)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(body_of(response), self.INVALID)

    def test_wrong_otp_increments_attempts_and_final_attempt_burns_the_code(self):
        record = _record(attempts=0)
        response, _, _ = self.invoke({**self.GOOD, "otp": "000000"}, record=record)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(body_of(response), self.INVALID)
        self.assertEqual(record.attempts, 1)
        self.assertIsNone(record.consumed_at)
        last = _record(attempts=views_reset.settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS - 1)
        self.invoke({**self.GOOD, "otp": "000000"}, record=last)
        self.assertEqual(last.consumed_at, NOW)

    def test_correct_otp_is_consumed_before_the_password_changes_and_password_is_hashed(self):
        record = _record()
        order = []
        users = mock.Mock()
        users.filter.return_value.first.return_value = SimpleNamespace(pk=17, email="u@example.invalid")
        users.filter.return_value.update.side_effect = lambda **kw: order.append(("update", record.consumed_at, kw))
        record.save.side_effect = lambda **kw: order.append(("save", kw))
        otps = mock.Mock()
        otps.select_for_update.return_value.filter.return_value.order_by.return_value.first.return_value = record
        with mock.patch.object(views_reset.LegacyUser, "objects", users), \
                mock.patch.object(views_reset.PasswordResetOTP, "objects", otps), \
                mock.patch.object(views_reset.transaction, "atomic", return_value=nullcontext()), \
                mock.patch.object(views_reset.timezone, "now", return_value=NOW):
            response = views_reset.reset_password(post("/api/acc/reset", self.GOOD))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body_of(response), {"success": True, "message": "Password reset successful"})
        self.assertEqual([step[0] for step in order], ["save", "update"])
        self.assertEqual(order[1][1], NOW)  # already consumed when the password update ran
        stored = order[1][2]["password"]
        self.assertTrue(stored.startswith("$argon2id$"))
        self.assertNotEqual(stored, self.GOOD["new_password"])
        self.assertNotIn(self.GOOD["new_password"], response.content.decode())

    def test_used_otp_cannot_be_replayed(self):
        response, users, _ = self.invoke(self.GOOD, record=None)  # consumed rows are filtered out by the query
        self.assertEqual(response.status_code, 400)
        users.filter.return_value.update.assert_not_called()

    def test_username_identity_and_numeric_otp_are_accepted(self):
        response, _, _ = self.invoke({"username": "alice", "otp": 123456, "password": "new-secret-pass-1"}, record=_record())
        self.assertEqual(response.status_code, 200)

    def test_otp_digest_is_user_bound_and_not_the_plain_code(self):
        a, b = views_reset._otp_digest(1, "123456"), views_reset._otp_digest(2, "123456")
        self.assertNotEqual(a, b)
        self.assertEqual(len(a), 64)
        self.assertNotIn("123456", a)


class ResetRequestTests(SimpleTestCase):
    def _call(self, body, **kw):
        users, otps = mock.Mock(), mock.Mock()
        users.filter.return_value.first.return_value = kw.get("user")
        users.select_for_update.return_value.filter.return_value.first.return_value = kw.get("user")
        otps.filter.return_value.count.return_value = kw.get("recent", 0)
        with mock.patch.object(views_reset.LegacyUser, "objects", users), \
                mock.patch.object(views_reset.PasswordResetOTP, "objects", otps), \
                mock.patch.object(views_reset.transaction, "atomic", return_value=nullcontext()), \
                mock.patch.object(views_reset.timezone, "now", return_value=NOW), \
                mock.patch.object(views_reset, "send_mail") as send_mail:
            response = views_reset.request_reset(post("/api/acc/", body))
        return response, users, otps, send_mail

    def test_get_is_405(self):
        self.assertEqual(views_reset.request_reset(rf.get("/api/acc/")).status_code, 405)

    def test_null_empty_non_string_or_nul_identity_is_generic_and_never_looked_up(self):
        """REGRESSION (D2): null used to be stringified to 'None' and looked up as a username."""
        for body in ({}, {"email": None}, {"email": ""}, {"email": None, "username": None}, {"email": ["a"]},
                     {"email": {"a": 1}}, {"email": True}, {"email": "a\x00b"}):
            with self.subTest(body=body):
                response, users, otps, send_mail = self._call(body)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(body_of(response), views_reset.GENERIC)
                users.filter.assert_not_called()
                otps.create.assert_not_called()
                send_mail.assert_not_called()

    def test_empty_email_falls_back_to_username(self):
        _, users, _, _ = self._call({"email": "", "username": "alice"})
        users.filter.assert_any_call(email="alice")
        users.filter.assert_any_call(username="alice")

    def test_unknown_and_known_accounts_get_identical_responses(self):
        known = self._call({"email": "u@example.invalid"}, user=SimpleNamespace(pk=17, email="u@example.invalid"))
        unknown = self._call({"email": "nobody@example.invalid"}, user=None)
        self.assertEqual(known[0].status_code, unknown[0].status_code)
        self.assertEqual(known[0].content, unknown[0].content)
        known[3].assert_called_once()
        unknown[3].assert_not_called()

    def test_otp_is_mailed_but_never_returned_or_stored_in_plain_text(self):
        with mock.patch.object(views_reset.secrets, "randbelow", return_value=48151):
            response, _, otps, send_mail = self._call({"email": "u@example.invalid"},
                                                      user=SimpleNamespace(pk=17, email="u@example.invalid"))
        self.assertNotIn("048151", response.content.decode())
        self.assertIn("048151", send_mail.call_args.args[1])
        created = otps.create.call_args.kwargs
        self.assertNotIn("048151", created["otp_hash"])
        self.assertEqual(created["otp_hash"], views_reset._otp_digest(17, "048151"))

    def test_hourly_request_cap_silently_skips_mail_and_new_otp(self):
        response, _, otps, send_mail = self._call({"email": "u@example.invalid"},
                                                  user=SimpleNamespace(pk=17, email="u@example.invalid"), recent=3)
        self.assertEqual(body_of(response), views_reset.GENERIC)
        otps.create.assert_not_called()
        send_mail.assert_not_called()


class MailBackendDefaultTests(SimpleTestCase):
    def test_default_mail_backend_never_prints_the_otp_to_server_logs(self):
        """REGRESSION (D5): the console backend writes the full mail body (including the OTP) to stdout."""
        backend = load_settings()["EMAIL_BACKEND"]
        self.assertNotIn("console", backend)
        self.assertEqual(backend, "django.core.mail.backends.dummy.EmailBackend")

    def test_explicit_mail_backend_is_still_honoured(self):
        backend = "django.core.mail.backends.smtp.EmailBackend"
        self.assertEqual(load_settings(EMAIL_BACKEND=backend)["EMAIL_BACKEND"], backend)


# --------------------------------------------------------------------------- safe error handling
class SafeDatabaseErrorTests(SimpleTestCase):
    LEAK = 'FATAL: password authentication failed for user "postgres" host 10.0.0.5 secret-token-xyz'
    SAFE = {"status": "error", "message": "Internal server error"}

    def test_database_failure_in_a_handler_returns_sanitised_json_500(self):
        """REGRESSION (D1): previously an unhandled exception (HTML technical page when DEBUG=1)."""
        request = post("/api/login", {"username": "alice", "password": PASSWORD})
        with mock.patch.object(views_auth, "fetchone", side_effect=OperationalError(self.LEAK)):
            with self.assertLogs("legacy_api", level="ERROR") as logs:
                response = views_auth.login(request)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(body_of(response), self.SAFE)
        text = response.content.decode()
        for fragment in ("secret-token-xyz", "postgres", "10.0.0.5", "Traceback", PASSWORD):
            self.assertNotIn(fragment, text)
        self.assertNotIn("secret-token-xyz", "\n".join(logs.output))

    def test_database_failure_during_token_lookup_is_500_not_session_expired(self):
        """A DB outage must not be reported as an expired session (the client would discard a valid login)."""
        with mock.patch("accounts.services.authenticate_token", side_effect=OperationalError(self.LEAK)), \
                self.assertLogs("legacy_api", level="ERROR"):
            response = views_auth.profile(rf.get("/api/profile", **BEARER))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(body_of(response), self.SAFE)

    def test_database_failure_in_password_reset_is_sanitised(self):
        users = mock.Mock()
        users.filter.return_value.first.side_effect = OperationalError(self.LEAK)
        with mock.patch.object(views_reset.LegacyUser, "objects", users), self.assertLogs("legacy_api", level="ERROR"):
            response = views_reset.request_reset(post("/api/acc/", {"email": "u@example.invalid"}))
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret-token-xyz", response.content.decode())

    def test_programming_errors_are_not_swallowed(self):
        with mock.patch.object(views_auth, "fetchone", side_effect=RuntimeError("bug")):
            with self.assertRaises(RuntimeError):
                views_auth.login(post("/api/login", {"username": "alice", "password": PASSWORD}))


# --------------------------------------------------------------------------- ownership (verification of existing behaviour)
class OwnershipScopingTests(SimpleTestCase):
    """The authenticated username/email -- never a body/query value -- scopes every customer-owned read/write."""

    def test_favourite_toggle_uses_authenticated_username(self):
        request = post("/api/fav", {"product_id": 5, "user_id": "mallory", "username": "mallory"}, **BEARER)
        with authed(), mock.patch.object(views_favorites.transaction, "atomic", return_value=nullcontext()), \
                mock.patch.object(views_favorites, "fetchone", return_value=None), \
                mock.patch.object(views_favorites, "execute") as execute:
            response = views_favorites.fav(request)
        self.assertEqual(body_of(response)["fav_status"], "added")
        self.assertEqual(execute.call_args.args[1], ["alice", 5])

    def test_favourite_list_is_scoped_to_authenticated_username(self):
        request = rf.get("/api/favpage?user_id=mallory&username=mallory", **BEARER)
        with authed(), mock.patch.object(views_favorites, "fetchall", return_value=[]) as fetchall, \
                mock.patch.object(views_favorites, "fetchone", return_value={"total": 0}) as fetchone:
            views_favorites.favpage(request)
        self.assertEqual(fetchall.call_args.args[1][0], "alice")
        self.assertEqual(fetchone.call_args.args[1], ["alice"])

    def test_cart_mutation_is_scoped_to_authenticated_username(self):
        request = post("/api/cart_action", {"action": "remove", "variant_id": 3, "username": "mallory"}, **BEARER)
        with authed(), mock.patch.object(views_cart.transaction, "atomic", return_value=nullcontext()), \
                mock.patch.object(views_cart, "lock_user_cart"), \
                mock.patch.object(views_cart, "fetchall", return_value=[{"product_id": 5, "qty": 1}]) as fetchall, \
                mock.patch.object(views_cart, "execute", return_value=1) as execute:
            views_cart.cart_action(request)
        self.assertEqual(fetchall.call_args.args[1], ["alice", 3])
        # the product comes from the authenticated user's own cart row, never from the request body
        self.assertEqual(execute.call_args.args[1], ["alice", 3, 5])

    def test_order_list_is_scoped_to_authenticated_users_email(self):
        request = rf.get("/api/orders?email=mallory@example.invalid", **BEARER)
        with authed(), mock.patch.object(views_orders, "fetchone",
                                         side_effect=[{"email": "alice@example.invalid"}, {"total_orders": 0}]), \
                mock.patch.object(views_orders, "fetchall", return_value=[]) as fetchall:
            views_orders.orders(request)
        self.assertEqual(fetchall.call_args.args[1][0], "alice@example.invalid")

    def test_order_details_of_another_customer_is_404(self):
        request = post("/api/order_details", {"order_id": 5}, **BEARER)
        with authed(), mock.patch.object(views_orders, "fetchone",
                                         return_value={"email": "alice@example.invalid", "gst_percentage": 0,
                                                       "delivery_charges": 0}), \
                mock.patch.object(views_orders, "fetchall", return_value=[]) as fetchall:
            response = views_orders.order_details(request)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(fetchall.call_args.args[1], [5, "alice@example.invalid"])

    def test_cancelling_another_customers_order_is_403_and_writes_nothing(self):
        request = post("/api/order_cancel", {"order_id": 5}, **BEARER)
        mine = {"phone": "111", "email": "alice@example.invalid"}
        theirs = {"order_id": 5, "phone": "222", "email": "bob@example.invalid", "status": "Placed"}
        with authed(), mock.patch.object(views_orders.transaction, "atomic", return_value=nullcontext()), \
                mock.patch.object(views_orders, "fetchone", side_effect=[mine, theirs]), \
                mock.patch.object(views_orders, "execute") as execute:
            response = views_orders.order_cancel(request)
        self.assertEqual(response.status_code, 403)
        execute.assert_not_called()
