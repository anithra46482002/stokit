"""Database-free tests for the admin token flow (stateless signed tokens)."""
from types import SimpleNamespace

from django.core import signing
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from adminapi.views import AdminRefreshView


class AdminRefreshTests(SimpleTestCase):
    def _refresh(self, principal):
        request = APIRequestFactory().post("/admin-api/auth/refresh")
        force_authenticate(request, user=principal)
        return AdminRefreshView.as_view()(request)

    def test_refresh_issues_token_for_same_admin_principal(self):
        response = self._refresh(SimpleNamespace(pk=9, principal_type="ADMIN", is_authenticated=True))
        self.assertEqual(response.status_code, 200)
        payload = signing.loads(response.data["token"], salt="stokit.admin-token", max_age=60)
        self.assertEqual(payload, {"admin_id": 9})

    def test_refresh_keeps_non_admin_principal_type(self):
        response = self._refresh(SimpleNamespace(pk=4, principal_type="SALESMAN", is_authenticated=True))
        payload = signing.loads(response.data["token"], salt="stokit.admin-token", max_age=60)
        self.assertEqual(payload, {"principal_type": "SALESMAN", "principal_id": 4})

    def test_refresh_requires_authentication(self):
        request = APIRequestFactory().post("/admin-api/auth/refresh")
        response = AdminRefreshView.as_view()(request)
        self.assertIn(response.status_code, (401, 403))

class AdminAuthenticationStatusTests(SimpleTestCase):
    def test_missing_credentials_return_401_with_bearer_challenge(self):
        from adminapi.operations import WarehouseAdminView

        request = APIRequestFactory().get("/admin-api/warehouses")
        response = WarehouseAdminView.as_view()(request)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], "Bearer")

    def test_authenticated_role_without_warehouse_access_remains_forbidden(self):
        from adminapi.operations import WarehouseAdminView

        request = APIRequestFactory().get("/admin-api/warehouses")
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True, role="SALESMAN"))
        response = WarehouseAdminView.as_view()(request)
        self.assertEqual(response.status_code, 403)

class AdminRoleLookupFailureTests(SimpleTestCase):
    def test_strict_role_lookup_propagates_database_failure_for_login(self):
        from django.db import ProgrammingError
        from unittest import mock
        from adminapi.auth import active_admin_role

        error = ProgrammingError('relation "accounts_adminroleassignment" does not exist')
        cause = RuntimeError("simulated PostgreSQL driver error")
        cause.sqlstate = "42P01"
        error.__cause__ = cause
        with mock.patch("adminapi.auth.AdminRoleAssignment.objects.filter", side_effect=error), \
                self.assertRaises(ProgrammingError):
            active_admin_role("ADMIN", 17, raise_on_error=True)


class AdminLoginProvisioningTests(SimpleTestCase):
    def test_missing_admin_table_returns_explicit_503_without_leaking_credentials(self):
        from django.db import ProgrammingError
        from unittest import mock
        from adminapi.views import AdminLoginView

        error = ProgrammingError('relation "admins" does not exist')
        cause = RuntimeError("simulated PostgreSQL driver error")
        cause.sqlstate = "42P01"
        error.__cause__ = cause
        request = APIRequestFactory().post(
            "/admin-api/auth/login",
            {"username": "example-user", "password": "never-log-this"},
            format="json",
        )
        with mock.patch("adminapi.views.AdminAccount.objects.filter", side_effect=error), \
                self.assertLogs("adminapi.db", level="ERROR"):
            response = AdminLoginView.as_view()(request)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "schema_not_provisioned")
        self.assertIn("schema is missing", response.data["message"])
        self.assertNotIn("never-log-this", str(response.data))

    def test_missing_role_table_does_not_issue_successful_login_token(self):
        from django.db import ProgrammingError
        from unittest import mock
        from adminapi.views import AdminLoginView

        error = ProgrammingError('relation "accounts_adminroleassignment" does not exist')
        cause = RuntimeError("simulated PostgreSQL driver error")
        cause.sqlstate = "42P01"
        error.__cause__ = cause
        account = SimpleNamespace(
            pk=17, username="example-user", email="example@example.invalid",
            fullname="Example", password="stored-hash",
        )
        request = APIRequestFactory().post(
            "/admin-api/auth/login",
            {"username": "example-user", "password": "never-log-this"},
            format="json",
        )
        with mock.patch("adminapi.views.AdminAccount.objects.filter") as query, \
                mock.patch("adminapi.views.verify_php_password", return_value=True), \
                mock.patch("adminapi.views.active_admin_role", side_effect=error), \
                self.assertLogs("adminapi.db", level="ERROR"):
            query.return_value.first.return_value = account
            response = AdminLoginView.as_view()(request)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "schema_not_provisioned")
        self.assertNotIn("token", response.data)
        self.assertNotIn("never-log-this", str(response.data))

    def test_valid_credentials_without_active_role_return_403_without_token(self):
        from unittest import mock
        from adminapi.views import AdminLoginView

        account = SimpleNamespace(
            pk=18, username="unassigned-user", email="unassigned@example.invalid",
            fullname="Unassigned", password="stored-hash",
        )
        request = APIRequestFactory().post(
            "/admin-api/auth/login",
            {"username": "unassigned-user", "password": "never-log-this"},
            format="json",
        )
        with mock.patch("adminapi.views.AdminAccount.objects.filter") as query, \
                mock.patch("adminapi.views.verify_php_password", return_value=True), \
                mock.patch("adminapi.views.active_admin_role", return_value=None):
            query.return_value.first.return_value = account
            response = AdminLoginView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "admin_role_not_configured")
        self.assertNotIn("token", response.data)
        self.assertNotIn("never-log-this", str(response.data))

