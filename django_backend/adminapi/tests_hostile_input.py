"""Regression tests for hostile/malformed admin write input (found by the audit's 1,144-request sweep).

* A non-object JSON body (`[1, 2]`, `"x"`) used to raise AttributeError -> HTTP 500 on every admin write endpoint.
* JSON `null` for a name was coerced by `str(None)` into the literal name "None".
* The role check must still run BEFORE body validation (403/401 are not turned into 400).
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from rest_framework.exceptions import ParseError
from rest_framework.test import APIRequestFactory, force_authenticate

from adminapi.field_validation import clean_text
from adminapi.permissions import AdminRolePermission, require_object_body

factory = APIRequestFactory()


def _drf_request(method, body, role="SUPER_ADMIN", content_type="application/json"):
    from rest_framework.request import Request
    from rest_framework.parsers import JSONParser
    raw = getattr(factory, method)("/admin-api/products", data=body, content_type=content_type)
    request = Request(raw, parsers=[JSONParser()])
    request.user = SimpleNamespace(is_authenticated=True, role=role)
    return request


class RequireObjectBodyTests(SimpleTestCase):
    def test_list_and_string_bodies_are_rejected_with_parse_error(self):
        for body in ("[1, 2]", '"x"', "5"):
            with self.subTest(body=body), self.assertRaisesMessage(ParseError, "must be a JSON object"):
                require_object_body(_drf_request("post", body))

    def test_object_empty_and_safe_requests_pass(self):
        require_object_body(_drf_request("post", '{"a": 1}'))
        require_object_body(_drf_request("patch", "{}"))
        require_object_body(_drf_request("get", ""))  # GET never inspected

    def test_request_double_without_data_is_ignored(self):
        require_object_body(SimpleNamespace(method="POST"))


class PermissionOrderTests(SimpleTestCase):
    def test_unauthorized_role_gets_false_not_a_parse_error(self):
        view = SimpleNamespace(required_resource="catalogue")
        request = _drf_request("post", "[1, 2]", role="DELIVERY_BOY")
        self.assertFalse(AdminRolePermission().has_permission(request, view))  # -> 403, never 400

    def test_authorized_role_with_bad_body_gets_parse_error(self):
        view = SimpleNamespace(required_resource="catalogue")
        with self.assertRaises(ParseError):
            AdminRolePermission().has_permission(_drf_request("post", "[1, 2]"), view)

    def test_authorized_role_with_object_body_is_allowed(self):
        view = SimpleNamespace(required_resource="catalogue")
        self.assertTrue(AdminRolePermission().has_permission(_drf_request("post", '{"name": "x"}'), view))


class CleanTextTests(SimpleTestCase):
    def test_null_becomes_empty_never_the_string_none(self):
        self.assertEqual(clean_text(None), "")

    def test_values_are_trimmed_and_stringified(self):
        self.assertEqual(clean_text("  Bags "), "Bags")
        self.assertEqual(clean_text(5), "5")
        self.assertEqual(clean_text(""), "")
