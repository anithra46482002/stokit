"""Isolated-PostgreSQL integration checks for monthly credit (order placement -> ledger -> admin figures).

SAFETY
* Creates a brand-new scratch database named stokit_credit_isolated_<timestamp> on the configured server, builds it
  from docs/STOKIT_COMPLETE_DDL_CANDIDATE.sql, seeds SYNTHETIC rows only, and DROPS it at the end.
* The configured development/production database is never opened by this script: DB_NAME is overridden in the
  process environment before Django starts, and every destructive statement is guarded by assert_scratch().
* No credentials are printed.

Usage (from django_backend):  python scripts/isolated_pg/credit_isolated_pg.py [--keep]
"""
import copy
import json
import os
import sys
import threading
import time
import unittest
from datetime import date
from decimal import Decimal as D
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
PREFIX = "stokit_credit_isolated_"
DB_NAME = PREFIX + time.strftime("%Y%m%d_%H%M%S")
os.environ["DB_NAME"] = DB_NAME  # real environment variables outrank the .env file (settings.py: override=False)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from django.db import connection, connections, transaction  # noqa: E402
from django.db.utils import ConnectionHandler  # noqa: E402
from django.test import RequestFactory, override_settings  # noqa: E402

from adminapi.bonus_credit import release_and_deduct_for_confirmed_order  # noqa: E402
from legacy_api import views_commerce, views_orders  # noqa: E402
from legacy_api.tests_auth import BEARER, authed  # noqa: E402
from legacydb import monthly_credit as mc  # noqa: E402

rf = RequestFactory()
KEEP = "--keep" in sys.argv
EMAIL = "iso.customer@example.invalid"
USERNAME = "iso_customer"


def assert_scratch():
    name = connection.settings_dict["NAME"]
    assert name == DB_NAME and name.startswith(PREFIX), "refusing to touch non-scratch database %r" % name


def admin_connection():
    cfg = copy.deepcopy(connections.settings["default"])
    cfg["NAME"] = "postgres"
    return ConnectionHandler({"default": cfg})["default"]


def provision():
    assert DB_NAME.startswith(PREFIX)
    admin = admin_connection()
    with admin.cursor() as c:
        c.execute('CREATE DATABASE "%s"' % DB_NAME)
    admin.close()
    assert_scratch()
    with open(os.path.join(ROOT, "docs", "STOKIT_COMPLETE_DDL_CANDIDATE.sql"), encoding="utf-8") as fh:
        ddl = fh.read()
    with connection.cursor() as c:
        c.execute(ddl)


def drop():
    connection.close()
    admin = admin_connection()
    with admin.cursor() as c:
        c.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", [DB_NAME])
        c.execute('DROP DATABASE IF EXISTS "%s"' % DB_NAME)
    admin.close()


def month_start():
    return mc.local_today().replace(day=1)


def seed():
    """Synthetic customer + 40,000 / 12% / 12-month allocation (monthly credit 4,800). Wipes the scratch DB only."""
    assert_scratch()
    today = mc.local_today()
    start = month_start()
    end = date(start.year + 1, start.month, 1)
    with connection.cursor() as c:
        c.execute("TRUNCATE advance_pay_transactions, advance_pay_allocations, advance_pay_offers, zg_order_items, "
                  "zg_checkout, a_cart, zg_variant, zg_product, users RESTART IDENTITY CASCADE")
        c.execute("INSERT INTO users (username,password,email,fullname,token,latitude,longitude,phone,address) "
                  "VALUES (%s,'x',%s,'Iso Customer','t','0','0','9999999999','Test address') RETURNING id", [USERNAME, EMAIL])
        uid = c.fetchone()[0]
        c.execute("INSERT INTO advance_pay_offers (offer_name,payment_amount,bonus_percentage,duration_months,total_credit,status) "
                  "VALUES ('special',40000,12,12,57600,'ACTIVE') RETURNING id")
        offer = c.fetchone()[0]
        c.execute("INSERT INTO advance_pay_allocations (offer_id,user_id,payment_amount,bonus_percentage,duration_months,total_credit,"
                  "used_credit,remaining_credit,start_date,end_date,payment_date,status) "
                  "VALUES (%s,%s,40000,12,12,57600,0,57600,%s,%s,%s,'ACTIVE') RETURNING id", [offer, uid, start, end, today])
        alloc = c.fetchone()[0]
        c.execute("INSERT INTO zg_product (code,stock,product_name,color,product_price,product_keywords,top2,hand2,heading5_tag,"
                  "heading6_tag,heading7_tag,added,view) VALUES ('P1','10','Iso Product','red',1000,'k',0,0,0,0,0,'now','1') RETURNING product_id")
        product = c.fetchone()[0]
    return {"uid": uid, "alloc": alloc, "product": product}


def user_dict(uid):
    return {"id": uid, "username": USERNAME, "email": EMAIL, "fullname": "Iso Customer", "phone": "9999999999", "address": "Test address"}


def put_in_cart(ctx, amount):
    with connection.cursor() as c:
        c.execute("UPDATE zg_product SET product_price=%s WHERE product_id=%s", [amount, ctx["product"]])
        c.execute("DELETE FROM a_cart WHERE username=%s", [USERNAME])
        c.execute("INSERT INTO a_cart (cart_id,username,product_id,variant_id,qty) VALUES ('c1',%s,%s,0,1)", [USERNAME, ctx["product"]])


def place(ctx, amount):
    """Run the REAL order_post view against the scratch database; returns the decoded JSON response."""
    put_in_cart(ctx, amount)
    with authed(user_dict(ctx["uid"])), override_settings(STOKIT_MIN_ORDER_VALUE=D("0.00")):
        response = views_orders.order_post(rf.post("/api/order_post", data={}, **BEARER))
    return json.loads(response.content)


def ledger(ctx):
    with connection.cursor() as c:
        c.execute("SELECT transaction_type,amount,reference_type,reference_id FROM advance_pay_transactions "
                  "WHERE allocation_id=%s ORDER BY id", [ctx["alloc"]])
        return [(t, D(str(a)), rt, ri) for t, a, rt, ri in c.fetchall()]


def stored(ctx):
    with connection.cursor() as c:
        c.execute("SELECT used_credit,remaining_credit FROM advance_pay_allocations WHERE id=%s", [ctx["alloc"]])
        u, r = c.fetchone()
        return D(str(u)), D(str(r))


def state(ctx):
    with connection.cursor() as c:
        return mc.load_state(c, ctx["uid"])[0]


def count(sql, params=()):
    with connection.cursor() as c:
        c.execute(sql, params)
        return c.fetchone()[0]


class CreditOnRealPostgres(unittest.TestCase):
    def setUp(self):
        self.ctx = seed()

    # Example A ------------------------------------------------------------------------------------------------
    def test_a_single_3000_order_consumes_3000_of_4800(self):
        result = place(self.ctx, 3000)
        self.assertEqual(result["status"], "success", result)
        rows = ledger(self.ctx)
        self.assertEqual(rows, [("CREDIT_USED", D("3000.00"), "ORDER_BONUS", int(result["order_id"]))])
        st = state(self.ctx)
        self.assertEqual((st.monthly_credit_release, st.used_this_month, st.remaining_this_month), (D("4800.00"), D("3000.00"), D("1800.00")))
        self.assertEqual(stored(self.ctx), (D("3000.00"), D("54600.00")))  # lifetime used / lifetime remaining

    # Example B ------------------------------------------------------------------------------------------------
    def test_b_multiple_orders_share_one_monthly_allowance(self):
        for amount in (2000, 2000, 1500):
            self.assertEqual(place(self.ctx, amount)["status"], "success")
        self.assertEqual([r[1] for r in ledger(self.ctx)], [D("2000.00"), D("2000.00"), D("800.00")])
        st = state(self.ctx)
        self.assertEqual((st.used_this_month, st.remaining_this_month), (D("4800.00"), D("0.00")))
        # a fourth order gets a zero-amount marker row only
        self.assertEqual(place(self.ctx, 500)["status"], "success")
        self.assertEqual(ledger(self.ctx)[-1][1], D("0.00"))
        self.assertEqual(state(self.ctx).used_this_month, D("4800.00"))

    def test_order_larger_than_remaining_consumes_only_remaining(self):
        place(self.ctx, 4000)
        place(self.ctx, 3000)
        self.assertEqual([r[1] for r in ledger(self.ctx)], [D("4000.00"), D("800.00")])

    # previews never deduct --------------------------------------------------------------------------------------
    def test_cart_refresh_and_checkout_preview_do_not_deduct(self):
        put_in_cart(self.ctx, 3000)
        with authed(user_dict(self.ctx["uid"])), override_settings(STOKIT_MIN_ORDER_VALUE=D("0.00")):
            for _ in range(3):
                cart = json.loads(views_commerce.cart_api_test(rf.get("/api/cart_api_test", **BEARER)).content)
                checkout = json.loads(views_commerce.checkout(rf.get("/api/checkout", **BEARER)).content)
        summary = cart["cart_items"]["final_summary"]
        self.assertEqual((summary["monthly_credit_release"], summary["credit_applied"], summary["payable_amount"]), (4800.0, 3000.0, 0.0))
        self.assertEqual(summary["order_total_before_credit"], 3000.0)
        self.assertEqual(checkout["status"], "success")
        self.assertEqual(ledger(self.ctx), [])
        self.assertEqual(stored(self.ctx), (D("0.00"), D("57600.00")))

    # idempotency / admin confirmation ---------------------------------------------------------------------------
    def test_reprocessing_and_admin_confirmation_never_deduct_twice(self):
        order_id = int(place(self.ctx, 3000)["order_id"])
        with transaction.atomic(), connection.cursor() as c:
            again = mc.commit_order_credit(c, order_id, self.ctx["uid"], D("3000"))
            self.assertTrue(again["duplicate"])
            confirmed = release_and_deduct_for_confirmed_order(c, order_id, EMAIL, D("3000"), allow_new=True)
            self.assertEqual(confirmed["credit_status"], "already_applied")
            later = release_and_deduct_for_confirmed_order(c, order_id, EMAIL, D("3000"), allow_new=False)
            self.assertEqual(later["bonus_applied"], D("3000.00"))
        self.assertEqual(len(ledger(self.ctx)), 1)
        self.assertEqual(stored(self.ctx), (D("3000.00"), D("54600.00")))

    # rollback ---------------------------------------------------------------------------------------------------
    def test_failure_after_credit_commit_rolls_back_order_and_ledger(self):
        put_in_cart(self.ctx, 3000)
        real_execute = views_orders.execute

        def failing(sql, params=None):
            if "DELETE FROM a_cart" in sql:
                raise RuntimeError("simulated failure after credit was recorded")
            return real_execute(sql, params)

        with authed(user_dict(self.ctx["uid"])), override_settings(STOKIT_MIN_ORDER_VALUE=D("0.00")), \
                mock.patch.object(views_orders, "execute", side_effect=failing):
            try:
                views_orders.order_post(rf.post("/api/order_post", data={}, **BEARER))
            except RuntimeError:
                pass
        self.assertEqual(ledger(self.ctx), [])
        self.assertEqual(stored(self.ctx), (D("0.00"), D("57600.00")))
        self.assertEqual(count("SELECT COUNT(*) FROM zg_checkout"), 0)
        self.assertEqual(count("SELECT COUNT(*) FROM zg_order_items"), 0)
        self.assertEqual(count("SELECT COUNT(*) FROM a_cart WHERE username=%s", [USERNAME]), 1)  # cart kept for retry

    # concurrency ------------------------------------------------------------------------------------------------
    def test_concurrent_orders_cannot_over_consume_the_allowance(self):
        workers, results, errors = 6, [], []
        barrier = threading.Barrier(workers)
        uid = self.ctx["uid"]

        def run(order_id):
            try:
                barrier.wait(timeout=20)
                with transaction.atomic(), connection.cursor() as c:
                    results.append(mc.commit_order_credit(c, order_id, uid, D("2000"), record_zero=True)["bonus_applied"])
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(repr(exc))
            finally:
                connection.close()

        threads = [threading.Thread(target=run, args=(9000 + i,)) for i in range(workers)]
        [t.start() for t in threads]
        [t.join(timeout=60) for t in threads]
        self.assertEqual(errors, [])
        self.assertEqual(sorted(results, reverse=True), [D("2000.00"), D("2000.00"), D("800.00"), D("0.00"), D("0.00"), D("0.00")])
        self.assertEqual(sum(r[1] for r in ledger(self.ctx)), D("4800.00"))
        self.assertEqual(stored(self.ctx), (D("4800.00"), D("52800.00")))

    def test_concurrent_duplicate_processing_of_one_order_deducts_once(self):
        workers, errors = 5, []
        barrier = threading.Barrier(workers)
        uid = self.ctx["uid"]

        def run():
            try:
                barrier.wait(timeout=20)
                with transaction.atomic(), connection.cursor() as c:
                    mc.commit_order_credit(c, 4242, uid, D("3000"), record_zero=True)
            except Exception as exc:  # pragma: no cover
                errors.append(repr(exc))
            finally:
                connection.close()

        threads = [threading.Thread(target=run) for _ in range(workers)]
        [t.start() for t in threads]
        [t.join(timeout=60) for t in threads]
        self.assertEqual(errors, [])
        self.assertEqual([r[1] for r in ledger(self.ctx)], [D("3000.00")])

    # identity / ambiguity ---------------------------------------------------------------------------------------
    def test_customer_without_allocation_gets_no_credit_and_no_ledger_rows(self):
        with connection.cursor() as c:
            c.execute("UPDATE advance_pay_allocations SET status='CANCELLED'")
        self.assertEqual(place(self.ctx, 3000)["status"], "success")
        self.assertEqual(ledger(self.ctx), [])
        self.assertEqual(state(self.ctx).code, "no_allocation")


def main():
    print("Provisioning isolated database", DB_NAME)
    provision()
    try:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(CreditOnRealPostgres)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        if KEEP:
            print("--keep given; scratch database left in place:", DB_NAME)
        else:
            drop()
            print("Dropped isolated database", DB_NAME)
    print("RESULT: ran=%d failures=%d errors=%d skipped=%d" % (result.testsRun, len(result.failures), len(result.errors), len(result.skipped)))
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
