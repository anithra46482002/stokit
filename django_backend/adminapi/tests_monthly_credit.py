"""Tests for the shared monthly credit service (legacydb.monthly_credit) and the code paths that use it.

The ledger is simulated with a small in-memory cursor, so these tests prove the RULES (allowance, month boundaries,
idempotency, agreement between surfaces) and that row locks are requested. They do NOT prove PostgreSQL concurrency
safety: that needs a disposable PostgreSQL test database (see ConcurrencyVerificationStatus below).
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from adminapi import allocation_management
from adminapi.bonus_credit import release_and_deduct_for_confirmed_order
from legacy_api import views_finance
from legacy_api.views_commerce import _build_cart_response
from legacydb import monthly_credit as mc

D = Decimal
OCT = datetime(2026, 10, 12, 10, 0, 0)
NOV = datetime(2026, 11, 5, 10, 0, 0)
EMAIL = "buyer@example.com"


def terms(payment="36000", bonus="10", months=12, start=date(2026, 10, 1), end=date(2027, 9, 30), status="ACTIVE"):
    return mc.AllocationTerms(1, 7, D(payment), D(bonus), months, start, end, status)


class FakeLedger:
    """In-memory stand-in for advance_pay_allocations / advance_pay_transactions / users."""

    def __init__(self, allocation=None):
        self.allocation = allocation
        self.rows = []
        self.allocation_updates = []
        self.sql_log = []

    def add(self, amount, kind="CREDIT_USED", ref_type=None, ref_id=None, created=OCT):
        self.rows.append({"amount": D(amount), "type": kind, "ref_type": ref_type, "ref_id": ref_id, "created": created})

    def cursor(self):
        return FakeCursor(self)

    def used(self, start=None, end=None):
        total = D("0")
        for row in self.rows:
            if row["type"] != "CREDIT_USED" or row["ref_type"] == mc.MANUAL_ADJUSTMENT_REFERENCE_TYPE:
                continue
            if (start and row["created"] < start) or (end and row["created"] >= end):
                continue
            total += row["amount"]
        return total

    def order_rows(self):
        return [r for r in self.rows if r["ref_type"] == mc.ORDER_REFERENCE_TYPE]


class FakeCursor:
    def __init__(self, ledger):
        self.ledger = ledger
        self._rows = []

    def execute(self, sql, params=None):
        ledger, p = self.ledger, list(params or [])
        s = " ".join(sql.split())
        ledger.sql_log.append(s)
        if s.startswith("SELECT user_id FROM advance_pay_transactions WHERE reference_type=%s"):
            self._rows = [(7,) for r in ledger.rows
                          if r["type"] == "CREDIT_USED" and r["ref_type"] == p[0] and r["ref_id"] == p[1]][:1]
        elif s.startswith("SELECT id FROM users WHERE id=%s"):
            self._rows = [(7,)] if p and p[0] == 7 else []
        elif s.startswith("SELECT id FROM users"):
            self._rows = [(7,)] if p and p[0] == EMAIL else []
        elif s.startswith("SELECT id, user_id, payment_amount"):
            a = ledger.allocation
            self._rows = [(a.allocation_id, a.user_id, a.payment_amount, a.bonus_percentage, a.duration_months,
                           a.start_date, a.end_date, a.status)] if a else []
        elif "COALESCE(SUM(amount),0)" in s and "created_at >=" in s:
            self._rows = [(ledger.used(p[2], p[3]),)]
        elif "COALESCE(SUM(amount),0)" in s:
            self._rows = [(ledger.used(),)]
        elif s.startswith("SELECT reference_id, SUM(amount)"):
            grouped = {}
            for r in ledger.order_rows():
                total, first = grouped.get(r["ref_id"], (D("0"), r["created"]))
                grouped[r["ref_id"]] = (total + r["amount"], min(first, r["created"]))
            self._rows = [(k, v[0], v[1]) for k, v in grouped.items()]
        elif s.startswith("SELECT amount FROM advance_pay_transactions WHERE reference_type=%s AND reference_id=%s"):
            self._rows = [(r["amount"],) for r in ledger.rows
                          if r["type"] == "CREDIT_USED" and r["ref_type"] == p[0] and r["ref_id"] == p[1]][:1]
        elif s.startswith("INSERT INTO advance_pay_transactions"):
            ledger.add(p[2], "CREDIT_USED", ref_type=p[4], ref_id=p[3], created=p[6])
            self._rows = []
        elif s.startswith("UPDATE advance_pay_allocations"):
            ledger.allocation_updates.append(p[0])
            self._rows = []
        else:
            raise AssertionError("unexpected SQL in test: " + s)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


def ledger_with_october_usage(amount="2500"):
    ledger = FakeLedger(terms())
    ledger.add(amount, ref_type=mc.ORDER_REFERENCE_TYPE, ref_id=1, created=datetime(2026, 10, 3, 9, 0))
    return ledger


class MonthlyCreditRuleTests(SimpleTestCase):
    def test_formula_36000_at_10_percent_for_12_months(self):
        self.assertEqual(mc.monthly_credit_release(D("36000"), D("10")), D("3600.00"))
        self.assertEqual(mc.total_credit(D("36000"), D("10"), 12), D("43200.00"))

    def test_money_is_rounded_half_up_to_two_places(self):
        self.assertEqual(mc.monthly_credit_release(D("33333"), D("7.5")), D("2499.98"))

    def test_usage_reduces_only_the_current_allowance(self):
        state = mc.evaluate(terms(), D("2500"), D("2500"), date(2026, 10, 12))
        self.assertEqual((state.monthly_credit_release, state.used_this_month, state.remaining_this_month),
                         (D("3600.00"), D("2500.00"), D("1100.00")))

    def test_spending_the_remainder_leaves_zero_and_more_is_rejected(self):
        ledger = ledger_with_october_usage("2500")
        cursor = ledger.cursor()
        first = mc.commit_order_credit(cursor, 101, 7, D("1100"), now=OCT)
        self.assertEqual((first["bonus_applied"], first["remaining_bonus"]), (D("1100.00"), D("0.00")))
        self.assertEqual(ledger.used(), D("3600.00"))
        second = mc.commit_order_credit(cursor, 102, 7, D("500"), now=OCT)
        self.assertEqual(second["bonus_applied"], D("0.00"))
        self.assertEqual(second["credit_status"], "no_bonus_applied")
        self.assertEqual(ledger.used(), D("3600.00"))
        self.assertEqual(len(ledger.order_rows()), 2)  # only the original and the 1,100 deduction

    def test_next_month_starts_with_a_fresh_allowance_independent_of_last_month(self):
        ledger = ledger_with_october_usage("3600")
        cursor = ledger.cursor()
        state, _ = mc.load_state(cursor, 7, date(2026, 11, 5))
        self.assertEqual((state.used_this_month, state.remaining_this_month), (D("0.00"), D("3600.00")))
        result = mc.commit_order_credit(cursor, 103, 7, D("1000"), now=NOV)
        self.assertEqual((result["bonus_applied"], result["remaining_bonus"]), (D("1000.00"), D("2600.00")))
        state, _ = mc.load_state(cursor, 7, date(2026, 11, 20))
        self.assertEqual(state.used_this_month, D("1000.00"))  # October's 3,600 is not part of November

    def test_unused_credit_is_carried_forward_once_as_its_unused_remainder(self):
        ledger = ledger_with_october_usage("1000")
        cursor = ledger.cursor()
        state, _ = mc.load_state(cursor, 7, date(2026, 11, 5))
        # October: 3,600 allowance - 1,000 used = 2,600 unused (not the original 3,600) carries into November.
        self.assertEqual((state.monthly_credit_release, state.carried_forward), (D("3600.00"), D("2600.00")))
        self.assertEqual((state.available_credit, state.remaining_this_month), (D("6200.00"), D("6200.00")))
        result = mc.commit_order_credit(cursor, 104, 7, D("9000"), now=NOV)
        self.assertEqual(result["carried_forward"], D("2600.00"))
        self.assertEqual(result["bonus_applied"], D("6200.00"))  # the 2,800 excess is paid by the customer
        self.assertEqual(result["amount_payable"], D("2800.00"))

    def test_total_credit_is_never_the_monthly_allowance(self):
        ledger = FakeLedger(terms())
        result = mc.commit_order_credit(ledger.cursor(), 105, 7, D("50000"), now=OCT)
        self.assertEqual(result["total_credit"], D("43200.00"))
        self.assertEqual(result["bonus_applied"], D("3600.00"))

    def test_customer_without_an_eligible_allocation_gets_zero(self):
        ledger = FakeLedger(None)
        cursor = ledger.cursor()
        self.assertIsNone(mc.commit_order_credit(cursor, 106, 7, D("500"), now=OCT))
        self.assertEqual(mc.customer_credit_context(cursor, EMAIL, date(2026, 10, 12))["state"].remaining_this_month, D("0.00"))
        self.assertEqual(mc.customer_credit_context(cursor, "nobody@example.com", date(2026, 10, 12))["state"].remaining_this_month, D("0.00"))
        self.assertEqual(ledger.rows, [])

    def test_expired_not_started_inactive_and_out_of_duration_allocations_cannot_spend(self):
        cases = {
            "expired": (terms(end=date(2026, 10, 5)), OCT),
            "not_started": (terms(start=date(2026, 11, 1), end=date(2027, 10, 31)), OCT),
            "inactive": (terms(status="CANCELLED"), OCT),
            "expired_duration": (terms(months=1), NOV),
        }
        for expected, (allocation, now) in cases.items():
            with self.subTest(expected):
                ledger = FakeLedger(allocation)
                result = mc.commit_order_credit(ledger.cursor(), 107, 7, D("500"), now=now)
                self.assertEqual(result["bonus_applied"], D("0.00"))
                self.assertEqual(ledger.rows, [])
                self.assertEqual(mc.evaluate(allocation, D("0"), D("0"), now.date()).remaining_this_month, D("0.00"))

    def test_duplicate_order_confirmation_is_idempotent(self):
        ledger = FakeLedger(terms())
        cursor = ledger.cursor()
        first = mc.commit_order_credit(cursor, 108, 7, D("2000"), now=OCT)
        again = mc.commit_order_credit(cursor, 108, 7, D("2000"), now=OCT)
        self.assertFalse(first["duplicate"])
        self.assertTrue(again["duplicate"])
        self.assertEqual(again["bonus_applied"], first["bonus_applied"])
        self.assertEqual(len(ledger.order_rows()), 1)
        self.assertEqual(ledger.allocation_updates, [D("2000.00")])

    def test_repeat_confirmation_cannot_create_a_new_deduction(self):
        ledger = FakeLedger(terms())
        result = mc.commit_order_credit(ledger.cursor(), 109, 7, D("2000"), now=OCT, allow_new=False)
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["bonus_applied"], D("0.00"))
        self.assertEqual(ledger.rows, [])

    def test_negative_and_invalid_purchase_values_are_rejected(self):
        ledger = FakeLedger(terms())
        for bad in (D("-1"), "abc", D("NaN"), None, True):
            with self.subTest(bad=bad):
                with self.assertRaises(mc.CreditLimitError):
                    mc.commit_order_credit(ledger.cursor(), 110, 7, bad, now=OCT)
        self.assertEqual(ledger.rows, [])

    def test_invalid_offer_values_give_no_credit_instead_of_crashing(self):
        state = mc.evaluate(terms(payment="-5"), D("0"), D("0"), date(2026, 10, 12))
        self.assertEqual((state.code, state.remaining_this_month, state.eligible), ("invalid", D("0.00"), False))


class MonthBoundaryTests(SimpleTestCase):
    def test_usage_is_split_at_midnight_of_the_first_day(self):
        ledger = FakeLedger(terms())
        ledger.add("100", created=datetime(2026, 10, 31, 23, 59, 59))
        ledger.add("40", created=datetime(2026, 11, 1, 0, 0, 0))
        cursor = ledger.cursor()
        self.assertEqual(mc.usage_in_month(cursor, 1, date(2026, 10, 31)), D("100.00"))
        self.assertEqual(mc.usage_in_month(cursor, 1, date(2026, 11, 1)), D("40.00"))

    @staticmethod
    def _frozen(moment_utc):
        class Frozen(datetime):
            @classmethod
            def now(cls, tz=None):
                return moment_utc.astimezone(tz) if tz else moment_utc.replace(tzinfo=None)
        return Frozen

    def test_business_month_follows_the_configured_time_zone_not_the_os_clock(self):
        moment = datetime(2026, 10, 31, 19, 0, 0, tzinfo=dt_timezone.utc)  # 00:30 on 1 Nov in Kolkata
        with patch("legacydb.monthly_credit.datetime", self._frozen(moment)):
            with override_settings(TIME_ZONE="Asia/Kolkata"):
                self.assertEqual(mc.local_today(), date(2026, 11, 1))
            with override_settings(TIME_ZONE="UTC"):
                self.assertEqual(mc.local_today(), date(2026, 10, 31))

    def test_reporting_period_defaults_to_the_business_month(self):
        moment = datetime(2026, 10, 31, 19, 0, 0, tzinfo=dt_timezone.utc)
        with patch("legacydb.monthly_credit.datetime", self._frozen(moment)), override_settings(TIME_ZONE="Asia/Kolkata"):
            start, end, as_of = allocation_management.reporting_period({})
        self.assertEqual((start, end, as_of), (date(2026, 11, 1), date(2026, 12, 1), date(2026, 11, 1)))


class LedgerSemanticsTests(SimpleTestCase):
    """Documented rule: only CREDIT_USED rows that are not MANUAL_ADJUSTMENT reduce the monthly allowance.

    CREDIT_ADDED rows (manual top-ups) never raise it. The ledger has no refund type, so refunds cannot be
    told apart from other CREDIT_ADDED rows and are NOT credited back (reported as a warning by the admin API).
    """

    def test_manual_adjustments_and_added_credit_do_not_change_the_allowance(self):
        ledger = FakeLedger(terms())
        ledger.add("1000", ref_type=mc.ORDER_REFERENCE_TYPE, ref_id=1)
        ledger.add("700", "CREDIT_USED", ref_type=mc.MANUAL_ADJUSTMENT_REFERENCE_TYPE)
        ledger.add("500", "CREDIT_ADDED", ref_type=mc.MANUAL_ADJUSTMENT_REFERENCE_TYPE)
        ledger.add("300", "CREDIT_ADDED")
        state, _ = mc.load_state(ledger.cursor(), 7, date(2026, 10, 12))
        self.assertEqual((state.used_this_month, state.remaining_this_month), (D("1000.00"), D("2600.00")))

    def test_usage_classification(self):
        self.assertTrue(mc.is_valid_usage("CREDIT_USED", "ORDER_BONUS"))
        self.assertTrue(mc.is_valid_usage("credit_used", None))
        self.assertFalse(mc.is_valid_usage("CREDIT_USED", "MANUAL_ADJUSTMENT"))
        self.assertFalse(mc.is_valid_usage("CREDIT_ADDED", None))
        self.assertFalse(mc.is_valid_usage("MONTHLY_RELEASE", None))

    def test_sum_valid_usage_filters_by_month(self):
        tx = [SimpleNamespace(transaction_type="CREDIT_USED", amount=D("100"), reference_type="ORDER_BONUS", created_at=datetime(2026, 10, 2)),
              SimpleNamespace(transaction_type="CREDIT_USED", amount=D("50"), reference_type="ORDER_BONUS", created_at=datetime(2026, 11, 2)),
              SimpleNamespace(transaction_type="CREDIT_ADDED", amount=D("999"), reference_type=None, created_at=datetime(2026, 10, 2))]
        self.assertEqual(mc.sum_valid_usage(tx, datetime(2026, 10, 1), datetime(2026, 11, 1)), D("100.00"))
        self.assertEqual(mc.sum_valid_usage(tx), D("150.00"))


class SurfacesAgreeTests(SimpleTestCase):
    """Cart, customer credit report, admin table and order confirmation must report the same numbers."""

    def test_all_surfaces_show_the_same_remaining_credit(self):
        ledger = ledger_with_october_usage("2500")
        context = mc.customer_credit_context(ledger.cursor(), EMAIL, date(2026, 10, 12))

        with patch("legacy_api.views_finance.current_credit_context", return_value=context):
            monthly, carried, available = views_finance.current_available_credit({"email": EMAIL})
        self.assertEqual((monthly, carried, available), (3600.0, 0.0, 1100.0))

        item = {"sub_total": 5000.0, "discounted_subtotal": 5000.0, "discount_amount": 0.0, "discount_percent": 0.0, "quantity": 1}
        summary = _build_cart_response("u", [], [item], 0, credit_release=monthly, available_credit=available)["cart_items"]["final_summary"]
        self.assertEqual((summary["credit_applied"], summary["available_credit"], summary["carry_forward_to_next_month"]), (1100.0, 1100.0, 0.0))

        row = SimpleNamespace(id=1, offer_id=1, user_id=7, payment_amount=D("36000"), bonus_percentage=D("10"), duration_months=12,
                              total_credit=D("99999"), used_credit=D("2500"), remaining_credit=D("0"), start_date=date(2026, 10, 1),
                              end_date=date(2027, 9, 30), payment_date=date(2026, 10, 1), payment_reference="", notes="", status="ACTIVE")
        usage = [SimpleNamespace(transaction_type="CREDIT_USED", amount=D("2500"), reference_type="ORDER_BONUS", created_at=datetime(2026, 10, 3, 9, 0))]
        with patch("adminapi.allocation_management.AdvancePayTransaction") as model:
            model.objects.filter.return_value.order_by.return_value = usage
            admin = allocation_management.serialize(row, SimpleNamespace(username="u", fullname="U"), SimpleNamespace(offer_name="Offer"),
                                                    date(2026, 10, 1), date(2026, 11, 1), date(2026, 10, 12))
        self.assertEqual((admin["monthly_credit_release"], admin["remaining_this_month"], admin["used_this_month"]), ("3600.00", "1100.00", "2500.00"))
        self.assertEqual((admin["total_credit"], admin["stored_total_credit"]), ("43200.00", "99999.00"))  # stored total is not trusted

        confirmed = release_and_deduct_for_confirmed_order(ledger.cursor(), 201, EMAIL, D("5000"), today=date(2026, 10, 12))
        self.assertEqual(float(confirmed["bonus_applied"]), available)
        self.assertEqual(confirmed["remaining_bonus"], D("0.00"))


class LockingTests(SimpleTestCase):
    def test_confirmation_locks_customer_and_allocation_before_reading_usage(self):
        ledger = FakeLedger(terms())
        release_and_deduct_for_confirmed_order(ledger.cursor(), 301, EMAIL, D("100"), today=date(2026, 10, 12))
        log = ledger.sql_log
        user_lock = next(i for i, s in enumerate(log) if s.startswith("SELECT id FROM users") and s.endswith("FOR UPDATE"))
        allocation_lock = next(i for i, s in enumerate(log) if s.startswith("SELECT id, user_id, payment_amount") and s.endswith("FOR UPDATE"))
        first_usage_read = next(i for i, s in enumerate(log) if "COALESCE(SUM(amount),0)" in s)
        self.assertLess(user_lock, allocation_lock)
        self.assertLess(allocation_lock, first_usage_read)

    def test_read_only_state_loading_takes_no_locks(self):
        ledger = FakeLedger(terms())
        mc.customer_credit_context(ledger.cursor(), EMAIL, date(2026, 10, 12))
        self.assertFalse(any("FOR UPDATE" in s for s in ledger.sql_log))


class ConcurrencyVerificationStatus(SimpleTestCase):
    def test_postgresql_concurrent_purchases_cannot_overspend(self):
        """Needs a disposable PostgreSQL test database: two transactions confirming different orders for one allocation.

        The tests above only show that FOR UPDATE locks are requested in the right order against a simulated ledger;
        they do not demonstrate PostgreSQL's blocking behaviour. Run the real check only after a disposable test
        database has been approved (never against stokit_postgres_dev or production data).
        """
        self.skipTest("PostgreSQL concurrency not verified: no disposable PostgreSQL test database approved/available.")


from legacy_api.cart_discount_testing import module_fixtures
setUpModule, tearDownModule = module_fixtures()  # no saved cart-discount row: promotion unconfigured, no DB access
