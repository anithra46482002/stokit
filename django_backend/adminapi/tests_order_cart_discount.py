"""DB-free regressions: Admin Order Details / list / PATCH / Processing use the PERSISTED fixed cart discount.

The customer cart and order_post apply the fixed amount from the saved Cart Discount Settings and store
zg_checkout.total_amount = items total - that amount. The admin must read that, never re-derive a 10% promotion.
Nothing here touches a database: cursors are fakes and every write is recorded, never executed.
"""
from contextlib import nullcontext
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from adminapi import order_pages as op

ZERO = D("0.00")


def line(total, discount="0", item_id=1, price=None, qty=1):
    return {"item_id": item_id, "product_id": 10 + item_id, "variant_id": 0, "product_name": f"P{item_id}",
            "variant_name": "", "quantity": qty, "price": price if price is not None else total, "discount": discount,
            "total_price": total}


def preview(email, amount, order_id=None):
    amount = D(str(amount))
    return {"monthly_bonus": ZERO, "carried_forward": ZERO, "available_bonus": ZERO, "bonus_applied": ZERO,
            "amount_payable": amount, "remaining_bonus": ZERO, "credit_status": "no_active_allocation"}


class FakeCursor:
    """Answers the exact statements order_pages issues; records every UPDATE/INSERT/DELETE."""

    def __init__(self, state):
        self.state, self.cols, self.rows = state, [], []

    @property
    def description(self):
        return [(c,) for c in self.cols]

    def _set(self, cols, rows):
        self.cols, self.rows = cols, rows

    def execute(self, sql, params=None):
        s, st = " ".join(sql.split()), self.state
        if s.startswith(("UPDATE", "INSERT", "DELETE")):
            st["writes"].append((s, list(params or [])))
            if s.startswith("UPDATE zg_order_items"):
                qty, price, discount, total, item_id, _order = params
                st["items"][item_id] = {**st["items"][item_id], "quantity": qty, "price": price,
                                        "discount": discount, "total_price": total}
            if s.startswith("UPDATE zg_checkout SET total_amount"):
                st["order"]["total_amount"] = params[0]
            self._set([], [])
        elif s == "SELECT * FROM zg_checkout WHERE order_id = %s":
            self._set(list(st["order"]), [tuple(st["order"].values())])
        elif "FROM users WHERE email = %s" in s:
            self._set(list(st["user"]), [tuple(st["user"].values())])
        elif s == "SELECT * FROM zg_order_items WHERE order_id = %s ORDER BY item_id":
            rows = list(st["items"].values())
            self._set(list(rows[0]) if rows else [], [tuple(r.values()) for r in rows])
        elif s.startswith("SELECT 1 FROM zg_checkout"):
            self._set(["x"], [(1,)])
        elif s.startswith("SELECT total_amount FROM zg_checkout"):
            self._set(["total_amount"], [(st["order"]["total_amount"],)])
        elif s.startswith("SELECT item_id, discount, total_price FROM zg_order_items"):
            self._set([], [(i["item_id"], i["discount"], i["total_price"]) for i in st["items"].values()])
        elif s.startswith("SELECT discount, total_price FROM zg_order_items"):
            self._set([], [(i["discount"], i["total_price"]) for i in st["items"].values()])
        elif s.startswith("SELECT item_id FROM zg_order_items"):
            self._set([], [(i["item_id"],) for i in st["items"].values()])
        elif s.startswith("SELECT DISTINCT c.order_id"):
            self._set(["order_id", "full_name", "email", "order_date", "total_amount", "payment_method", "status",
                       "delivery_boy_id", "item_count"],
                      [(st["order"]["order_id"], "N", st["order"]["email"], "2026-10-27", st["order"]["total_amount"], "online", "Placed",
                        None, len(st["items"]))])
        elif s.startswith("SELECT COUNT(*) AS total_orders"):
            self._set(["total_orders", "revenue", "pending_orders"], [(1, 0, 1)])
        elif "FROM zg_order_status_history" in s and s.startswith("SELECT 1"):
            self._set(["x"], [(1,)] if st.get("history") else [])
        elif s.startswith("SELECT delivery_boy_id, status, email FROM zg_checkout"):
            self._set([], [(None, st["order"]["status"], st["order"]["email"])])
        elif s.startswith("SELECT order_id, discount, total_price, gst_amount FROM zg_order_items"):
            self._set([], [(st["order"]["order_id"], i["discount"], i["total_price"], i.get("gst_amount")) for i in st["items"].values()])
        elif "FROM advance_pay_transactions" in s:
            self._set([], [(st["order"]["order_id"], st["credit"])] if st.get("credit") is not None else [])
        elif s.startswith("SELECT email, delivery_charges, vip_discount, vip_percentage, gst_percentage FROM users"):
            u = st["user"]
            self._set([], [(st["order"]["email"], u["delivery_charges"], u["vip_discount"], u["vip_percentage"], u["gst_percentage"])])
        elif s.startswith("SELECT order_id, discount, total_price, product_id, variant_id, quantity FROM zg_order_items"):
            self._set([], [(st["order"]["order_id"], i["discount"], i["total_price"], i["product_id"], i["variant_id"], i["quantity"]) for i in st["items"].values()])
        elif s.startswith("SELECT product_id, gst_applicable, gst_price FROM zg_product"):
            cfg = st.get("gst_config", {"gst_applicable": "Y", "gst_price": D("0")})
            self._set([], [(pid, cfg["gst_applicable"], cfg["gst_price"]) for pid in sorted({i["product_id"] for i in st["items"].values()})])
        elif s.startswith("SELECT p.gst_applicable AS product_gst_applicable"):
            cfg = st.get("gst_config", {"gst_applicable": "Y", "gst_price": D("0")})
            self._set(["product_gst_applicable", "configured_amount", "variant_gst"], [(cfg["gst_applicable"], cfg["gst_price"], "N")])
        else:  # images, warehouses, history, delivery boys, filter dropdowns

            self._set([], [])

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self, state):
        self.state = state

    def cursor(self):
        return _Ctx(FakeCursor(self.state))


class _Ctx:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, *exc):
        return False


def make_state(items, total, gst=None, delivery="50", vip=("N", 0), status="Placed"):
    rows = {}
    for item in items:
        item = dict(item)
        item["gst_amount"] = gst.get(item["item_id"]) if isinstance(gst, dict) else None
        rows[item["item_id"]] = item
    return {"writes": [], "items": rows, "history": False,
            "order": {"order_id": 77, "full_name": "N", "email": "c@example.invalid", "phone": "1", "address": "a",
                      "city": "c", "state": "s", "postal_code": "1", "country": "IN", "order_date": "2026-10-27",
                      "status": status, "payment_method": "online", "delivery_boy_id": None, "total_amount": total},
            "user": {"username": "u", "warehouse_id": None, "city": None, "gst_percentage": D("100"),
                     "delivery_charges": D(delivery), "latitude": None, "longitude": None,
                     "vip_discount": vip[0], "vip_percentage": D(str(vip[1]))}}


def detail(state, bonus=preview, snapshot=True):
    with patch.object(op, "connection", FakeConnection(state)), \
         patch.object(op, "preview_customer_bonus", bonus), \
         patch("legacydb.order_gst_snapshot.snapshot_available", return_value=snapshot):
        return op._build_detail(77)


class StoredCartDiscountTests(SimpleTestCase):
    def test_fixed_800_is_inferred_from_the_persisted_total(self):
        self.assertEqual(op.stored_cart_discount([line("9550.00")], "8750.00"),
                         (D("800.00"), D("8750.00"), op.DISCOUNT_STORED))

    def test_no_discount_when_total_equals_items(self):
        self.assertEqual(op.stored_cart_discount([line("500")], "500")[2], op.DISCOUNT_NONE)

    def test_total_above_items_is_preserved_not_invented(self):
        d, subtotal, source = op.stored_cart_discount([line("500")], "650")
        self.assertEqual((d, subtotal, source), (ZERO, D("650.00"), op.DISCOUNT_ABOVE_ITEMS))

    def test_difference_larger_than_eligible_lines_is_unreliable_and_preserved(self):
        items = [line("1000", discount="100", item_id=1), line("500", item_id=2)]
        d, subtotal, source = op.stored_cart_discount(items, "100")
        self.assertEqual((d, subtotal, source), (ZERO, D("100.00"), op.DISCOUNT_UNRELIABLE))

    def test_missing_total_falls_back_to_items_and_invents_nothing(self):
        for stored in (None, "", 0):
            d, subtotal, source = op.stored_cart_discount([line("500")], stored)
            self.assertEqual((d, subtotal, source), (ZERO, D("500.00"), op.DISCOUNT_NO_TOTAL))

    def test_todays_cart_discount_settings_are_never_read(self):
        with patch("adminapi.cart_discount.load_cart_discount_config", side_effect=AssertionError("must not be read")):
            self.assertEqual(op.stored_cart_discount([line("9550")], "8750")[0], D("800.00"))

    def test_no_hardcoded_percentage_remains(self):
        self.assertNotIn("cart_discount_percent", op.FIN)


class OrderDetailFinancialsTests(SimpleTestCase):
    def test_screenshot_order_shows_fixed_800_not_955(self):
        state = make_state([line("9550.00")], D("8750.00"), gst={1: D("3510.00")})
        data = detail(state)
        f, items = data["financials"], data["items"]
        self.assertEqual((items["cart_discount"], items["cart_discount_type"], items["cart_discount_percent"]),
                         ("800.00", "fixed", "0.00"))
        self.assertEqual(items["non_discounted_after_discount"], "8750.00")
        self.assertEqual((f["subtotal"], f["cart_discount"], f["gst_amount"], f["total_with_gst"]),
                         ("8750.00", "800.00", "3510.00", "12260.00"))
        self.assertEqual((f["delivery_charges"], f["amount_before_bonus"], f["amount_payable"]),
                         ("50.00", "12310.00", "12310.00"))
        self.assertEqual((f["recorded_order_amount"], f["stored_subtotal_after_discount"]), ("12310.00", "8750.00"))
        self.assertEqual(f["original_items_subtotal"], "9550.00")

    def test_details_subtotal_matches_the_persisted_amount_and_the_list(self):
        state = make_state([line("9550.00")], D("8750.00"), gst={1: D("3510.00")})
        data = detail(state)
        with patch.object(op, "connection", FakeConnection(state)):
            listed = op.OrderManageView().get(SimpleNamespace(query_params={})).data["orders"][0]["total_amount"]
        self.assertEqual(listed, "8750.00")
        self.assertEqual(data["financials"]["subtotal"], listed)
        self.assertEqual(data["order"]["total_amount"], listed)

    def test_discount_is_not_deducted_twice(self):
        state = make_state([line("9550.00")], D("8750.00"), gst={1: D("3510.00")})
        f = detail(state)["financials"]
        self.assertEqual(D(f["amount_before_bonus"]), D("8750.00") + D("3510.00") + D("50.00"))

    def test_vip_does_not_stack_with_a_cart_discount(self):
        state = make_state([line("9550.00")], D("8750.00"), gst={1: D("0")}, vip=("Y", 10))
        f = detail(state)["financials"]
        self.assertEqual((f["vip_discount"], f["vip_discount_percent"], f["vip_not_applied_reason"]),
                         ("0.00", "0.00", "cart_discount_applied"))

    def test_vip_applies_normally_when_there_is_no_cart_discount(self):
        state = make_state([line("1000.00")], D("1000.00"), gst={1: D("0")}, vip=("Y", 10))
        f = detail(state)["financials"]
        self.assertEqual((f["vip_discount"], f["vip_not_applied_reason"], f["amount_before_bonus"]),
                         ("100.00", "", "950.00"))

    def test_product_level_discounts_stay_separate_from_the_cart_discount(self):
        items = [line("900.00", discount="100", item_id=1, price="500", qty=2), line("9000.00", item_id=2)]
        state = make_state(items, D("9100.00"), gst={1: D("0"), 2: D("0")})
        data = detail(state)
        self.assertEqual((data["financials"]["product_discount"], data["financials"]["cart_discount"],
                          data["financials"]["original_items_subtotal"]), ("100.00", "800.00", "10000.00"))
        self.assertEqual((data["items"]["discounted_subtotal"], data["items"]["non_discounted_subtotal"]),
                         ("900.00", "9000.00"))
        self.assertEqual(data["financials"]["subtotal"], "9100.00")

    def test_stored_gst_snapshot_is_preserved_not_recalculated(self):
        state = make_state([line("1000.00")], D("1000.00"), gst={1: D("123.45")})
        f = detail(state)["financials"]
        self.assertEqual((f["gst_amount"], f["gst_source"]), ("123.45", "snapshot"))

    def test_legacy_order_without_gst_snapshot_keeps_legacy_handling(self):
        state = make_state([line("1000.00")], D("1000.00"), gst=None)
        f = detail(state)["financials"]
        self.assertEqual((f["gst_amount"], f["gst_source"]), ("0.00", "legacy_unrecorded"))

    def test_delivery_is_counted_once(self):
        state = make_state([line("1000.00")], D("1000.00"), gst={1: D("0")}, delivery="50")
        f = detail(state)["financials"]
        self.assertEqual((f["delivery_charges"], f["amount_before_bonus"]), ("50.00", "1050.00"))

    def test_recorded_credit_is_subtracted_once(self):
        def recorded(email, amount, order_id=None):
            amount = D(str(amount))
            return {"monthly_bonus": D("1000"), "carried_forward": ZERO, "available_bonus": D("200"),
                    "bonus_applied": D("800"), "amount_payable": amount - D("800"), "remaining_bonus": D("200"),
                    "credit_status": "already_applied"}
        state = make_state([line("1000.00")], D("1000.00"), gst={1: D("0")}, delivery="0")
        f = detail(state, bonus=recorded)["financials"]
        self.assertEqual((f["amount_before_bonus"], f["credit_release"], f["amount_payable"], f["bonus_is_recorded"]),
                         ("1000.00", "800.00", "200.00", True))

    def test_historical_order_without_a_reliable_breakdown_keeps_its_stored_total(self):
        items = [line("1000.00", discount="100", item_id=1), line("500.00", item_id=2)]
        state = make_state(items, D("100.00"), gst={1: D("0"), 2: D("0")}, delivery="0")
        data = detail(state)
        self.assertEqual((data["financials"]["subtotal"], data["financials"]["cart_discount"],
                          data["financials"]["cart_discount_source"]), ("100.00", "0.00", op.DISCOUNT_UNRELIABLE))


class PatchDoesNotRewriteTotalsTests(SimpleTestCase):
    def patch_order(self, state, items):
        body = {"full_name": "N", "items": items}
        request = SimpleNamespace(data=body)
        with patch.object(op, "connection", FakeConnection(state)), patch.object(op, "transaction", SimpleNamespace(atomic=nullcontext)), \
             patch.object(op, "_has_column", return_value=False), \
             patch.object(op, "_build_detail", side_effect=lambda *a, **k: {"financials": {}}):
            return op.OrderDetailView().patch(request, 77).data

    def total_writes(self, state):
        return [w for w in state["writes"] if w[0].startswith("UPDATE zg_checkout SET total_amount")]

    def test_edit_preserves_the_original_fixed_discount_instead_of_applying_10_percent(self):
        state = make_state([line("9550.00", price="9550")], D("8750.00"))
        self.patch_order(state, [{"item_id": 1, "quantity": 1, "price": "10550", "discount": "0"}])
        writes = self.total_writes(state)
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][1][0], D("9750.00"))          # 10550 - 800, not 10550 x 0.9 = 9495

    def test_edit_that_changes_nothing_does_not_rewrite_the_total(self):
        state = make_state([line("9550.00", price="9550")], D("8750.00"))
        self.patch_order(state, [{"item_id": 1, "quantity": 1, "price": "9550", "discount": "0"}])
        self.assertEqual(self.total_writes(state), [])
        self.assertEqual(state["order"]["total_amount"], D("8750.00"))

    def test_unreliable_history_keeps_the_stored_amount_and_says_so(self):
        items = [line("1000.00", discount="100", item_id=1, price="1100"), line("500.00", item_id=2, price="500")]
        state = make_state(items, D("100.00"))
        data = self.patch_order(state, [{"item_id": 2, "quantity": 1, "price": "600", "discount": "0"}])
        self.assertEqual(self.total_writes(state), [])
        self.assertIn("recorded_total_notice", data)

    def test_order_without_a_recorded_total_is_not_given_an_invented_one(self):
        state = make_state([line("500.00", price="500")], None)
        self.patch_order(state, [{"item_id": 1, "quantity": 1, "price": "600", "discount": "0"}])
        self.assertEqual(self.total_writes(state), [])

    def test_order_without_a_discount_follows_the_edited_items(self):
        state = make_state([line("500.00", price="500")], D("500.00"))
        self.patch_order(state, [{"item_id": 1, "quantity": 1, "price": "600", "discount": "0"}])
        self.assertEqual(self.total_writes(state)[0][1][0], D("600.00"))

    def test_discount_never_exceeds_the_lines_that_can_carry_it(self):
        self.assertEqual(op.recorded_total_after_edit([line("9550")], "8750", [line("500")]), D("0.00"))


class ProcessingConfirmationTests(SimpleTestCase):
    def confirm(self, history):
        state = make_state([line("9550.00")], D("8750.00"), gst={1: D("3510.00")})
        state["history"] = history
        calls = []

        def release(cursor, order_id, email, amount, allow_new=True, **kw):
            calls.append((amount, allow_new))
            return {"amount_payable": amount, "bonus_applied": ZERO, "remaining_bonus": ZERO}

        request = SimpleNamespace(user=SimpleNamespace(role="ADMIN"), data={"status": "processing"})
        with patch.object(op, "connection", FakeConnection(state)), patch.object(op, "transaction", SimpleNamespace(atomic=nullcontext)), \
             patch.object(op, "_has_column", return_value=False), \
             patch.object(op, "release_and_deduct_for_confirmed_order", release), \
             patch.object(op, "preview_customer_bonus", preview), \
             patch("legacydb.order_gst_snapshot.snapshot_available", return_value=True):
            op.OrderStatusView().post(request, 77)
        return calls

    def test_confirmation_passes_the_persisted_based_amount_once(self):
        self.assertEqual(self.confirm(history=False), [(D("12310.00"), True)])

    def test_a_repeat_confirmation_is_not_allowed_to_create_a_new_deduction(self):
        self.assertEqual(self.confirm(history=True), [(D("12310.00"), False)])


def listed(state, snapshot=True):
    with patch.object(op, "connection", FakeConnection(state)), \
         patch("legacydb.order_gst_snapshot.snapshot_available", return_value=snapshot):
        return op.OrderManageView().get(SimpleNamespace(query_params={})).data["orders"][0]


def recorded_credit(applied):
    def preview_recorded(email, amount, order_id=None):
        amount, applied_amount = D(str(amount)), D(str(applied))
        return {"monthly_bonus": ZERO, "carried_forward": ZERO, "available_bonus": ZERO, "bonus_applied": applied_amount,
                "amount_payable": max(ZERO, amount - applied_amount), "remaining_bonus": ZERO, "credit_status": "already_applied"}
    return preview_recorded


class PayableVersusRecordedAmountTests(SimpleTestCase):
    """zg_checkout.total_amount is the subtotal after cart discount; the payable amount is derived, never stored there.

    Order 257375 of the report: items 8,845, fixed discount 800, stored total 8,045, GST 145, delivery 0.
    """

    def order_257375(self, **kw):
        return make_state([line("8845.00", price="8845")], D("8045.00"), gst={1: D("145.00")}, delivery="0", **kw)

    def test_recorded_amount_is_the_derived_payable_while_the_stored_subtotal_is_kept(self):
        data = detail(self.order_257375())
        f = data["financials"]
        self.assertEqual((f["subtotal"], f["recorded_order_amount"], f["recorded_order_amount_meaning"]),
                         ("8045.00", "8190.00", "derived_payable_amount"))
        self.assertEqual((f["total_with_gst"], f["amount_payable"], f["final_payable_amount"]), ("8190.00", "8190.00", "8190.00"))
        self.assertEqual(f["recorded_order_amount"], f["final_payable_amount"])
        self.assertEqual(f["stored_subtotal_after_discount"], "8045.00")   # the stored subtotal is still reported separately

    def test_all_orders_and_order_details_agree_on_the_payable_amount(self):
        state = self.order_257375()
        row, data = listed(state), detail(state)
        self.assertEqual(row["payable_amount"], data["financials"]["amount_payable"])
        self.assertEqual(row["payable_amount"], "8190.00")
        # the original keys keep their meaning: total_amount is still the stored subtotal after the cart discount
        self.assertEqual((row["total_amount"], row["subtotal_after_discount"]), ("8045.00", "8045.00"))
        self.assertEqual(data["order"]["total_amount"], "8045.00")

    def test_gst_and_delivery_are_each_counted_once_in_both_views(self):
        state = make_state([line("8845.00", price="8845")], D("8045.00"), gst={1: D("145.00")}, delivery="60")
        self.assertEqual(listed(state)["payable_amount"], "8250.00")      # 8045 + 145 + 60
        self.assertEqual(detail(state)["financials"]["amount_payable"], "8250.00")

    def test_the_fixed_discount_is_applied_once_in_both_views(self):
        state = self.order_257375()
        self.assertEqual(listed(state)["payable_amount"], "8190.00")      # not 8845 - 800 - 800 + 145
        self.assertEqual(detail(state)["items"]["cart_discount"], "800.00")

    def test_vip_does_not_stack_with_the_cart_discount_in_either_view(self):
        state = self.order_257375(vip=("Y", 10))
        self.assertEqual(listed(state)["payable_amount"], "8190.00")
        self.assertEqual(detail(state)["financials"]["amount_payable"], "8190.00")

    def test_vip_applies_to_an_order_without_a_cart_discount_in_both_views(self):
        state = make_state([line("1000.00")], D("1000.00"), gst={1: D("0")}, delivery="0", vip=("Y", 10))
        self.assertEqual(listed(state)["payable_amount"], "900.00")
        self.assertEqual(detail(state)["financials"]["amount_payable"], "900.00")

    def test_recorded_credit_reduces_the_payable_amount_once_in_both_views(self):
        state = self.order_257375()
        state["credit"] = D("1000.00")
        row, data = listed(state), detail(state, bonus=recorded_credit("1000.00"))
        self.assertEqual((row["payable_amount"], row["credit_recorded"]), ("7190.00", True))
        self.assertEqual(data["financials"]["amount_payable"], "7190.00")

    def test_without_a_recorded_credit_the_list_says_the_amount_is_before_credit(self):
        row = listed(self.order_257375())
        self.assertEqual((row["payable_amount"], row["credit_recorded"]), ("8190.00", False))

    def test_before_the_snapshot_columns_exist_the_list_derives_gst_with_the_shared_rule(self):
        state = self.order_257375()
        state["gst_config"] = {"gst_applicable": "Y", "gst_price": D("145.00")}
        row = listed(state, snapshot=False)
        self.assertEqual(row["payable_amount"], "8190.00")
        self.assertEqual(row["total_amount"], "8045.00")                  # the stored subtotal is still reported

    def test_historical_order_values_are_unchanged_and_nothing_is_written_when_viewing(self):
        items = [line("1000.00", discount="100", item_id=1), line("500.00", item_id=2)]
        state = make_state(items, D("100.00"), gst={1: D("0"), 2: D("0")}, delivery="0")
        row = listed(state)
        data = detail(state)
        self.assertEqual(row["total_amount"], "100.00")
        self.assertEqual(data["order"]["total_amount"], "100.00")
        self.assertEqual(state["order"]["total_amount"], D("100.00"))
        self.assertEqual(state["writes"], [])

    def test_patch_stores_only_the_subtotal_after_discount_never_gst_delivery_or_payable(self):
        state = make_state([line("8845.00", price="8845")], D("8045.00"), gst={1: D("145.00")}, delivery="60")
        request = SimpleNamespace(data={"full_name": "N", "items": [{"item_id": 1, "quantity": 1, "price": "9845", "discount": "0"}]})
        with patch.object(op, "connection", FakeConnection(state)), patch.object(op, "transaction", SimpleNamespace(atomic=nullcontext)), \
             patch.object(op, "_has_column", return_value=False), \
             patch.object(op, "_build_detail", side_effect=lambda *a, **k: {"financials": {}}):
            op.OrderDetailView().patch(request, 77)
        writes = [w for w in state["writes"] if w[0].startswith("UPDATE zg_checkout SET total_amount")]
        self.assertEqual([w[1][0] for w in writes], [D("9045.00")])       # 9845 - 800; no GST (145) or delivery (60) added


def credit_preview_not_recorded(email, amount, order_id=None):
    amount = D(str(amount))
    return {"monthly_bonus": ZERO, "carried_forward": ZERO, "available_bonus": D("500"), "bonus_applied": D("500"),
            "amount_payable": amount - D("500"), "remaining_bonus": ZERO, "credit_status": "applied"}


class RecordedAmountMatchesPayableTests(SimpleTestCase):
    """Reported order: items 8,235, fixed discount 800, stored total 7,435, GST 135, delivery 0 -> payable 7,570."""

    def reported(self, **kw):
        kw.setdefault("gst", {1: D("135.00")})
        return make_state([line("8235.00", price="8235")], D("7435.00"), delivery="0", **kw)

    def test_stored_subtotal_plus_gst_and_zero_delivery_gives_7570(self):
        f = detail(self.reported())["financials"]
        self.assertEqual((f["subtotal"], f["gst_amount"], f["delivery_charges"], f["vip_discount"]),
                         ("7435.00", "135.00", "0.00", "0.00"))
        self.assertEqual((f["amount_payable"], f["recorded_order_amount"]), ("7570.00", "7570.00"))
        self.assertEqual((f["recorded_order_amount_meaning"], f["payable_reliably_derived"]), ("derived_payable_amount", True))

    def test_the_original_stored_subtotal_is_preserved_in_the_response_and_never_written(self):
        state = self.reported()
        data = detail(state)
        self.assertEqual(data["order"]["total_amount"], "7435.00")
        self.assertEqual(data["financials"]["stored_subtotal_after_discount"], "7435.00")
        self.assertEqual(state["order"]["total_amount"], D("7435.00"))
        self.assertEqual(state["writes"], [])

    def test_gst_is_included_once_and_the_fixed_discount_is_not_deducted_again(self):
        f = detail(self.reported())["financials"]
        self.assertEqual(D(f["recorded_order_amount"]), D("7435.00") + D("135.00"))
        self.assertEqual((f["original_items_subtotal"], f["cart_discount"]), ("8235.00", "800.00"))

    def test_the_list_and_the_details_show_the_same_payable_amount(self):
        state = self.reported()
        self.assertEqual(listed(state)["payable_amount"], detail(state)["financials"]["recorded_order_amount"])
        self.assertEqual(listed(state)["total_amount"], "7435.00")

    def test_vip_does_not_stack_with_the_cart_discount(self):
        f = detail(self.reported(vip=("Y", 10)))["financials"]
        self.assertEqual((f["vip_discount"], f["recorded_order_amount"]), ("0.00", "7570.00"))

    def test_a_recorded_credit_deduction_is_part_of_the_derived_amount_once(self):
        state = self.reported()
        state["credit"] = D("500.00")
        f = detail(state, bonus=recorded_credit("500.00"))["financials"]
        self.assertEqual((f["recorded_order_amount"], f["amount_payable"], f["payable_reliably_derived"]), ("7070.00", "7070.00", True))
        self.assertEqual(listed(state)["payable_amount"], "7070.00")

    def test_a_credit_that_is_only_a_preview_keeps_the_stored_subtotal(self):
        f = detail(self.reported(), bonus=credit_preview_not_recorded)["financials"]
        self.assertFalse(f["payable_reliably_derived"])
        self.assertEqual((f["recorded_order_amount"], f["recorded_order_amount_meaning"]), ("7435.00", "subtotal_after_cart_discount"))

    def test_an_order_without_a_gst_snapshot_keeps_the_stored_subtotal_and_never_invents_a_payable(self):
        state = self.reported(gst=None)
        f = detail(state)["financials"]
        self.assertEqual((f["payable_reliably_derived"], f["recorded_order_amount"], f["recorded_order_amount_meaning"]),
                         (False, "7435.00", "subtotal_after_cart_discount"))
        self.assertIsNone(listed(state)["payable_amount"])

    def test_an_order_whose_discount_cannot_be_established_keeps_the_stored_subtotal(self):
        items = [line("1000.00", discount="100", item_id=1), line("500.00", item_id=2)]
        state = make_state(items, D("100.00"), gst={1: D("5"), 2: D("5")}, delivery="0")
        f = detail(state)["financials"]
        self.assertEqual((f["payable_reliably_derived"], f["recorded_order_amount"]), (False, "100.00"))
        self.assertIsNone(listed(state)["payable_amount"])
        self.assertEqual(state["writes"], [])

    def test_the_cart_api_modules_are_not_imported_or_changed_by_the_admin_summary(self):
        import inspect
        source = inspect.getsource(op)
        import re
        imports = re.findall(r"^\s*(?:from|import)\s+.*$", source, flags=re.M)
        self.assertEqual([i for i in imports if "views_commerce" in i or "views_orders" in i], [])
        self.assertEqual([i for i in imports if "cart_discount" in i and "calculate" in i], [])   # the admin view never recalculates the promotion


class OrderWithoutSnapshotColumnsTests(SimpleTestCase):
    """Live-database case (order 807996): items 8,235, fixed discount 800, stored total 7,435, GST 135 by the shared GST rule.

    The database has no per-order GST snapshot columns, so GST is derived by the shared rule, not read from a snapshot.
    """

    def order(self, **kw):
        state = make_state([line("8235.00", price="8235")], D("7435.00"), delivery="0", **kw)
        state["gst_config"] = {"gst_applicable": "Y", "gst_price": D("135.00")}
        return state

    def test_detail_derives_the_payable_and_the_recorded_amount_matches_it(self):
        f = detail(self.order(), snapshot=False)["financials"]
        self.assertEqual((f["gst_source"], f["gst_amount"], f["amount_payable"]), ("current_settings_pre_snapshot", "135.00", "7570.00"))
        self.assertEqual((f["recorded_order_amount"], f["payable_reliably_derived"], f["recorded_order_amount_meaning"]),
                         ("7570.00", True, "derived_payable_amount"))
        self.assertEqual((f["stored_subtotal_after_discount"], f["payable_gst_basis"], f["payable_fallback_reason"]),
                         ("7435.00", "gst_current_settings", ""))

    def test_the_stored_subtotal_is_unchanged_and_viewing_writes_nothing(self):
        state = self.order()
        data = detail(state, snapshot=False)
        listed(state, snapshot=False)
        self.assertEqual((data["order"]["total_amount"], state["order"]["total_amount"]), ("7435.00", D("7435.00")))
        self.assertEqual(state["writes"], [])

    def test_all_orders_and_order_details_show_the_same_payable(self):
        state = self.order()
        row = listed(state, snapshot=False)
        self.assertEqual(row["payable_amount"], detail(state, snapshot=False)["financials"]["recorded_order_amount"])
        self.assertEqual((row["payable_amount"], row["total_amount"]), ("7570.00", "7435.00"))

    def test_gst_is_included_once_and_the_discount_is_not_deducted_twice(self):
        f = detail(self.order(), snapshot=False)["financials"]
        self.assertEqual(D(f["recorded_order_amount"]), D("7435.00") + D("135.00"))
        self.assertEqual((f["cart_discount"], f["original_items_subtotal"]), ("800.00", "8235.00"))

    def test_a_recorded_credit_is_subtracted_exactly_once(self):
        state = self.order()
        state["credit"] = D("500.00")
        f = detail(state, bonus=recorded_credit("500.00"), snapshot=False)["financials"]
        self.assertEqual((f["recorded_order_amount"], f["payable_reliably_derived"]), ("7070.00", True))
        self.assertEqual(listed(state, snapshot=False)["payable_amount"], "7070.00")

    def test_vip_does_not_stack_with_the_cart_discount(self):
        f = detail(self.order(vip=("Y", 10)), snapshot=False)["financials"]
        self.assertEqual((f["vip_discount"], f["recorded_order_amount"]), ("0.00", "7570.00"))


class FallbackReasonTests(SimpleTestCase):
    def test_missing_gst_in_a_snapshot_era_order_is_never_treated_as_zero(self):
        state = make_state([line("8235.00", price="8235")], D("7435.00"), gst=None, delivery="0")
        f = detail(state)["financials"]
        self.assertEqual((f["payable_reliably_derived"], f["recorded_order_amount"], f["gst_source"]), (False, "7435.00", "legacy_unrecorded"))
        self.assertEqual(f["payable_fallback_reason"], "GST was not recorded for every line of this order.")
        self.assertIsNone(listed(state)["payable_amount"])

    def test_a_partially_recorded_gst_snapshot_is_unreliable(self):
        items = [line("1000.00", item_id=1), line("500.00", item_id=2)]
        state = make_state(items, D("1500.00"), gst={1: D("10.00")}, delivery="0")
        f = detail(state)["financials"]
        self.assertEqual((f["gst_source"], f["payable_reliably_derived"], f["recorded_order_amount"]), ("partial_snapshot", False, "1500.00"))
        self.assertIsNone(listed(state)["payable_amount"])

    def test_an_unestablishable_discount_names_the_missing_information(self):
        items = [line("1000.00", discount="100", item_id=1), line("500.00", item_id=2)]
        state = make_state(items, D("100.00"), gst={1: D("5"), 2: D("5")}, delivery="0")
        f = detail(state)["financials"]
        self.assertFalse(f["payable_reliably_derived"])
        self.assertEqual(f["payable_fallback_reason"], "The cart discount cannot be established from the stored total of this order.")

    def test_a_credit_that_is_only_a_preview_names_the_missing_information(self):
        state = make_state([line("8235.00", price="8235")], D("7435.00"), gst={1: D("135.00")}, delivery="0")
        f = detail(state, bonus=credit_preview_not_recorded)["financials"]
        self.assertFalse(f["payable_reliably_derived"])
        self.assertEqual(f["payable_fallback_reason"], "The monthly credit for this order is not recorded yet.")

    def test_the_reliability_rule(self):
        for gst, discount, expected in [("snapshot", op.DISCOUNT_STORED, True), ("snapshot", op.DISCOUNT_NONE, True),
                                        ("current_settings_pre_snapshot", op.DISCOUNT_STORED, True),
                                        ("legacy_unrecorded", op.DISCOUNT_STORED, False), ("partial_snapshot", op.DISCOUNT_NONE, False),
                                        ("snapshot", op.DISCOUNT_UNRELIABLE, False), ("snapshot", op.DISCOUNT_NO_TOTAL, False),
                                        ("snapshot", op.DISCOUNT_ABOVE_ITEMS, False)]:
            self.assertEqual(op.payable_inputs_reliable(gst, discount), expected, (gst, discount))
