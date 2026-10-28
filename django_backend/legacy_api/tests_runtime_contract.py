"""Database-FREE runtime contract tests: the real view functions are executed (request -> JSON response)
with only the SQL helper layer replaced by test doubles. They prove exact legacy key names/status codes
of the code paths exercised; they do NOT prove behaviour against MariaDB data (see docs)."""
import json
from contextlib import nullcontext
from decimal import Decimal
from unittest import mock

from django.test import RequestFactory, SimpleTestCase

from legacy_api import views_catalog, views_remaining

USER = {"id": 7, "username": "contract-user", "email": "c@example.invalid", "fullname": "C", "phone": "1", "address": "a"}
AUTH = {"HTTP_AUTHORIZATION": "Bearer " + "a" * 64}


def _authed():
    return mock.patch("accounts.services.authenticate_token", return_value=(object(), USER))


class LegacyKeySpellingRuntimeTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_product_api_returns_misspelled_discound_banners_key(self):
        product = {
            "product_id": 5, "mrp": Decimal("120.00"), "product_name": "P", "disable_variants": "N",
            "subtitle": None, "brand": None, "youtube_link": None, "share_image": None,
            "product_details": None, "additional_details": None, "product_description": "Admin description", "product_keywords": "keyword one, keyword two", "product_price": Decimal("100.00"),
            "product_discount": None, "discount_value": Decimal("0.00"), "discount_percent": Decimal("0.00"),
            "no_discount_banner": "N", "moq": 1, "set_of": 1, "quantity_selected": 0,
            "set_contains": None, "gst_applicable": "N", "gst_percentage": Decimal("0.00"), "gst_price": Decimal("0.00"),
        }
        request = self.rf.post("/api/product-api", data=json.dumps({"product_id": 5}),
                               content_type="application/json", **AUTH)
        with _authed(), \
                mock.patch.object(views_catalog, "fetchone", side_effect=[{"category_id": 3}, product, None, None]), \
                mock.patch.object(views_catalog, "fetchall",
                                  side_effect=[[{"image_path": "uploads/a.webp"}], [{"image_path": "uploads/b.webp"}], []]), \
                mock.patch.object(views_catalog, "execute", return_value=1):
            response = views_catalog.product_api(request)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["product"]["product_details"], "Admin description")
        self.assertEqual(body["product"]["additional_details"], "keyword one, keyword two")
        self.assertIn("discound_banners", body["product"])
        self.assertNotIn("discount_banners", body["product"])
        self.assertEqual(len(body["product"]["discound_banners"]), 1)
        self.assertTrue(body["product"]["discound_banners"][0].endswith("uploads/b.webp"))

    def test_save_check_returns_misspelled_oder_id_key_and_exact_key_set(self):
        request = self.rf.post("/api/saveCheck", data=json.dumps({"cart": [1]}),
                               content_type="application/json", **AUTH)
        with _authed(), \
                mock.patch.object(views_remaining.transaction, "atomic", return_value=nullcontext()), \
                mock.patch.object(views_remaining.CheckoutPayload.objects, "create"):
            response = views_remaining.save_check(request)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(set(body), {"success", "message", "file", "oder_id"})
        self.assertIs(body["success"], True)
        self.assertIsInstance(body["oder_id"], int)


class LegacyAuthGateRuntimeTests(SimpleTestCase):
    def test_missing_token_returns_exact_legacy_401_body_without_touching_database(self):
        for name in ("product_api", "search", "highlights"):
            with self.subTest(view=name):
                response = getattr(views_catalog, name)(RequestFactory().get("/api/x"))
                self.assertEqual(response.status_code, 401)
                self.assertEqual(json.loads(response.content), {"status": "session_expired", "message": "Session expired"})

class FlutterSearchPostContractTests(SimpleTestCase):
    """Database-free coverage for Flutter POST filters while preserving PHP GET behavior."""

    def setUp(self):
        self.rf = RequestFactory()

    def test_flutter_post_applies_price_bounds_sort_and_pagination(self):
        request = self.rf.post(
            "/api/search",
            data=json.dumps({"min_price": 100, "max_price": 500, "sort_by": "price_asc", "skip": 5, "limit": 10}),
            content_type="application/json",
            **AUTH,
        )
        row = {"id": 9, "product_name": "Example", "price": Decimal("120.00"),
               "discount": Decimal("5.00"), "category_name": "Tools", "image_url": "uploads/item.webp"}
        with _authed(), \
             mock.patch.object(views_catalog, "fetchone", return_value={"total": 1}) as count_mock, \
             mock.patch.object(views_catalog, "fetchall", return_value=[row]) as rows_mock:
            response = views_catalog.search(request)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual((body["total"], body["skip"], body["limit"]), (1, 5, 10))
        self.assertEqual(body["search"][0]["id"], 9)
        count_sql, count_params = count_mock.call_args.args
        self.assertIn("p.product_price >= %s", count_sql)
        self.assertIn("p.product_price <= %s", count_sql)
        self.assertEqual(count_params, [100.0, 500.0])
        rows_sql, rows_params = rows_mock.call_args.args
        self.assertIn("ORDER BY p.product_price ASC, p.product_id DESC", rows_sql)
        self.assertEqual(rows_params, [100.0, 500.0, 10, 5])

    def test_php_get_search_contract_remains_supported(self):
        request = self.rf.get("/api/search?search=lamp&skip=2&limit=7", **AUTH)
        with _authed(), \
             mock.patch.object(views_catalog, "fetchone", return_value={"total": 0}) as count_mock, \
             mock.patch.object(views_catalog, "fetchall", return_value=[]):
            response = views_catalog.search(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["search"], [])
        sql, params = count_mock.call_args.args
        self.assertIn("p.product_name ILIKE %s", sql)
        self.assertEqual(params, ["%lamp%"])

    def test_flutter_post_rejects_inverted_price_bounds(self):
        request = self.rf.post(
            "/api/search", data=json.dumps({"min_price": 100, "max_price": 50}),
            content_type="application/json", **AUTH,
        )
        with _authed(), mock.patch.object(views_catalog, "fetchone") as count_mock, \
             mock.patch.object(views_catalog, "fetchall") as rows_mock:
            response = views_catalog.search(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)["message"], "min_price cannot exceed max_price")
        count_mock.assert_not_called()
        rows_mock.assert_not_called()

    def test_unsupported_search_method_returns_405_without_sql(self):
        request = self.rf.put("/api/search", data=json.dumps({"min_price": 10}),
                              content_type="application/json", **AUTH)
        with _authed(), mock.patch.object(views_catalog, "fetchone") as count_mock, \
             mock.patch.object(views_catalog, "fetchall") as rows_mock:
            response = views_catalog.search(request)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(json.loads(response.content)["message"], "Method not allowed")
        count_mock.assert_not_called()
        rows_mock.assert_not_called()
