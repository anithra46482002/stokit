"""Monthly credit is deducted when an order is PLACED and never resets until the next eligible month.

Evidence level: UNIT / REGRESSION against the in-memory ledger from tests_monthly_credit (no database is touched).
These tests prove the rules, the call order inside order placement, idempotency, and that the row locks are requested
in a safe order. They do NOT prove PostgreSQL transaction rollback or real concurrent-transaction blocking: that needs
an approved disposable PostgreSQL database (see ConcurrentPlacementNotVerified).
"""
import json
from contextlib import nullcontext
from datetime import date, datetime
from decimal import Decimal
from unittest import mock

from django.test import RequestFactory, SimpleTestCase, override_settings

from adminapi.bonus_credit import release_and_deduct_for_confirmed_order
from adminapi.tests_monthly_credit import EMAIL, FakeCursor, FakeLedger, terms
from legacy_api import views_finance, views_orders
from legacy_api.tests_auth import BEARER, authed, post
from legacydb import monthly_credit as mc

D = Decimal
OCT12 = datetime(2026, 10, 12, 10, 0)
OCT13 = datetime(2026, 10, 13, 9, 30)
OCT29 = datetime(2026, 10, 29, 18, 0)
NOV3 = datetime(2026, 11, 3, 11, 0)


def ledger2000():
    """20,000 offer at 10% for 12 months starting 1 October 2026 = 2,000 per month."""
    return FakeLedger(terms(payment="20000", bonus="10"))


class _CursorContext:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, *exc):
        return False


class FakeConnection:
    def __init__(self, ledger, events=None):
        self.ledger, self.events = ledger, events

    def cursor(self):
        events = self.events

        class Cursor(FakeCursor):
            def execute(self, sql, params=None):
                if events is not None and sql.startswith("INSERT INTO advance_pay_transactions"):
                    events.append("ledger-insert")
                return super().execute(sql, params)

        return _CursorContext(Cursor(self.ledger))


def place(ledger, order_id, amount, when, email=EMAIL):
    """Run the real placement credit step against the fake ledger at a fixed time."""
    with mock.patch.object(views_orders, "connection", FakeConnection(ledger)), \
            mock.patch.object(mc, "local_now", return_value=when):
        return views_orders.apply_order_credit(7 if email else None, order_id, D(str(amount)))


def remaining(ledger, when):
    return mc.load_state(ledger.cursor(), 7, when.date())[0].remaining_this_month


class PlacementDeductionTests(SimpleTestCase):
    def test_acceptance_1400_of_2000_leaves_exactly_600(self):
        ledger = ledger2000()
        result = place(ledger, 1001, "1400.00", OCT12)
        self.assertEqual((result["bonus_applied"], result["remaining_bonus"]), (D("1400.00"), D("600.00")))
        self.assertEqual(remaining(ledger, OCT12), D("600.00"))
        self.assertEqual(ledger.used(), D("1400.00"))

    def test_next_day_purchase_uses_the_same_remaining_balance_then_zero(self):
        ledger = ledger2000()
        place(ledger, 1001, "1400", OCT12)
        second = place(ledger, 1002, "1000", OCT13)
        self.assertEqual((second["bonus_applied"], second["amount_payable"]), (D("600.00"), D("400.00")))
        self.assertEqual(remaining(ledger, OCT13), D("0.00"))

    def test_balances_600_then_200_then_0_never_restore_2000(self):
        ledger = ledger2000()
        self.assertEqual(place(ledger, 1, "1400", OCT12)["remaining_bonus"], D("600.00"))
        self.assertEqual(place(ledger, 2, "400", OCT12)["remaining_bonus"], D("200.00"))
        self.assertEqual(place(ledger, 3, "200", OCT13)["remaining_bonus"], D("0.00"))
        for order_id, when in ((4, OCT13), (5, OCT29)):
            result = place(ledger, order_id, "750", when)
            self.assertEqual((result["bonus_applied"], result["amount_payable"]), (D("0.00"), D("750.00")))
            self.assertEqual(remaining(ledger, when), D("0.00"))
        self.assertEqual(ledger.used(), D("2000.00"))  # never more than the October release

    def test_several_purchases_on_the_same_day_share_one_balance(self):
        ledger = ledger2000()
        applied = [place(ledger, i, amount, OCT12)["bonus_applied"] for i, amount in ((1, "700"), (2, "700"), (3, "700"))]
        self.assertEqual(applied, [D("700.00"), D("700.00"), D("600.00")])
        self.assertEqual(remaining(ledger, OCT12), D("0.00"))

    def test_purchases_on_different_days_in_october_share_one_balance(self):
        ledger = ledger2000()
        place(ledger, 1, "1400", OCT12)
        place(ledger, 2, "400", OCT13)
        self.assertEqual(remaining(ledger, OCT29), D("200.00"))
        self.assertEqual(place(ledger, 3, "900", OCT29)["bonus_applied"], D("200.00"))
        self.assertEqual(remaining(ledger, OCT29), D("0.00"))

    def test_purchase_smaller_than_the_balance_is_fully_covered(self):
        ledger = ledger2000()
        self.assertEqual(place(ledger, 1, "150.50", OCT12)["remaining_bonus"], D("1849.50"))

    def test_no_active_allocation_records_nothing(self):
        ledger = FakeLedger(None)
        self.assertIsNone(place(ledger, 1, "500", OCT12))
        self.assertEqual(ledger.rows, [])
        self.assertIsNone(place(ledger2000(), 1, "500", OCT12, email=""))


class NeverResetsTests(SimpleTestCase):
    def test_refreshing_cart_summary_and_reopening_the_app_never_restores_the_balance(self):
        ledger = ledger2000()
        place(ledger, 1, "1400", OCT12)
        rows_before = list(ledger.rows)
        for _ in range(5):
            with mock.patch.object(mc, "local_now", return_value=OCT13):
                context = mc.customer_credit_context(ledger.cursor(), EMAIL)
            with mock.patch.object(views_finance, "current_credit_context", return_value=context):
                monthly, carried, available = views_finance.current_available_credit({"email": EMAIL})
            self.assertEqual((monthly, available), (2000.0, 600.0))
            self.assertEqual(context["state"].remaining_this_month, D("600.00"))
        self.assertEqual(ledger.rows, rows_before)  # summary/cart reads never write
        self.assertEqual(ledger.allocation_updates, [D("1400.00")])  # lifetime column changed once, by the placement only

    def test_unused_october_credit_carries_into_november_exactly_once(self):
        ledger = ledger2000()
        place(ledger, 1, "1400", OCT12)  # 600 unused
        state = mc.load_state(ledger.cursor(), 7, NOV3.date())[0]
        self.assertEqual((state.monthly_credit_release, state.carried_forward), (D("2000.00"), D("600.00")))
        self.assertEqual(state.remaining_this_month, D("2600.00"))
        result = place(ledger, 2, "1000", NOV3)
        self.assertEqual(result["remaining_bonus"], D("1600.00"))
        # Another reading in November must not add the October 600 a second time.
        self.assertEqual(remaining(ledger, NOV3), D("1600.00"))

    def test_fully_used_october_gives_november_only_its_own_release(self):
        ledger = ledger2000()
        place(ledger, 1, "2000", OCT29)
        state = mc.load_state(ledger.cursor(), 7, NOV3.date())[0]
        self.assertEqual((state.carried_forward, state.remaining_this_month), (D("0.00"), D("2000.00")))


class AdminConfirmationTests(SimpleTestCase):
    def confirm(self, ledger, order_id, amount, when=date(2026, 10, 14), allow_new=True):
        return release_and_deduct_for_confirmed_order(ledger.cursor(), order_id, EMAIL, D(str(amount)), today=when, allow_new=allow_new)

    def test_confirming_an_already_placed_order_never_deducts_again(self):
        ledger = ledger2000()
        place(ledger, 1, "1400", OCT12)
        rows = list(ledger.rows)
        for _ in range(3):
            result = self.confirm(ledger, 1, "1400")
            self.assertTrue(result["duplicate"])
            self.assertEqual(result["bonus_applied"], D("1400.00"))
        self.assertEqual(ledger.rows, rows)
        self.assertEqual(remaining(ledger, OCT13), D("600.00"))

    def test_order_placed_with_no_credit_cannot_receive_credit_at_a_later_confirmation(self):
        ledger = ledger2000()
        place(ledger, 1, "2000", OCT12)
        place(ledger, 2, "500", OCT13)  # exhausted: zero-amount marker row
        self.assertEqual([r["amount"] for r in ledger.order_rows()], [D("2000.00"), D("0.00")])
        confirmed_in_november = self.confirm(ledger, 2, "500", when=date(2026, 11, 4))
        self.assertTrue(confirmed_in_november["duplicate"])
        self.assertEqual(confirmed_in_november["bonus_applied"], D("0.00"))
        self.assertEqual(ledger.used(), D("2000.00"))
        self.assertEqual(remaining(ledger, NOV3), D("2000.00"))  # November's own release is untouched

    def test_zero_rows_do_not_change_the_allocation_summary_columns(self):
        ledger = ledger2000()
        place(ledger, 1, "2000", OCT12)
        updates = len(ledger.allocation_updates)
        place(ledger, 2, "500", OCT12)
        self.assertEqual(len(ledger.allocation_updates), updates)


class DuplicateAndCancellationTests(SimpleTestCase):
    def test_the_same_order_submitted_twice_is_deducted_once(self):
        ledger = ledger2000()
        first = place(ledger, 77, "1400", OCT12)
        again = place(ledger, 77, "1400", OCT12)
        self.assertFalse(first["duplicate"])
        self.assertTrue(again["duplicate"])
        self.assertEqual(ledger.used(), D("1400.00"))
        self.assertEqual(len(ledger.order_rows()), 1)

    def test_cancelling_an_order_changes_nothing_in_the_credit_ledger(self):
        """No refund is implemented on purpose: a safe refund needs product decisions (partial refunds, month rollover)."""
        ledger = ledger2000()
        place(ledger, 500, "1400", OCT12)
        rows = list(ledger.rows)
        order = {"order_id": 500, "phone": "111", "email": "alice@example.invalid", "status": "Placed"}
        user = {"phone": "111", "email": "alice@example.invalid"}
        connection = mock.MagicMock()
        with authed(), mock.patch.object(views_orders.transaction, "atomic", return_value=nullcontext()), \
                mock.patch.object(views_orders, "fetchone", side_effect=[user, order]), \
                mock.patch.object(views_orders, "execute") as execute, \
                mock.patch.object(views_orders, "connection", connection):
            response = views_orders.order_cancel(post("/api/order_cancel", {"order_id": 500}, **BEARER))
        self.assertEqual(response.status_code, 200)
        connection.cursor.assert_not_called()  # cancellation never touches the credit ledger
        self.assertEqual([c.args[0] for c in execute.call_args_list], ["UPDATE zg_checkout SET status=%s WHERE order_id=%s"])
        self.assertEqual(ledger.rows, rows)
        self.assertEqual(remaining(ledger, OCT13), D("600.00"))  # still spent; the balance is not restored or doubled


ITEM = {"product_id": 15, "variant_id": 0, "qty": 1, "product_name": "Widget", "has_disc": 0, "discount_percent": 0,
        "discount_value": 0, "product_discount": 0, "product_gst_applicable": "N", "gst_price": D("0"),
        "variant_gst": "N", "variant_name": "", "price": D("1400.00"), "stock_qty": 1}
USER = {"id": 7, "fullname": "T", "phone": "1", "address": "a", "email": EMAIL, "delivery_charges": D("0.00"),
        "vip_discount": "N", "vip_percentage": D("0"), "gst_percentage": D("0")}


class OrderPostIntegrationTests(SimpleTestCase):
    """The real order_post view with the SQL helpers patched and the credit step running on the fake ledger."""

    def run_order(self, ledger, price, order_id, when, events=None, execute_side_effect=None):
        item = {**ITEM, "price": D(str(price))}
        events = events if events is not None else []

        def record(sql, params=()):
            events.append(sql.split("(")[0].strip()[:40])
            if execute_side_effect:
                execute_side_effect(sql)
            return 1

        with authed(), override_settings(STOKIT_MIN_ORDER_VALUE=D("0.00")), \
                mock.patch.object(views_orders, "snapshot_available", return_value=False), \
                mock.patch.object(views_orders.transaction, "atomic", return_value=nullcontext()), \
                mock.patch.object(views_orders, "fetchone", return_value=USER), \
                mock.patch.object(views_orders, "fetchall", return_value=[item]), \
                mock.patch.object(views_orders, "_insert_checkout_with_unique_id", return_value=order_id), \
                mock.patch.object(views_orders, "execute", side_effect=record), \
                mock.patch.object(views_orders, "connection", FakeConnection(ledger, events)), \
                mock.patch.object(mc, "local_now", return_value=when):
            return views_orders.order_post(RequestFactory().post("/api/order_post", **BEARER))

    def test_three_orders_in_october_use_one_shrinking_balance(self):
        ledger = ledger2000()
        for order_id, price, when, expected_remaining in ((901, "1400", OCT12, "600.00"), (902, "1000", OCT13, "0.00"), (903, "300", OCT29, "0.00")):
            response = self.run_order(ledger, price, order_id, when)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.content)["order_id"], str(order_id))
            self.assertEqual(remaining(ledger, when), D(expected_remaining))
        self.assertEqual([r["amount"] for r in ledger.order_rows()], [D("1400.00"), D("600.00"), D("0.00")])
        self.assertEqual(ledger.used(), D("2000.00"))

    def test_credit_is_committed_after_the_order_rows_and_before_the_cart_is_cleared(self):
        events = []
        self.run_order(ledger2000(), "1400", 910, OCT12, events=events)
        item_insert = events.index("INSERT INTO zg_order_items")
        ledger_insert = events.index("ledger-insert")
        cart_delete = events.index("DELETE FROM a_cart WHERE username=%s")
        self.assertLess(item_insert, ledger_insert)
        self.assertLess(ledger_insert, cart_delete)

    def test_failure_before_the_order_exists_records_no_credit(self):
        ledger = ledger2000()

        def fail(sql):
            if sql.startswith("INSERT INTO zg_order_items"):
                raise RuntimeError("order item insert failed")

        with self.assertRaises(RuntimeError):
            self.run_order(ledger, "1400", 920, OCT12, execute_side_effect=fail)
        self.assertEqual(ledger.rows, [])
        self.assertEqual(remaining(ledger, OCT12), D("2000.00"))

    def test_failure_after_the_deduction_propagates_so_the_transaction_rolls_back(self):
        ledger = ledger2000()

        def fail(sql):
            if sql.startswith("DELETE FROM a_cart"):
                raise RuntimeError("cart cleanup failed")

        # The exception is not swallowed: in production it leaves transaction.atomic(), which rolls the order and the
        # ledger row back together. (The fake ledger has no rollback, so only the propagation is asserted here.)
        with self.assertRaises(RuntimeError):
            self.run_order(ledger, "1400", 930, OCT12, execute_side_effect=fail)

    def test_rejected_orders_do_not_touch_the_ledger(self):
        ledger = ledger2000()
        with override_settings(STOKIT_MIN_ORDER_VALUE=D("5000.00")), authed(), \
                mock.patch.object(views_orders.transaction, "atomic", return_value=nullcontext()), \
                mock.patch.object(views_orders, "fetchone", return_value=USER), \
                mock.patch.object(views_orders, "fetchall", return_value=[ITEM]), \
                mock.patch.object(views_orders, "execute"), \
                mock.patch.object(views_orders, "connection", FakeConnection(ledger)):
            response = views_orders.order_post(RequestFactory().post("/api/order_post", **BEARER))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ledger.rows, [])


class LockingAndConcurrencyTests(SimpleTestCase):
    def test_placement_locks_customer_then_allocation_before_reading_usage(self):
        ledger = ledger2000()
        place(ledger, 1, "100", OCT12)
        log = ledger.sql_log
        user_lock = next(i for i, s in enumerate(log) if s.startswith("SELECT id FROM users") and s.endswith("FOR UPDATE"))
        allocation_lock = next(i for i, s in enumerate(log) if s.startswith("SELECT id, user_id, payment_amount") and s.endswith("FOR UPDATE"))
        usage_read = next(i for i, s in enumerate(log) if "COALESCE(SUM(amount),0)" in s)
        self.assertLess(user_lock, allocation_lock)
        self.assertLess(allocation_lock, usage_read)

    def test_back_to_back_purchases_from_two_orders_never_overspend(self):
        """Serial simulation only: each purchase re-reads the ledger after the previous one committed."""
        ledger = ledger2000()
        total = sum(place(ledger, i, "900", OCT12)["bonus_applied"] for i in range(1, 6))
        self.assertEqual(total, D("2000.00"))


class ConcurrentPlacementNotVerified(SimpleTestCase):
    def test_postgresql_concurrent_placements_cannot_overspend(self):
        self.skipTest("Not verified: two simultaneous PostgreSQL transactions need an approved disposable database; "
                      "only the lock order is asserted above (never test against stokit_postgres_dev).")


from legacy_api.cart_discount_testing import module_fixtures
setUpModule, tearDownModule = module_fixtures()  # no saved cart-discount row: promotion unconfigured, no DB access
