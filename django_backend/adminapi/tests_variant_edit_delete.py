"""Database-free regression tests for product-variant View (GET), Edit (PATCH) and Delete.

The destructive paths run on mocks only; the real-database behaviour is checked by
scripts/verify_variant_flow.py inside a transaction that is always rolled back.
"""
from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db import IntegrityError
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from adminapi import crud


def _user(role="ADMIN"):
    return SimpleNamespace(is_authenticated=True, role=role, pk=1, principal_type="ADMIN")


def _row(variant_id=3, product_id=10, **extra):
    row = SimpleNamespace(
        variant_id=variant_id, product_id=product_id, variant_name="500g", variant_price=Decimal("10"),
        mrp=Decimal("12"), quantity=5, disc="0", gst="N", gst_price=Decimal("0"), minimum_buying_count=1,
        save=MagicMock(), delete=MagicMock())
    for key, value in extra.items():
        setattr(row, key, value)
    return row


def _call(method, payload=None, query="", user="ADMIN"):
    path = "/admin-api/product-variants" + query
    factory = APIRequestFactory()
    request = getattr(factory, method)(path, payload, format="json") if payload is not None else getattr(factory, method)(path)
    if user:
        force_authenticate(request, user=_user(user))
    return crud.VariantCRUDView.as_view()(request)


class VariantEditTests(SimpleTestCase):
    def _patch(self, payload, row=None, **kwargs):
        row = row or _row()
        with patch.object(crud.Variant.objects, "filter") as variants:
            variants.return_value.first.return_value = row
            response = _call("patch", payload, **kwargs)
        return response, row

    def test_valid_edit_saves_only_the_changed_columns_of_that_variant(self):
        response, row = self._patch({"id": 3, "name": "1kg", "quantity": 9})
        self.assertEqual(response.status_code, 200)
        row.save.assert_called_once_with(update_fields=["quantity", "variant_name"])
        self.assertEqual((response.data["id"], response.data["name"], response.data["quantity"]), (3, "1kg", 9))

    def test_success_response_has_the_same_fields_as_get_and_post(self):
        response, _ = self._patch({"id": 3, "name": "1kg"})
        for field in ("id", "product_id", "name", "price", "mrp", "quantity", "discount", "gst", "gst_price", "minimum_buying_count"):
            self.assertIn(field, response.data)

    def test_changing_the_product_is_refused_instead_of_silently_ignored(self):
        response, row = self._patch({"id": 3, "product_id": 99, "name": "x"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("product_id", response.data)
        row.save.assert_not_called()

    def test_resending_the_same_product_id_is_accepted(self):
        response, row = self._patch({"id": 3, "product_id": 10, "name": "x"})
        self.assertEqual(response.status_code, 200)
        row.save.assert_called_once()

    def test_non_numeric_product_id_is_rejected(self):
        response, row = self._patch({"id": 3, "product_id": "abc"})
        self.assertEqual(response.status_code, 400)
        row.save.assert_not_called()

    def test_invalid_input_is_rejected_without_saving(self):
        for payload in ({"id": 3, "name": "  "}, {"id": 3, "quantity": -1}, {"id": 3, "quantity": "1.5"},
                        {"id": 3, "price": "-4"}, {"id": 3, "discount": "abc"}, {"id": 3, "gst": "Q"}):
            response, row = self._patch(payload)
            self.assertEqual(response.status_code, 400, payload)
            row.save.assert_not_called()

    def test_missing_variant_is_404_and_nothing_is_saved(self):
        with patch.object(crud.Variant.objects, "filter") as variants:
            variants.return_value.first.return_value = None
            response = _call("patch", {"id": 999, "name": "x"})
        self.assertEqual(response.status_code, 404)

    def test_missing_or_invalid_id_is_400(self):
        for payload in ({"name": "x"}, {"id": "abc"}, {"id": None}):
            self.assertEqual(_call("patch", payload).status_code, 400, payload)

    def test_database_failure_is_reported_not_swallowed(self):
        row = _row(save=MagicMock(side_effect=IntegrityError("constraint")))
        response, _ = self._patch({"id": 3, "name": "x"}, row=row)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("id", response.data)  # an error body, never a success payload
        row = _row(save=MagicMock(side_effect=RuntimeError("db down")))
        with patch.object(crud, "log_db_error") as log:
            response, _ = self._patch({"id": 3, "name": "x"}, row=row)
        self.assertEqual(response.status_code, 500)
        log.assert_called_once()

    def test_unauthenticated_and_unprivileged_edits_are_rejected(self):
        for user in (None, "WAREHOUSE_STAFF", "SALESMAN", "DELIVERY_BOY"):
            with patch.object(crud.Variant.objects, "filter") as variants:
                response = _call("patch", {"id": 3, "name": "x"}, user=user)
                variants.assert_not_called()
            self.assertIn(response.status_code, (401, 403), user)


class VariantDeleteTests(SimpleTestCase):
    """Runs the real view with the database layer mocked; asserts what is (and is not) touched.

    A variant referenced by order history, customer carts or stock history is now deleted like any other:
    zg_variant has no foreign keys, so the view cleans up carts itself and leaves history rows alone."""

    def _delete(self, row, *, stock=False, cart_error=None, user="ADMIN", query="?id=3", order_error=False, order_history=False):
        select = MagicMock()
        select.return_value.filter.return_value.first.return_value = row
        cursor = MagicMock()
        if cart_error:
            cursor.__enter__.return_value.execute.side_effect = cart_error
        order_items = MagicMock()
        order_items.filter.return_value.exists.return_value = order_history
        if order_error:
            order_items.filter.side_effect = AssertionError("order history must not be queried or changed")
        stock_log = MagicMock()
        stock_log.filter.return_value.exists.return_value = stock
        self.cursor, self.order_items, self.stock_log = cursor.__enter__.return_value, order_items, stock_log
        patches = (
            patch.object(crud.transaction, "atomic", return_value=nullcontext()),
            patch.object(crud.Variant.objects, "select_for_update", select),
            patch.object(crud.OrderItem, "objects", order_items),
            patch.object(crud.StockLog, "objects", stock_log),
            patch.object(crud, "connection", MagicMock(cursor=MagicMock(return_value=cursor))),
            patch.object(crud, "log_db_error"),
        )
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return _call("delete", query=query, user=user), select

    def test_unreferenced_variant_is_deleted_by_deleting_only_that_row(self):
        row = _row()
        response, select = self._delete(row)
        self.assertEqual(response.status_code, 204)
        row.delete.assert_called_once_with()  # the single locked instance, never a queryset/bulk delete
        select.return_value.filter.assert_called_once_with(pk=3)
        self.stock_log.create.assert_not_called()  # no stock history -> no audit entry needed

    def test_parent_product_and_sibling_variants_are_never_queried_for_deletion(self):
        with patch.object(crud.Product.objects, "filter") as products, patch.object(crud.Product.objects, "get") as product_get:
            response, _ = self._delete(_row())
        self.assertEqual(response.status_code, 204)
        products.assert_not_called()
        product_get.assert_not_called()

    def test_variant_in_customer_carts_is_deleted_and_only_its_cart_lines_are_removed(self):
        row = _row()
        response, _ = self._delete(row)
        self.assertEqual(response.status_code, 204)
        sql, params = self.cursor.execute.call_args.args
        self.assertEqual(" ".join(sql.split()), "DELETE FROM a_cart WHERE variant_id=%s")
        self.assertEqual(params, [3])
        row.delete.assert_called_once_with()

    def test_cart_cleanup_and_variant_delete_share_one_transaction_and_cart_goes_first(self):
        order = []
        row = _row(delete=MagicMock(side_effect=lambda: order.append("variant")))
        atomic = MagicMock()
        atomic.return_value.__enter__.side_effect = lambda: order.append("begin")
        atomic.return_value.__exit__.side_effect = lambda *a: order.append("end") or False
        with patch.object(crud.transaction, "atomic", atomic):
            response, _ = self._delete_inside_existing_atomic(row, order)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(order, ["begin", "cart", "variant", "end"])

    def _delete_inside_existing_atomic(self, row, order):
        select = MagicMock()
        select.return_value.filter.return_value.first.return_value = row
        cursor = MagicMock()
        cursor.__enter__.return_value.execute.side_effect = lambda *a, **k: order.append('cart')
        stock_log = MagicMock()
        stock_log.filter.return_value.exists.return_value = False
        with patch.object(crud.transaction, 'atomic') as atomic, patch.object(crud.Variant.objects, 'select_for_update', select), patch.object(crud.OrderItem, 'objects') as order_items, patch.object(crud.StockLog, 'objects', stock_log), patch.object(crud, 'connection', MagicMock(cursor=MagicMock(return_value=cursor))), patch.object(crud, 'log_db_error'):
            atomic.return_value.__enter__.side_effect = lambda: order.append('begin')
            atomic.return_value.__exit__.side_effect = lambda *a: order.append('end') or False
            order_items.filter.side_effect = AssertionError('order history must not be queried during delete')
            response = _call('delete', query='?id=3')
        return response, select

    def test_variant_with_order_history_can_be_deleted_by_admin(self):
        row = _row()
        response, _ = self._delete(row, order_history=True)
        self.assertEqual(response.status_code, 204)
        row.delete.assert_called_once_with()
    def test_a_failed_cart_cleanup_rolls_back_the_whole_delete_with_a_500(self):
        row = _row()
        with patch.object(crud, "log_db_error") as log:
            response, _ = self._delete(row, cart_error=RuntimeError("a_cart missing"))
        self.assertEqual(response.status_code, 500)
        self.assertIn("Nothing was removed", response.data["detail"])
        row.delete.assert_not_called()

    def test_database_failure_during_delete_is_a_500_not_a_fake_success(self):
        row = _row(delete=MagicMock(side_effect=RuntimeError("db down")))
        response, _ = self._delete(row)
        self.assertEqual(response.status_code, 500)
        self.assertIn("Nothing was removed", response.data["detail"])

    def test_cart_only_and_stock_only_variants_remain_deletable(self):
        for stock in (False, True):
            response, _ = self._delete(_row(), stock=stock)
            self.assertEqual(response.status_code, 204)
        self.assertFalse(hasattr(crud.VariantCRUDView, "_delete_blocker"))
        self.assertFalse(hasattr(crud.VariantCRUDView, "_DependencyCheckFailed"))

    def test_missing_variant_is_404_and_repeating_a_delete_cannot_delete_anything_else(self):
        for _ in range(2):  # second request finds nothing; it must not fall through to another row
            response, select = self._delete(None)
            self.assertEqual(response.status_code, 404)
            select.return_value.filter.assert_called_once_with(pk=3)
            self.cursor.execute.assert_not_called()  # nothing is cleaned up for a variant that is not there

    def test_missing_or_invalid_id_is_400_and_touches_no_row(self):
        for query in ("", "?id=abc", "?id="):
            response, select = self._delete(_row(), query=query)
            self.assertEqual(response.status_code, 400, query)
            select.assert_not_called()

    def test_unauthenticated_and_unprivileged_deletes_are_rejected(self):
        for user in (None, "WAREHOUSE_STAFF", "SALESMAN", "DELIVERY_BOY"):
            row = _row()
            response, select = self._delete(row, user=user)
            self.assertIn(response.status_code, (401, 403), user)
            select.assert_not_called()
            row.delete.assert_not_called()


class VariantViewTests(SimpleTestCase):
    """GET product-variants?id=N returns the saved record itself."""

    def _get(self, row, query="?id=3", names=None, user="ADMIN"):
        with patch.object(crud.Variant.objects, "filter") as variants, \
                patch.object(crud.VariantCRUDView, "_product_names", return_value=names or {10: "Pens"}), \
                patch.object(crud.VariantCRUDView, "_in_use_map", return_value={3: "order history"}):
            variants.return_value.first.return_value = row
            response = _call("get", query=query, user=user)
        return response, variants

    def test_returns_every_saved_field_for_that_id(self):
        response, variants = self._get(_row(mrp=Decimal("12.50"), gst="Y", gst_price=Decimal("1.50"), minimum_buying_count=4))
        self.assertEqual(response.status_code, 200)
        variants.assert_called_once_with(pk=3)
        self.assertEqual(response.data, {
            "id": 3, "product_id": 10, "product_name": "Pens", "name": "500g", "price": "10", "mrp": "12.50",
            "quantity": 5, "discount": "0", "gst": "Y", "gst_price": "1.50", "minimum_buying_count": 4,
            "in_use": "order history"})

    def test_missing_variant_is_404(self):
        response, _ = self._get(None, query="?id=999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Variant not found")

    def test_invalid_id_is_400_without_a_lookup(self):
        for query in ("?id=abc", "?id=1.5"):
            response, variants = self._get(_row(), query=query)
            self.assertEqual(response.status_code, 400, query)
            variants.assert_not_called()

    def test_unauthenticated_view_is_rejected_and_the_permission_policy_matches_the_list(self):
        response, variants = self._get(_row(), user=None)
        self.assertIn(response.status_code, (401, 403))
        variants.assert_not_called()
        # Reading one record needs exactly the access the variant list already needs (same view, same permission).
        for role in ("ADMIN", "SUPER_ADMIN", "WAREHOUSE_STAFF", "SALESMAN", "DELIVERY_BOY"):
            single, _ = self._get(_row(), user=role)
            with patch.object(crud.Variant.objects, "order_by", return_value=MagicMock(
                    filter=MagicMock(), count=MagicMock(return_value=0), __getitem__=MagicMock(return_value=[]))), \
                    patch.object(crud.VariantCRUDView, "_product_names", return_value={}), \
                    patch.object(crud.VariantCRUDView, "_in_use_map", return_value={}):
                listing = _call("get", user=role)
            self.assertEqual(single.status_code, listing.status_code, role)

    def test_parent_product_name_lookup_failure_only_leaves_the_name_empty(self):
        with patch.object(crud.Product.objects, "filter", side_effect=RuntimeError("db down")), patch.object(crud, "log_db_error") as log:
            self.assertEqual(crud.VariantCRUDView._product_names([10]), {})
        log.assert_called_once()
        self.assertEqual(crud.VariantCRUDView._product_names([None]), {})


class VariantUnsupportedFieldTests(SimpleTestCase):
    def test_unsupported_fields_are_rejected_not_silently_dropped(self):
        row = _row()
        with patch.object(crud.Variant.objects, "filter") as variants:
            variants.return_value.first.return_value = row
            response = _call("patch", {"id": 3, "name": "x", "in_use": "order history", "product_name": "Pens"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("in_use", response.data["detail"])
        self.assertIn("product_name", response.data["detail"])
        row.save.assert_not_called()

    def test_every_editable_form_field_is_accepted_and_saved(self):
        row = _row()
        payload = {"id": 3, "product_id": 10, "name": "1kg", "variant_price": "20", "mrp": "25", "quantity": 7,
                   "discount": "5", "gst": "Y", "gst_price": "1", "minimum_buying_count": 3}
        with patch.object(crud.Variant.objects, "filter") as variants:
            variants.return_value.first.return_value = row
            response = _call("patch", payload)
        self.assertEqual(response.status_code, 200)
        saved = set(row.save.call_args.kwargs["update_fields"])
        self.assertEqual(saved, {"variant_name", "variant_price", "mrp", "quantity", "disc", "gst", "gst_price", "minimum_buying_count"})
        self.assertEqual(row.minimum_buying_count, 3)


class VariantInUseHintTests(SimpleTestCase):
    def _map(self, ids, orders=(), cart=(), stock=()):
        cursor = MagicMock()
        cursor.__enter__.return_value.fetchall.return_value = [(v,) for v in cart]
        with patch.object(crud.OrderItem.objects, "filter", return_value=MagicMock(values_list=lambda *a, **k: list(orders))), \
                patch.object(crud.StockLog.objects, "filter", return_value=MagicMock(values_list=lambda *a, **k: list(stock))), \
                patch.object(crud, "connection", MagicMock(cursor=MagicMock(return_value=cursor))):
            return crud.VariantCRUDView._in_use_map(ids)

    def test_unreferenced_variants_are_absent_and_empty_input_does_no_queries(self):
        self.assertEqual(crud.VariantCRUDView._in_use_map([]), {})
        self.assertEqual(self._map([1, 2]), {})

    def test_every_kind_of_reference_is_reported_in_a_fixed_order(self):
        result = self._map([1, 2, 3, 4], orders=[2, 3], cart=[3, 4], stock=[4])
        self.assertEqual(result, {2: "order history", 3: "order history, customer carts", 4: "customer carts, inventory history"})

    def test_a_failed_lookup_gives_no_hint_and_never_breaks_the_list(self):
        with patch.object(crud.OrderItem.objects, "filter", side_effect=RuntimeError("db down")), patch.object(crud, "log_db_error") as log:
            self.assertEqual(crud.VariantCRUDView._in_use_map([1]), {})
        log.assert_called_once()

    def test_list_rows_carry_in_use_and_keep_the_existing_fields(self):
        rows = [_row(variant_id=1), _row(variant_id=2)]
        queryset = MagicMock()
        queryset.filter.return_value = queryset
        queryset.count.return_value = 2
        queryset.__getitem__.return_value = rows
        with patch.object(crud.Variant.objects, "order_by", return_value=queryset), \
                patch.object(crud.VariantCRUDView, "_product_names", return_value={10: "Pens"}), \
                patch.object(crud.VariantCRUDView, "_in_use_map", return_value={2: "order history"}):
            response = _call("get")
        self.assertEqual(response.status_code, 200)
        first, second = response.data["results"]
        self.assertEqual((first["in_use"], second["in_use"]), ("", "order history"))
        for field in ("id", "product_id", "product_name", "name", "price", "mrp", "quantity", "discount", "gst", "gst_price", "minimum_buying_count"):
            self.assertIn(field, first)
        self.assertEqual(first["product_name"], "Pens")
