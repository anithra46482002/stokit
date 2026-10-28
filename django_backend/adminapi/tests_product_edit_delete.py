"""Database-free regression tests for product Edit (PATCH) and Delete.

The destructive paths run on mocks only; the real-database behaviour is checked by
scripts/verify_product_variant_crud_rollback.py inside a transaction that is always rolled back.
"""
from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db import IntegrityError
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from adminapi import crud


_DEFAULT = object()


def _user(role="ADMIN"):
    return SimpleNamespace(is_authenticated=True, role=role, pk=1, principal_type="ADMIN")


def _product(pid=4, **extra):
    row = SimpleNamespace(
        product_id=pid, product_name="bangless", code="1000022", subtitle="", brand="", set_contains="[]",
        product_price=Decimal("300"), mrp=Decimal("300"), product_discount=Decimal("0"), category_id=1,
        subcategory_id=None, no_discount_banner="N", disable_variants="N", moq=1, view="1", highlight=False,
        stock="In Stock", color="", gst_applicable="N", gst_percentage=Decimal("0"), gst_price=Decimal("0"),
        product_description="", product_keywords="", product_details="", additional_details="",
        save=MagicMock(), delete=MagicMock())
    for key, value in extra.items():
        setattr(row, key, value)
    return row


def _call(method, payload=None, query="", user="ADMIN"):
    factory = APIRequestFactory()
    path = "/admin-api/products" + query
    request = getattr(factory, method)(path, payload, format="json") if payload is not None else getattr(factory, method)(path)
    if user:
        force_authenticate(request, user=_user(user))
    return crud.ProductCRUDView.as_view()(request)


class ProductEditTests(SimpleTestCase):
    def _patch(self, payload, row=_DEFAULT, **kwargs):
        row = _product() if row is _DEFAULT else row
        with patch.object(crud.Product.objects, "filter") as products:
            products.return_value.first.return_value = row
            response = _call("patch", payload, **kwargs)
        return response, row

    def test_valid_edit_saves_only_the_columns_sent_and_returns_the_saved_values(self):
        response, row = self._patch({"id": 4, "name": "glass bangles", "price": 320})
        self.assertEqual(response.status_code, 200)
        row.save.assert_called_once_with(update_fields=["product_name", "product_price"])
        self.assertEqual((response.data["id"], response.data["name"], response.data["price"]), (4, "glass bangles", "320"))

    def test_the_exact_payload_the_edit_dialog_sends_is_accepted(self):
        payload = {"id": 4, "name": "bangless", "code": "1000022", "price": 300, "mrp": 300, "discount": 0, "no_discount_banner": "Y",
                   "disable_variants": "N", "minimum_buying_count": 6, "minimum_buying_quantity": 6, "category_id": 1, "subcategory_id": None,
                   "visible": "0", "highlight": False, "stock": "In Stock", "gst_applicable": "N", "gst_percentage": 0, "gst_price": 0,
                   "description": "", "keywords": "", "subtitle": "glass Bangles", "brand": "aaa", "set_contains": []}
        with patch.object(crud.Category.objects, "filter") as categories:
            categories.return_value.exists.return_value = True
            response, row = self._patch(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(row.moq, 6)
        self.assertEqual(row.view, "0")

    def test_edit_never_touches_variants_images_or_order_history(self):
        with patch.object(crud.Variant.objects, "filter") as variants, patch.object(crud.ProductImage.objects, "filter") as images, \
                patch.object(crud.OrderItem.objects, "filter") as orders:
            response, _ = self._patch({"id": 4, "name": "renamed"})
        self.assertEqual(response.status_code, 200)
        variants.assert_not_called(); images.assert_not_called(); orders.assert_not_called()

    def test_invalid_input_is_rejected_without_saving(self):
        for payload in ({"id": 4, "price": "abc"}, {"id": 4, "price": -1}, {"id": 4, "name": "  "}, {"id": 4, "code": ""},
                        {"id": 4, "disable_variants": "maybe"}, {"id": 4, "minimum_buying_count": 0}, {"id": 4, "gst_percentage": 101}):
            response, row = self._patch(payload)
            self.assertEqual(response.status_code, 400, payload)
            row.save.assert_not_called()

    def test_missing_product_is_404_and_bad_id_is_400(self):
        response, _ = self._patch({"id": 99}, row=None)
        self.assertEqual(response.status_code, 404)
        with patch.object(crud.Product.objects, "filter") as products:
            response = _call("patch", {"id": "abc"})
            products.assert_not_called()
        self.assertEqual(response.status_code, 400)

    def test_database_failure_is_reported_not_swallowed(self):
        row = _product(save=MagicMock(side_effect=RuntimeError("schema mismatch")))
        cursor = MagicMock()
        cursor.__enter__.return_value.execute.side_effect = RuntimeError("sql down")
        with patch.object(crud, "connection", MagicMock(cursor=MagicMock(return_value=cursor))), patch.object(crud, "log_db_error") as log:
            response, _ = self._patch({"id": 4, "name": "x"}, row=row)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("name", response.data)  # an error body, never a success payload
        log.assert_called_once()

    def test_unauthenticated_and_unprivileged_edits_are_rejected(self):
        for user in (None, "WAREHOUSE_STAFF", "SALESMAN", "DELIVERY_BOY"):
            with patch.object(crud.Product.objects, "filter") as products:
                response = _call("patch", {"id": 4, "name": "x"}, user=user)
                products.assert_not_called()
            self.assertIn(response.status_code, (401, 403), user)


class ProductDeleteTests(SimpleTestCase):
    """Runs the real view with the database layer mocked; asserts what is (not) deleted."""

    def _delete(self, row, *, orders=False, variant_orders=False, variant_ids=(11, 12), cart=0, stock=False,
                cart_error=None, delete_error=None, user="ADMIN", query="?id=4"):
        select = MagicMock()
        select.return_value.filter.return_value.first.return_value = row
        order_filter = MagicMock(side_effect=lambda **kw: MagicMock(exists=lambda: variant_orders if "variant_id__in" in kw else orders))
        variant_filter = MagicMock()
        variant_filter.return_value.values_list.return_value = list(variant_ids)
        image_filter = MagicMock()
        cursor = MagicMock()
        cursor.__enter__.return_value.fetchone.return_value = (cart,)
        if cart_error:
            cursor.__enter__.return_value.execute.side_effect = cart_error
        if delete_error:
            variant_filter.return_value.delete.side_effect = delete_error
        self.mocks = SimpleNamespace(variant=variant_filter, image=image_filter, cursor=cursor.__enter__.return_value, select=select)
        patches = (
            patch.object(crud.transaction, "atomic", return_value=nullcontext()),
            patch.object(crud.Product.objects, "select_for_update", select),
            patch.object(crud.OrderItem.objects, "filter", order_filter),
            patch.object(crud.Variant.objects, "filter", variant_filter),
            patch.object(crud.ProductImage.objects, "filter", image_filter),
            patch.object(crud.StockLog.objects, "filter", return_value=MagicMock(exists=lambda: stock)),
            patch.object(crud, "connection", MagicMock(cursor=MagicMock(return_value=cursor))),
            patch.object(crud, "log_db_error"),
        )
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return _call("delete", query=query, user=user)

    def test_unreferenced_product_is_deleted_with_its_owned_children_only(self):
        row = _product()
        response = self._delete(row)
        self.assertEqual(response.status_code, 204)
        row.delete.assert_called_once_with()
        self.mocks.variant.assert_any_call(product_id=4)
        self.mocks.image.assert_called_once_with(product_id=4)
        statements = [call.args[0] for call in self.mocks.cursor.execute.call_args_list]
        self.assertTrue(any("DELETE FROM zg_discount_banners" in s for s in statements), "banner rows (real FK) must be removed first")
        self.assertTrue(any("DELETE FROM zg_favorites" in s for s in statements))
        self.assertFalse(any("zg_order" in s for s in statements), "order history is never touched")

    def test_product_with_order_history_is_deleted_and_order_rows_are_not_touched(self):
        row = _product()
        response = self._delete(row, orders=True)
        self.assertEqual(response.status_code, 204)
        row.delete.assert_called_once_with()
        statements = [call.args[0] for call in self.mocks.cursor.execute.call_args_list]
        self.assertFalse(any('zg_order' in s for s in statements), 'order history is never touched')

    def test_product_whose_variant_is_in_order_history_can_be_deleted(self):
        row = _product()
        response = self._delete(row, variant_orders=True)
        self.assertEqual(response.status_code, 204)
        row.delete.assert_called_once_with()

    def test_product_in_customer_carts_is_deleted_and_cart_rows_are_cleaned(self):
        row = _product()
        response = self._delete(row, cart=3)
        self.assertEqual(response.status_code, 204)
        row.delete.assert_called_once_with()
        statements = [call.args[0] for call in self.mocks.cursor.execute.call_args_list]
        self.assertTrue(any('DELETE FROM a_cart' in s for s in statements))

    def test_product_with_inventory_history_can_be_deleted_without_deleting_stock_history(self):
        row = _product()
        response = self._delete(row, stock=True)
        self.assertEqual(response.status_code, 204)
        row.delete.assert_called_once_with()

    def test_cart_cleanup_database_error_fails_without_fake_success(self):
        row = _product()
        response = self._delete(row, cart_error=RuntimeError('a_cart missing'))
        self.assertEqual(response.status_code, 500)
        row.delete.assert_not_called()

    def test_database_failure_is_a_500_not_a_fake_success(self):
        row = _product()
        response = self._delete(row, delete_error=RuntimeError("db down"))
        self.assertEqual(response.status_code, 500)
        self.assertIn("No partial deletion", response.data["detail"])
        row.delete.assert_not_called()

    def test_constraint_violation_is_reported_as_409(self):
        row = _product(delete=MagicMock(side_effect=IntegrityError("fk")))
        response = self._delete(row)
        self.assertEqual(response.status_code, 409)

    def test_missing_product_is_404_and_a_repeat_deletes_nothing(self):
        for _ in range(2):
            response = self._delete(None)
            self.assertEqual(response.status_code, 404)
            self.mocks.variant.return_value.delete.assert_not_called()

    def test_missing_or_invalid_id_is_400_and_touches_no_row(self):
        for query in ("", "?id=abc", "?id="):
            response = self._delete(_product(), query=query)
            self.assertEqual(response.status_code, 400, query)
            self.mocks.select.assert_not_called()

    def test_unauthenticated_and_unprivileged_deletes_are_rejected(self):
        for user in (None, "WAREHOUSE_STAFF", "SALESMAN", "DELIVERY_BOY"):
            row = _product()
            response = self._delete(row, user=user)
            self.assertIn(response.status_code, (401, 403), user)
            self.mocks.select.assert_not_called(); row.delete.assert_not_called()
