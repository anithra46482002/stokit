"""READ-ONLY report: orders that should have consumed monthly credit but have no ledger row.

Writes nothing (the session is set read-only). Output is for review by a person; any correction must be a separately
approved, audited step. Run from django_backend:  python scripts/credit_reconciliation_report.py

For every ACTIVE allocation it lists orders by that customer placed on/after the allocation start with no
ORDER_BONUS ledger row, oldest first, with a chronological INDICATIVE simulation of the credit the rules would have
applied. Indicative only: the exact pre-credit total (GST, delivery, VIP) of old orders is not stored, so the order's
stored total_amount (item subtotal) is used. Cancelled orders are listed but not simulated: the repository documents
no cancellation/refund credit policy, and none is invented here.
"""
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.db import connection, transaction  # noqa: E402
from legacydb import monthly_credit as mc  # noqa: E402


def main():
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SELECT a.id, a.user_id, u.fullname, u.email, a.start_date FROM advance_pay_allocations a "
                    "JOIN users u ON u.id=a.user_id WHERE UPPER(a.status)='ACTIVE' ORDER BY a.id")
        allocations = cur.fetchall()
        print("ACTIVE allocations: %d\n" % len(allocations))
        for aid, uid, name, email, start in allocations:
            cur.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM advance_pay_transactions WHERE allocation_id=%s AND reference_type=%s", [aid, mc.ORDER_REFERENCE_TYPE])
            rows, total = cur.fetchone()
            print("Allocation %s - %s (user %s): %s ORDER_BONUS ledger rows totalling %s" % (aid, name, uid, rows, total))
            cur.execute("SELECT order_id, order_date, status, total_amount FROM zg_checkout c WHERE lower(c.email)=lower(%s) AND c.order_date >= %s "
                        "AND NOT EXISTS (SELECT 1 FROM advance_pay_transactions t WHERE t.reference_type=%s AND t.reference_id=c.order_id) ORDER BY c.order_date, c.order_id",
                        [email, start, mc.ORDER_REFERENCE_TYPE])
            missing = cur.fetchall()
            print("  orders since %s with no ledger row: %d" % (start, len(missing)))
            cur.execute("SELECT id, user_id, payment_amount, bonus_percentage, duration_months, start_date, end_date, status FROM advance_pay_allocations WHERE id=%s", [aid])
            terms = mc.AllocationTerms(*cur.fetchone())
            used_by_month = {}
            for order_id, placed, status, amount in missing:
                if str(status).lower() == "cancelled":
                    print("    order %s  %s  %-10s %10s   not simulated (no documented cancellation policy)" % (order_id, placed.strftime("%Y-%m-%d %H:%M"), status, amount))
                    continue
                month = placed.strftime("%Y-%m")
                used = used_by_month.get(month, Decimal("0"))
                lifetime = sum(used_by_month.values(), Decimal("0"))
                state = mc.evaluate(terms, used, lifetime, placed.date())
                applied = min(state.remaining_this_month, Decimal(str(amount)))
                used_by_month[month] = used + applied
                print("    order %s  %s  %-10s %10s   indicative credit %s" % (order_id, placed.strftime("%Y-%m-%d %H:%M"), status, amount, applied))
            print("  indicative total credit not recorded: %s\n" % sum(used_by_month.values(), Decimal("0")))
        print("No data was modified.")


if __name__ == "__main__":
    main()
