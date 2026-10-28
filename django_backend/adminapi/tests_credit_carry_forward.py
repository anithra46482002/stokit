"""Monthly credit remaining balance, purchase deduction and carry-forward (Examples A-F of the credit spec).

A Rs 2,000 monthly allowance is 20,000 x 10% (12 months from Oct 2026). Everything runs through the shared
legacydb.monthly_credit service with the in-memory ledger from tests_monthly_credit (no database access).
"""
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from adminapi.tests_monthly_credit import EMAIL, FakeLedger, terms
from legacy_api import views_finance
from legacy_api.views_commerce import _build_cart_response
from legacydb import monthly_credit as mc

D = Decimal
OCT = datetime(2026, 10, 12, 10, 0, 0)
NOV = datetime(2026, 11, 5, 10, 0, 0)
DEC = datetime(2026, 12, 8, 10, 0, 0)


def ledger2000(**kw):
    return FakeLedger(terms(payment="20000", bonus="10", **kw))


def buy(ledger, order_id, amount, now):
    return mc.commit_order_credit(ledger.cursor(), order_id, 7, D(amount), now=now)


def state(ledger, now):
    return mc.load_state(ledger.cursor(), 7, now.date())[0]


class RemainingAfterPurchasesTests(SimpleTestCase):
    def test_2000_allowance_minus_1500_purchase_leaves_500(self):
        ledger = ledger2000()
        self.assertEqual(state(ledger, OCT).remaining_this_month, D("2000.00"))
        result = buy(ledger, 1, "1500", OCT)
        self.assertEqual((result["bonus_applied"], result["remaining_bonus"]), (D("1500.00"), D("500.00")))
        current = state(ledger, OCT)
        self.assertEqual((current.monthly_credit_release, current.remaining_this_month), (D("2000.00"), D("500.00")))

    def test_second_purchase_reduces_the_same_months_balance_to_zero(self):
        ledger = ledger2000()
        buy(ledger, 1, "1500", OCT)
        buy(ledger, 2, "500", OCT)
        self.assertEqual(state(ledger, OCT).remaining_this_month, D("0.00"))

    def test_purchase_above_the_remaining_credit_never_goes_negative(self):
        ledger = ledger2000()
        buy(ledger, 1, "1500", OCT)
        result = buy(ledger, 2, "700", OCT)
        self.assertEqual((result["bonus_applied"], result["amount_payable"]), (D("500.00"), D("200.00")))
        self.assertEqual(state(ledger, OCT).remaining_this_month, D("0.00"))
        self.assertEqual(buy(ledger, 3, "300", OCT)["bonus_applied"], D("0.00"))
        self.assertEqual(ledger.used(), D("2000.00"))  # the excess is never taken from another month

    def test_zero_never_below_zero_even_if_the_ledger_overspent_in_the_past(self):
        current = mc.evaluate(terms(payment="20000", bonus="10"), D("2500"), D("2500"), date(2026, 10, 12))
        self.assertEqual(current.remaining_this_month, D("0.00"))


class CarryForwardTests(SimpleTestCase):
    def test_unused_500_carries_into_november_and_adds_to_the_allocation(self):
        ledger = ledger2000()
        buy(ledger, 1, "1500", OCT)
        nov = state(ledger, NOV)
        self.assertEqual((nov.monthly_credit_release, nov.carried_forward), (D("2000.00"), D("500.00")))
        self.assertEqual((nov.available_credit, nov.remaining_this_month), (D("2500.00"), D("2500.00")))

    def test_1000_november_purchase_leaves_1500(self):
        ledger = ledger2000()
        buy(ledger, 1, "1500", OCT)
        result = buy(ledger, 2, "1000", NOV)
        self.assertEqual(result["remaining_bonus"], D("1500.00"))
        self.assertEqual(state(ledger, NOV).remaining_this_month, D("1500.00"))

    def test_a_month_without_purchases_carries_its_whole_allowance(self):
        nov = state(ledger2000(), NOV)
        self.assertEqual((nov.carried_forward, nov.available_credit, nov.remaining_this_month),
                         (D("2000.00"), D("4000.00"), D("4000.00")))

    def test_multiple_months_count_each_purchase_once_and_never_re_add_an_allocation(self):
        ledger = ledger2000()
        buy(ledger, 1, "1500", OCT)
        buy(ledger, 2, "1000", NOV)
        dec = state(ledger, DEC)
        # Oct + Nov allocations (4,000) - 2,500 used = 1,500 carried; December adds 2,000.
        self.assertEqual((dec.carried_forward, dec.available_credit, dec.remaining_this_month),
                         (D("1500.00"), D("3500.00"), D("3500.00")))
        self.assertEqual(mc.carry_forward_into(terms(payment="20000", bonus="10"), date(2026, 12, 8), D("2500")), D("1500.00"))

    def test_carry_forward_lapses_when_the_offer_duration_ends(self):
        ledger = ledger2000(months=2, end=date(2026, 11, 30))
        buy(ledger, 1, "1500", OCT)
        self.assertEqual(state(ledger, NOV).remaining_this_month, D("2500.00"))
        december = state(ledger, DEC)
        self.assertEqual((december.code, december.carried_forward, december.remaining_this_month), ("expired", D("0.00"), D("0.00")))

    def test_the_start_month_has_nothing_to_carry(self):
        self.assertEqual(state(ledger2000(), OCT).carried_forward, D("0.00"))


class IdempotencyEligibilityAndIsolationTests(SimpleTestCase):
    def test_repeating_an_order_or_refreshing_does_not_deduct_again(self):
        ledger = ledger2000()
        buy(ledger, 1, "1500", OCT)
        again = buy(ledger, 1, "1500", OCT)
        self.assertTrue(again["duplicate"])
        for _ in range(3):
            self.assertEqual(state(ledger, OCT).remaining_this_month, D("500.00"))
        self.assertEqual(len(ledger.order_rows()), 1)
        self.assertEqual(ledger.used(), D("1500.00"))

    def test_repeat_confirmation_of_an_unpaid_order_never_creates_a_new_deduction(self):
        ledger = ledger2000()
        result = mc.commit_order_credit(ledger.cursor(), 9, 7, D("700"), now=OCT, allow_new=False)
        self.assertEqual(result["bonus_applied"], D("0.00"))
        self.assertEqual(ledger.order_rows(), [])

    def test_only_valid_ledger_usage_counts_manual_adjustments_and_added_credit_do_not(self):
        ledger = ledger2000()
        ledger.add("900", kind="CREDIT_USED", ref_type=mc.MANUAL_ADJUSTMENT_REFERENCE_TYPE, created=OCT)
        ledger.add("700", kind="CREDIT_ADDED", created=OCT)
        self.assertEqual(state(ledger, OCT).remaining_this_month, D("2000.00"))
        self.assertEqual(state(ledger, NOV).carried_forward, D("2000.00"))

    def test_customers_are_independent(self):
        first, second = ledger2000(), ledger2000()
        buy(first, 1, "1500", OCT)
        self.assertEqual(state(first, OCT).remaining_this_month, D("500.00"))
        self.assertEqual(state(second, OCT).remaining_this_month, D("2000.00"))
        self.assertEqual(state(second, NOV).carried_forward, D("2000.00"))


class CustomerSummaryTests(SimpleTestCase):
    USER = {"email": EMAIL, "delivery_charges": 0, "gst_percentage": None, "vip_discount": None, "vip_percentage": 0}

    def context(self, ledger, now):
        cursor = ledger.cursor()
        with patch.object(views_finance, "connection") as conn:
            conn.cursor.return_value.__enter__.return_value = cursor
            return views_finance.current_credit_context(self.USER)

    def test_credit_release_summary_shows_remaining_and_keeps_the_allocation_separate(self):
        ledger = ledger2000()
        buy(ledger, 1, "1500", OCT)
        with patch.object(mc, "local_today", return_value=OCT.date()):
            ctx = self.context(ledger, OCT)
        self.assertEqual(ctx["state"].remaining_this_month, D("500.00"))
        self.assertEqual(ctx["state"].monthly_credit_release, D("2000.00"))
        from django.test import RequestFactory
        from legacy_api.tests_auth import BEARER, authed, body_of
        with authed(), patch.object(views_finance, "current_credit_context", return_value=ctx), \
                patch.object(views_finance, "fetchone", return_value=self.USER), \
                patch.object(views_finance, "fetchall", return_value=[]):
            body = body_of(views_finance.credit_release(RequestFactory().get("/api/credit_release", **BEARER)))
        user = body["user"]
        self.assertEqual((user["current_month_cr"], user["monthly_remaining_credit"], user["available_credit"]),
                         (500.0, 500.0, 2000.0))
        self.assertEqual((user["monthly_credit_release"], user["monthly_used_credit"], user["carried_forward_credit"]),
                         (2000.0, 1500.0, 0.0))

    def test_order_statement_rows_use_the_carried_forward_balance(self):
        ledger = ledger2000()
        buy(ledger, 1, "1500", OCT)
        with patch.object(mc, "local_today", return_value=NOV.date()):
            ctx = self.context(ledger, NOV)
        row = {"order_id": 2, "order_date": NOV.date(), "order_datetime": NOV, "status": "pending", "payment_method": None,
               "discounted_subtotal": 0, "non_discounted_subtotal": 1000, "total_amount": 1000}
        with patch.object(views_finance, "_order_gst", return_value=(D("0"), "none")):
            out, summary = views_finance._credit_release_report(self.USER, [row], ctx)
        line = out[0]
        self.assertEqual((line["monthly_credit_released"], line["carried_forward_from_previous_month"],
                          line["total_available_credit"]), (2000.0, 500.0, 2500.0))
        self.assertEqual(ctx["state"].remaining_this_month, D("2500.00"))

    def test_cart_gets_the_carried_forward_and_available_credit(self):
        with patch.object(views_finance, "current_credit_context") as ctx:
            ctx.return_value = {"state": mc.evaluate(terms(payment="20000", bonus="10"), D("0"), D("1500"), date(2026, 11, 5))}
            monthly, carried, remaining = views_finance.current_available_credit(self.USER)
        self.assertEqual((monthly, carried, remaining), (2000.0, 500.0, 2500.0))
        summary = _build_cart_response("alice", [], [], 0, credit_release=monthly, available_credit=remaining,
                                       carried_forward=carried)["cart_items"]["final_summary"]
        self.assertEqual((summary["credit_release"], summary["carried_forward_from_previous_month"], summary["available_credit"]),
                         (0.0, 500.0, 2500.0))
        self.assertEqual(summary["monthly_credit_release"], 2000.0)


class StatedScenarioTests(SimpleTestCase):
    """Advance 20,000 at 10% for 12 months: 2,000 a month (Scenarios A-E of the customer summary spec)."""
    USER = CustomerSummaryTests.USER

    def summary(self, ledger, now):
        from django.test import RequestFactory
        from legacy_api.tests_auth import BEARER, authed, body_of
        cursor = ledger.cursor()
        with patch.object(views_finance, "connection") as conn, patch.object(mc, "local_today", return_value=now.date()):
            conn.cursor.return_value.__enter__.return_value = cursor
            with authed(), patch.object(views_finance, "fetchone", return_value=self.USER), \
                    patch.object(views_finance, "fetchall", return_value=[]):
                return body_of(views_finance.credit_release(RequestFactory().get("/api/credit_release", **BEARER))), mc.load_state(cursor, 7, now.date())[0]

    def test_api_fields_and_remaining_after_one_and_two_purchases(self):
        ledger = ledger2000()
        body, _ = self.summary(ledger, OCT)
        self.assertEqual(body["user"]["remaining_credit"], 2000.0)
        buy(ledger, 1, "1000", OCT)
        user = self.summary(ledger, OCT)[0]["user"]
        self.assertEqual((user["monthly_credit_release"], user["carried_forward_credit"], user["available_credit"],
                          user["used_credit"], user["remaining_credit"], user["current_month_cr"]),
                         (2000.0, 0.0, 2000.0, 1000.0, 1000.0, 1000.0))
        buy(ledger, 2, "400", OCT)
        self.assertEqual(self.summary(ledger, OCT)[0]["user"]["remaining_credit"], 600.0)

    def test_two_1000_purchases_leave_zero_and_refreshing_never_resets_or_deducts(self):
        ledger = ledger2000()
        buy(ledger, 1, "1000", OCT)
        buy(ledger, 2, "1000", OCT)
        for _ in range(3):
            self.assertEqual(self.summary(ledger, OCT)[0]["user"]["remaining_credit"], 0.0)
        self.assertEqual(buy(ledger, 3, "500", OCT)["bonus_applied"], D("0.00"))
        self.assertEqual(ledger.used(), D("2000.00"))

    def test_november_with_no_purchase_has_4000_and_with_1000_unused_has_3000(self):
        self.assertEqual(self.summary(ledger2000(), NOV)[0]["user"]["available_credit"], 4000.0)
        ledger = ledger2000()
        buy(ledger, 1, "1000", OCT)
        user = self.summary(ledger, NOV)[0]["user"]
        self.assertEqual((user["carried_forward_credit"], user["available_credit"], user["remaining_credit"]), (1000.0, 3000.0, 3000.0))
        buy(ledger, 2, "1000", NOV)
        user = self.summary(ledger, NOV)[0]["user"]
        self.assertEqual((user["used_credit"], user["remaining_credit"]), (1000.0, 2000.0))

    def test_history_rows_keep_each_months_own_opening_and_closing_balance(self):
        ledger = ledger2000()
        buy(ledger, 1, "1000", OCT)

        cursor = ledger.cursor()
        with patch.object(views_finance, "connection") as conn, patch.object(mc, "local_today", return_value=NOV.date()):
            conn.cursor.return_value.__enter__.return_value = cursor
            ctx = views_finance.current_credit_context(self.USER)
        base = {"order_datetime": NOV, "status": "pending", "payment_method": None, "discounted_subtotal": 0, "total_amount": 1000}
        rows = [dict(base, order_id=1, order_date=OCT.date(), non_discounted_subtotal=1000),
                dict(base, order_id=2, order_date=NOV.date(), non_discounted_subtotal=1000)]
        with patch.object(views_finance, "_order_gst", return_value=(D("0"), "none")):
            out, summary = views_finance._credit_release_report(self.USER, rows, ctx)
        october, november = out
        self.assertEqual((october["carried_forward_from_previous_month"], october["total_available_credit"],
                          october["monthly_credit_remaining_after_order"], october["closing_balance_carried_forward"]),
                         (0.0, 2000.0, 1000.0, 1000.0))
        self.assertEqual((november["carried_forward_from_previous_month"], november["total_available_credit"],
                          november["closing_balance_carried_forward"]), (1000.0, 3000.0, 3000.0))
        self.assertEqual(summary["final_closing_balance"], 3000.0)

    def test_another_customers_purchases_do_not_change_this_balance(self):
        mine, other = ledger2000(), ledger2000()
        buy(other, 1, "2000", OCT)
        self.assertEqual(self.summary(mine, OCT)[0]["user"]["remaining_credit"], 2000.0)


from legacy_api.cart_discount_testing import module_fixtures
setUpModule, tearDownModule = module_fixtures()  # no saved cart-discount row: promotion unconfigured, no DB access
