"""READ-ONLY audit of one credit allocation and its ledger. No writes, no names, no credentials printed.

Runs inside a PostgreSQL ``SET TRANSACTION READ ONLY`` transaction, so the database itself rejects any write.
Usage (from django_backend):  python scripts/read_only_audits/credit_ledger_readonly.py [payment_amount] [offer_id]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.db import connection, transaction  # noqa: E402

PAYMENT = sys.argv[1] if len(sys.argv) > 1 else "40000"
OFFER = int(sys.argv[2]) if len(sys.argv) > 2 else 2


def show(title, cursor, sql, params=()):
    cursor.execute(sql, params)
    cols = [c[0] for c in cursor.description]
    rows = cursor.fetchall()
    print("\n== %s (%d row%s)" % (title, len(rows), "" if len(rows) == 1 else "s"))
    print(" | ".join(cols))
    for row in rows:
        print(" | ".join("" if v is None else str(v) for v in row))
    return rows


with transaction.atomic():
    with connection.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        print("vendor:", connection.vendor, "| database:", connection.settings_dict.get("NAME"))
        cur.execute("SHOW transaction_read_only")
        print("transaction_read_only:", cur.fetchone()[0])
        allocs = show("allocations matching payment/offer", cur,
                      "SELECT id,user_id,offer_id,status,payment_amount,bonus_percentage,duration_months,total_credit,"
                      "used_credit,remaining_credit,start_date,end_date FROM advance_pay_allocations "
                      "WHERE payment_amount=%s AND offer_id=%s ORDER BY id", [PAYMENT, OFFER])
        for a in allocs:
            aid, uid = a[0], a[1]
            show("ledger summary for allocation %s" % aid, cur,
                 "SELECT transaction_type,COALESCE(reference_type,'') AS reference_type,COUNT(*) AS n,SUM(amount) AS total "
                 "FROM advance_pay_transactions WHERE allocation_id=%s GROUP BY 1,2 ORDER BY 1,2", [aid])
            show("latest ledger rows for allocation %s" % aid, cur,
                 "SELECT id,transaction_type,amount,reference_type,reference_id,created_at,LEFT(COALESCE(notes,''),60) AS note "
                 "FROM advance_pay_transactions WHERE allocation_id=%s ORDER BY id DESC LIMIT 12", [aid])
            show("all allocations for user_id %s (duplicates/ambiguity check)" % uid, cur,
                 "SELECT id,offer_id,status,start_date,end_date,used_credit,remaining_credit FROM advance_pay_allocations "
                 "WHERE user_id=%s ORDER BY id", [uid])
            show("recent orders for user_id %s and whether each has an ORDER_BONUS ledger row" % uid, cur,
                 "SELECT o.order_id,o.order_date,o.status,o.total_amount,"
                 "(SELECT COUNT(*) FROM advance_pay_transactions t WHERE t.reference_type='ORDER_BONUS' AND t.reference_id=o.order_id) AS ledger_rows,"
                 "(SELECT SUM(t.amount) FROM advance_pay_transactions t WHERE t.reference_type='ORDER_BONUS' AND t.reference_id=o.order_id) AS ledger_amount "
                 "FROM zg_checkout o WHERE o.email=(SELECT email FROM users WHERE id=%s) ORDER BY o.order_id DESC LIMIT 10", [uid])
        print("\nDone. Nothing was written.")
