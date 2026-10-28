"""GST order-snapshot tests: new orders freeze GST; existing orders are read from the snapshot, never from today's settings.

Evidence level: UNIT / REGRESSION with the SQL helper layer patched. The snapshot columns are not applied to any
database yet (migration awaiting approval), so `snapshot_available` is patched to simulate both deployment states.
"""
from contextlib import ExitStack, nullcontext
from decimal import Decimal
from unittest import mock

from django.test import RequestFactory, SimpleTestCase, override_settings

from legacy_api import views_finance, views_orders
from legacy_api.tests_auth import BEARER, authed, body_of, post
from legacydb import order_gst_snapshot as snap
from legacydb.order_gst_snapshot import SOURCE_LEGACY, SOURCE_PARTIAL, SOURCE_PRE_MIGRATION, SOURCE_SNAPSHOT

rf = RequestFactory()


def snapshot_columns(present):
    stack = ExitStack()
    stack.enter_context(mock.patch.object(snap, "snapshot_available", return_value=present))
    stack.enter_context(mock.patch.object(views_orders, "snapshot_available", return_value=present))
    return stack


def must_not_recalc(_row):
    raise AssertionError("current product/variant settings must not be consulted for a snapshot-era order")


class SnapshotRuleTests(SimpleTestCase):
    def test_snapshot_era_order_uses_stored_amounts_and_never_recalculates(self):
        with snapshot_columns(True):
            total, source = snap.order_gst([{"snap_gst_amount": Decimal("18.00")}, {"snap_gst_amount": Decimal("0.00")}], must_not_recalc)
        self.assertEqual((total, source), (Decimal("18.00"), SOURCE_SNAPSHOT))

    def test_legacy_orders_are_not_invented_or_recomputed(self):
        with snapshot_columns(True):
            total, source = snap.order_gst([{"snap_gst_amount": None}], must_not_recalc)
        self.assertEqual((total, source), (Decimal("0.00"), SOURCE_LEGACY))

    def test_partial_snapshot_is_reported_explicitly(self):
        with snapshot_columns(True):
            total, source = snap.order_gst([{"snap_gst_amount": Decimal("5.00")}, {"snap_gst_amount": None}], must_not_recalc)
        self.assertEqual((total, source), (Decimal("5.00"), SOURCE_PARTIAL))

    def test_before_migration_behaviour_is_unchanged(self):
        with snapshot_columns(False):
            total, source = snap.order_gst([{"x": 1}], lambda r: Decimal("7.00"))
        self.assertEqual((total, source), (Decimal("7.00"), SOURCE_PRE_MIGRATION))

    def test_line_snapshot_comes_from_the_central_rules(self):
        enabled = snap.line_snapshot(quantity=2, product_gst_applicable="Y", customer_gst_percentage=5, configured_amount=20)
        self.assertEqual((enabled["gst_applicable"], enabled["gst_percentage"], enabled["gst_unit_amount"], enabled["gst_amount"]),
                         ("Y", Decimal("5"), Decimal("20"), Decimal("2.00")))
        disabled = snap.line_snapshot(quantity=2, product_gst_applicable="N", customer_gst_percentage=18, configured_amount=9)
        self.assertEqual((disabled["gst_applicable"], disabled["gst_percentage"], disabled["gst_unit_amount"], disabled["gst_amount"]),
                         ("N", Decimal("0.00"), Decimal("0.00"), Decimal("0.00")))


class NewOrderSnapshotTests(SimpleTestCase):
    user = {"fullname": "T", "phone": "1", "address": "a", "email": "t@example.invalid",
            "delivery_charges": Decimal("0.00"), "vip_discount": "N", "vip_percentage": Decimal("0"),
            "gst_percentage": Decimal("5")}
    # Selling price 100 vs configured GST amount 20: 20 x 2 x 5% = 2.00 (price-based would be 10.00 or 36.00).
    item = {"product_id": 15, "variant_id": 0, "qty": 2, "product_name": "Pct", "has_disc": 0, "discount_percent": 0,
            "discount_value": 0, "product_discount": 0, "product_gst_applicable": "Y",
            "gst_price": Decimal("20.00"), "variant_gst": "N", "variant_name": "", "price": Decimal("100.00"), "stock_qty": 1}

    def setUp(self):
        patcher = mock.patch.object(views_orders, "apply_order_credit", return_value=None)  # covered in adminapi.tests_credit_placement
        patcher.start()
        self.addCleanup(patcher.stop)

    def place(self, item, present, forged=None, user=None):
        items = item if isinstance(item, list) else [item]
        request = rf.post("/api/order_post", data=forged or {}, **BEARER)
        with authed(), snapshot_columns(present), override_settings(STOKIT_MIN_ORDER_VALUE=Decimal("0.00")), \
                mock.patch.object(views_orders.transaction, "atomic", return_value=nullcontext()), \
                mock.patch.object(views_orders, "fetchone", return_value=user or self.user), \
                mock.patch.object(views_orders, "fetchall", return_value=items), \
                mock.patch.object(views_orders, "_insert_checkout_with_unique_id", return_value=500), \
                mock.patch.object(views_orders, "execute") as execute:
            response = views_orders.order_post(request)
        inserts = [c for c in execute.call_args_list if "INSERT INTO zg_order_items" in c.args[0]]
        return response, inserts

    def variant_item(self, variant_id, amount, price, qty=1, **extra):
        return {**self.item, "product_id": 16, "variant_id": variant_id, "variant_name": f"V{variant_id}", "qty": qty,
                "variant_gst": "Y", "gst_price": Decimal(str(amount)), "price": Decimal(str(price)), "stock_qty": 50, **extra}

    def test_new_order_stores_the_calculated_snapshot_once_columns_exist(self):
        response, inserts = self.place(self.item, True)
        self.assertEqual(response.status_code, 200)
        sql, params = inserts[0].args
        self.assertIn("gst_amount", sql)
        self.assertIn("gst_snapshot_at", sql)
        self.assertEqual(sql.count("%s"), len(params))
        # applicable, customer percentage used, configured unit amount used, calculated line GST
        self.assertEqual(params[-4:], ["Y", Decimal("5"), Decimal("20.00"), Decimal("2.00")])

    def test_order_placement_matches_the_business_example_total_of_20(self):
        items = [self.variant_item(201, 120, 999), self.variant_item(202, 135, 50), self.variant_item(203, 145, 1000)]
        response, inserts = self.place(items, True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c.args[1][-1] for c in inserts], [Decimal("6.00"), Decimal("6.75"), Decimal("7.25")])
        self.assertEqual(sum(c.args[1][-1] for c in inserts), Decimal("20.00"))

    def test_order_gst_agrees_with_the_cart_and_checkout_for_the_same_data(self):
        from legacy_api.tests_cart import FakeCartDb, add, cart_env, fetch_cart
        db = FakeCartDb()  # same 5% customer, same variants 201/202/203
        with cart_env(db):
            add(16, (201, 1), (202, 1), (203, 1))
            cart_gst = fetch_cart()["cart_items"]["final_summary"]["GST"]
        items = [self.variant_item(201, 120, 999), self.variant_item(202, 135, 50), self.variant_item(203, 145, 1000)]
        _, inserts = self.place(items, True)
        self.assertEqual(float(sum(c.args[1][-1] for c in inserts)), cart_gst)

    def test_quantity_two_doubles_the_order_line_gst(self):
        _, inserts = self.place(self.variant_item(201, 120, 999, qty=2), True)
        self.assertEqual(inserts[0].args[1][-1], Decimal("12.00"))

    def test_order_uses_the_customers_saved_percentage(self):
        for pct, expected in ((Decimal("5"), Decimal("2.00")), (Decimal("10"), Decimal("4.00")), (Decimal("12.5"), Decimal("5.00"))):
            _, inserts = self.place(self.item, True, user={**self.user, "gst_percentage": pct})
            self.assertEqual(inserts[0].args[1][-4:], ["Y", pct, Decimal("20.00"), expected])

    def test_missing_or_zero_customer_percentage_uses_configured_amount_and_invalid_rates_store_zero_gst(self):
        for pct in (None, "", 0, Decimal("0"), Decimal("0.00")):
            _, inserts = self.place(self.item, True, user={**self.user, "gst_percentage": pct})
            self.assertEqual(inserts[0].args[1][-1], Decimal("40.00"), repr(pct))
            self.assertEqual(inserts[0].args[1][-3], Decimal("0.00"), repr(pct))  # no customer rate was recorded
        for pct in (-5, 101, "abc", "NaN", "Infinity"):
            _, inserts = self.place(self.item, True, user={**self.user, "gst_percentage": pct})
            self.assertEqual(inserts[0].args[1][-1], Decimal("0.00"), repr(pct))
            self.assertEqual(inserts[0].args[1][-3], Decimal("0.00"), repr(pct))
    def test_disabled_gst_is_stored_as_zero_despite_stale_amounts(self):
        response, inserts = self.place({**self.item, "product_gst_applicable": "N"}, True)
        self.assertEqual(inserts[0].args[1][-4:], ["N", Decimal("0.00"), Decimal("0.00"), Decimal("0.00")])

    def test_variant_disabled_stores_zero_for_that_variant_only(self):
        items = [self.variant_item(201, 120, 999), self.variant_item(202, 135, 50, variant_gst="N")]
        _, inserts = self.place(items, True)
        self.assertEqual([c.args[1][-1] for c in inserts], [Decimal("6.00"), Decimal("0.00")])

    def test_forged_client_gst_cannot_reach_the_snapshot(self):
        forged = {"gst_amount": "999", "gst": "999", "gst_percentage": "28", "customer_gst_percentage": "28"}
        _, inserts = self.place({**self.item, "product_gst_applicable": "N"}, True, forged=forged)
        self.assertEqual(inserts[0].args[1][-1], Decimal("0.00"))

    def test_forged_client_percentage_cannot_change_an_enabled_line(self):
        forged = {"gst_percentage": "28", "customer_gst_percentage": "28", "gst_amount": "999"}
        _, inserts = self.place(self.item, True, forged=forged)
        self.assertEqual(inserts[0].args[1][-4:], ["Y", Decimal("5"), Decimal("20.00"), Decimal("2.00")])

    def test_before_migration_the_insert_is_exactly_the_legacy_statement(self):
        response, inserts = self.place(self.item, False)
        self.assertEqual(response.status_code, 200)
        sql, params = inserts[0].args
        self.assertNotIn("gst_", sql)
        self.assertEqual(len(params), 9)


class HistoricalDisplayTests(SimpleTestCase):
    def row(self, **extra):
        base = {"order_id": 9, "order_date": "2026-10-01", "status": "Placed", "total_amount": Decimal("200.00"),
                "full_name": "A", "phone": "1", "address": "a", "city": "c", "state": "s", "postal_code": "1",
                "country": "IN", "payment_method": "online", "shipping_charge": 0, "cod_charge": 0, "item_id": 1,
                "product_id": 15, "variant_id": 0, "product_name": "Pct", "variant_name": "", "quantity": 2,
                "price": Decimal("100.00"), "discount": Decimal("0"), "total_price": Decimal("200.00"),
                "snap_gst_amount": Decimal("36.00"), "product_gst_applicable": "N",
                "configured_gst_amount": Decimal("0"), "variant_gst": "N", "image_path": None}
        base.update(extra)
        return base

    def details(self, rows, present=True, customer_pct=0):
        def one(sql, params=()):
            if "FROM users" in sql:
                return {"email": "alice@example.invalid", "gst_percentage": customer_pct, "delivery_charges": 0,
                        "vip_discount": None, "vip_percentage": 0}
            return None
        request = post("/api/order_details", {"order_id": 9}, **BEARER)
        with authed(), snapshot_columns(present), mock.patch.object(views_orders, "fetchone", side_effect=one), \
                mock.patch.object(views_orders, "fetchall", return_value=rows):
            return body_of(views_orders.order_details(request))

    def test_old_order_gst_ignores_current_product_settings(self):
        # Today the product is GST-disabled, but the order was placed with 36.00 GST.
        pricing = self.details([self.row()])["pricing"]
        self.assertEqual((pricing["gst_amount"], pricing["gst_source"]), (36.0, "snapshot"))

    def test_changing_product_gst_configuration_does_not_change_old_order(self):
        before = self.details([self.row()])["pricing"]
        after = self.details([self.row(product_gst_applicable="Y", configured_gst_amount=Decimal("99"))])["pricing"]
        self.assertEqual((before["gst_amount"], before["total_with_gst"]), (after["gst_amount"], after["total_with_gst"]))
        self.assertEqual(self.details([self.row()])["order"]["total_amount"], 200.0)

    def test_changing_the_customers_gst_percentage_does_not_change_old_order(self):
        before = self.details([self.row(snap_gst_amount=Decimal("2.00"))], customer_pct=5)["pricing"]
        after = self.details([self.row(snap_gst_amount=Decimal("2.00"))], customer_pct=28)["pricing"]
        self.assertEqual(before["gst_amount"], 2.0)
        self.assertEqual((before["gst_amount"], before["total_with_gst"]), (after["gst_amount"], after["total_with_gst"]))
        self.assertEqual(before["gst_source"], "snapshot")

    def test_legacy_order_is_flagged_not_recomputed_from_current_settings(self):
        pricing = self.details([self.row(snap_gst_amount=None, product_gst_applicable="Y",
                                         configured_gst_amount=Decimal("20"))], customer_pct=5)["pricing"]
        self.assertEqual((pricing["gst_amount"], pricing["gst_source"]), (0.0, "legacy_unrecorded"))

    def test_before_the_snapshot_columns_exist_details_use_the_shared_rule(self):
        # Pre-migration only: configured amount 20 x qty 2 x the customer's saved 5% / 100 = 2.00 (price 100 ignored).
        pricing = self.details([self.row(snap_gst_amount=None, product_gst_applicable="Y",
                                         configured_gst_amount=Decimal("20"))], present=False, customer_pct=5)["pricing"]
        self.assertEqual((pricing["gst_amount"], pricing["gst_source"]), (2.0, "current_settings_pre_snapshot"))

    def test_flutter_pricing_keys_remain_present(self):
        pricing = self.details([self.row()])["pricing"]
        for key in ("gst_percentage", "gst_amount", "total_with_gst", "delivery_charge", "grand_total", "subtotal",
                    "customer_billed_percentage", "gst_source"):
            self.assertIn(key, pricing)

    def test_statement_gst_reads_the_snapshot(self):
        with snapshot_columns(True), mock.patch.object(views_finance, "fetchall", return_value=[
                {"product_id": 15, "variant_id": 0, "quantity": 2, "price": Decimal("100"), "snap_gst_amount": Decimal("36.00"),
                 "product_gst_applicable": "N", "configured_amount": 0, "variant_gst": "N"}]):
            total, source = views_finance._order_gst(9, 28)
        self.assertEqual((total, source), (Decimal("36.00"), SOURCE_SNAPSHOT))

    def test_statement_before_migration_uses_configured_amount_when_customer_rate_is_blank(self):
        rows = [{"product_id": 16, "variant_id": 201, "quantity": 1, "price": Decimal("999"), "snap_gst_amount": None,
                 "product_gst_applicable": "Y", "configured_amount": Decimal("120"), "variant_gst": "Y"}]
        with snapshot_columns(False), mock.patch.object(views_finance, "fetchall", return_value=rows):
            total, source = views_finance._order_gst(9, Decimal("5"))
            blank_total, _ = views_finance._order_gst(9, None)
        self.assertEqual((total, source), (Decimal("6.00"), SOURCE_PRE_MIGRATION))
        self.assertEqual(blank_total, Decimal("120.00"))


from legacy_api.cart_discount_testing import module_fixtures
setUpModule, tearDownModule = module_fixtures()  # no saved cart-discount row: promotion unconfigured, no DB access
