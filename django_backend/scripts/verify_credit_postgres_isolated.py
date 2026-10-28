"""Isolated PostgreSQL verification of the monthly-credit ledger (locking, concurrency, rollback, idempotency).

Creates a THROWAWAY database (stokit_credit_scratch_<random>) on the configured server, builds only the three tables
the credit service touches, runs every scenario with independent connections/transactions, then drops the database.
It never connects to the application database for anything but reading connection parameters, never prints
credentials, and refuses to run if the generated name could collide with a real database.

Run from django_backend:  python scripts/verify_credit_postgres_isolated.py
Exit codes: 0 all passed, 1 a check failed, 2 blocked (no permission / server unreachable; nothing was verified).
"""
import os
import sys
import threading
import uuid
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
import psycopg  # noqa: E402
from django.conf import settings  # noqa: E402
from legacydb import monthly_credit as mc  # noqa: E402

D = Decimal
SCHEMA = """
CREATE TABLE users (id SERIAL PRIMARY KEY, username TEXT, email TEXT, fullname TEXT);
CREATE TABLE advance_pay_allocations (id SERIAL PRIMARY KEY, offer_id INT, user_id INT, payment_amount NUMERIC(12,2),
  bonus_percentage NUMERIC(5,2), duration_months INT, total_credit NUMERIC(12,2), used_credit NUMERIC(12,2) DEFAULT 0,
  remaining_credit NUMERIC(12,2) DEFAULT 0, start_date DATE, end_date DATE, payment_date DATE, status TEXT, updated_at TIMESTAMP);
CREATE TABLE advance_pay_transactions (id SERIAL PRIMARY KEY, allocation_id INT, user_id INT, amount NUMERIC(12,2),
  transaction_type TEXT, reference_id BIGINT, reference_type TEXT, notes TEXT, created_at TIMESTAMP);
"""
results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition)))
    print(("PASS  " if condition else "FAIL  ") + name + (("  -> " + str(detail)) if detail and not condition else ""))


def conn_params(dbname):
    cfg = settings.DATABASES["default"]
    if cfg.get("ENGINE", "").rsplit(".", 1)[-1] not in ("postgresql", "postgresql_psycopg2"):
        raise SystemExit("BLOCKED: configured database is not PostgreSQL; nothing verified.")
    return dict(host=cfg.get("HOST") or "localhost", port=cfg.get("PORT") or 5432, user=cfg.get("USER"),
                password=cfg.get("PASSWORD"), dbname=dbname)


def fresh(dbname):
    """New connection (own transaction) to the scratch database."""
    return psycopg.connect(**conn_params(dbname))


def seed(dbname):
    with fresh(dbname) as c:
        cur = c.cursor()
        cur.execute("INSERT INTO users (username,email,fullname) VALUES ('t1','t1@example.test','Test One') RETURNING id")
        uid = cur.fetchone()[0]
        cur.execute("INSERT INTO advance_pay_allocations (offer_id,user_id,payment_amount,bonus_percentage,duration_months,total_credit,"
                    "used_credit,remaining_credit,start_date,end_date,payment_date,status) VALUES (1,%s,40000,12,12,57600,0,57600,"
                    "'2026-10-01','2027-10-01','2026-10-01','ACTIVE') RETURNING id", [uid])
        aid = cur.fetchone()[0]
        c.commit()
    return uid, aid


def place(dbname, uid, order_id, amount, now):
    """One order placement = one independent transaction (commit on success)."""
    with fresh(dbname) as c:
        cur = c.cursor()
        out = mc.commit_order_credit(cur, order_id, uid, D(str(amount)), now=now, record_zero=True)
        c.commit()
        return out


def ledger(dbname, aid):
    with fresh(dbname) as c:
        cur = c.cursor()
        cur.execute("SELECT COALESCE(SUM(amount),0), COUNT(*) FROM advance_pay_transactions WHERE allocation_id=%s", [aid])
        total, rows = cur.fetchone()
        cur.execute("SELECT used_credit, remaining_credit FROM advance_pay_allocations WHERE id=%s", [aid])
        used, remaining = cur.fetchone()
        return D(total), rows, D(used), D(remaining)


def main():
    name = "stokit_credit_scratch_" + uuid.uuid4().hex[:10]
    assert name.startswith("stokit_credit_scratch_") and name != settings.DATABASES["default"].get("NAME")
    try:
        admin = psycopg.connect(**conn_params("postgres"), autocommit=True)
        admin.execute('CREATE DATABASE "%s"' % name)
    except Exception as exc:  # permission denied, server down, ...
        print("BLOCKED: could not create a throwaway database (%s). Nothing was verified." % type(exc).__name__)
        return 2
    print("Created throwaway database %s (dropped at the end)." % name)
    try:
        with fresh(name) as c:
            c.execute(SCHEMA)
            c.commit()
        oct12 = datetime(2026, 10, 12, 11, 0)

        # --- A. one 3,000 order against a 4,800 monthly allowance
        uid, aid = seed(name)
        r = place(name, uid, 1001, 3000, oct12)
        check("A1 3,000 order applies exactly 3,000", r["bonus_applied"] == D("3000.00"), r["bonus_applied"])
        check("A2 payable after credit is 0", r["amount_payable"] == D("0.00"))
        total, rows, used, remaining = ledger(name, aid)
        check("A3 ledger holds exactly one 3,000 row", (total, rows) == (D("3000"), 1), (total, rows))
        check("A4 lifetime columns follow: used 3,000 / remaining 54,600", (used, remaining) == (D("3000"), D("54600")), (used, remaining))
        with fresh(name) as c:
            state, _ = mc.load_state(c.cursor(), uid, oct12.date())
        check("A5 October remaining credit is 1,800", state.remaining_this_month == D("1800.00"), state.remaining_this_month)

        # --- B. reprocessing the same order never deducts twice
        again = place(name, uid, 1001, 3000, oct12)
        check("B1 same order again reports already applied", again["duplicate"] is True)
        check("B2 ...and adds no ledger row / balance change", ledger(name, aid) == (D("3000"), 1, D("3000"), D("54600")), ledger(name, aid))

        # --- C. a view of the state (cart refresh / preview) writes nothing
        before = ledger(name, aid)
        for _ in range(5):
            with fresh(name) as c:
                mc.customer_credit_context(c.cursor(), user_id=uid, today=oct12.date())
        check("C1 five cart/preview reads leave the ledger untouched", ledger(name, aid) == before)

        # --- D. an order larger than what is left only gets the remainder
        r = place(name, uid, 1002, 2500, oct12)
        check("D1 2,500 order gets only the remaining 1,800", r["bonus_applied"] == D("1800.00"), r["bonus_applied"])
        check("D2 customer pays the 700 difference", r["amount_payable"] == D("700.00"), r["amount_payable"])
        r = place(name, uid, 1003, 500, oct12)
        check("D3 next order gets 0 (month exhausted) and still gets a zero marker row", r["bonus_applied"] == D("0.00") and ledger(name, aid)[1] == 3, ledger(name, aid))

        # --- E. rollback: failure after the deduction removes it together with the order
        uid2, aid2 = seed(name)
        c = fresh(name)
        cur = c.cursor()
        mc.commit_order_credit(cur, 2001, uid2, D("1000"), now=oct12, record_zero=True)
        inside = cur.execute("SELECT COUNT(*) FROM advance_pay_transactions WHERE allocation_id=%s", [aid2]).fetchone()[0]
        c.rollback()
        c.close()
        check("E1 deduction existed inside the transaction", inside == 1, inside)
        check("E2 after rollback no credit and no balance change remain", ledger(name, aid2) == (D("0"), 0, D("0"), D("57600")), ledger(name, aid2))

        # --- F. concurrency: 8 simultaneous orders of 1,000 against a 4,800 allowance
        uid3, aid3 = seed(name)
        barrier = threading.Barrier(8)
        applied, errors = [], []

        def worker(i):
            try:
                barrier.wait(timeout=20)
                applied.append(place(name, uid3, 3000 + i, 1000, oct12)["bonus_applied"])
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(repr(exc))
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        [t.start() for t in threads]
        [t.join(timeout=60) for t in threads]
        total, rows, used, remaining = ledger(name, aid3)
        check("F1 no worker failed or deadlocked", not errors and len(applied) == 8, errors)
        check("F2 total consumed is exactly the 4,800 allowance (never more)", total == D("4800.00") and sum(applied) == D("4800.00"), (total, sum(applied)))
        check("F3 every order got at most 1,000 and 8 ledger rows exist", max(applied) <= D("1000") and rows == 8, (max(applied), rows))
        check("F4 lifetime columns match the ledger", (used, remaining) == (D("4800"), D("52800")), (used, remaining))

        # --- G. same order submitted concurrently is deducted once
        uid4, aid4 = seed(name)
        barrier = threading.Barrier(5)
        outs, errors = [], []

        def same_order():
            try:
                barrier.wait(timeout=20)
                outs.append(place(name, uid4, 4001, 1000, oct12))
            except Exception as exc:  # pragma: no cover
                errors.append(repr(exc))
        threads = [threading.Thread(target=same_order) for _ in range(5)]
        [t.start() for t in threads]
        [t.join(timeout=60) for t in threads]
        total, rows, used, remaining = ledger(name, aid4)
        check("G1 five simultaneous submissions of one order deduct once", total == D("1000") and rows == 1 and not errors, (total, rows, errors))

        # --- H. rollover / carry-forward does not duplicate credit
        uid5, aid5 = seed(name)
        place(name, uid5, 5001, 3000, oct12)
        nov = datetime(2026, 11, 5, 9, 0)
        with fresh(name) as c:
            state, _ = mc.load_state(c.cursor(), uid5, nov.date())
        check("H1 November = 4,800 + 1,800 carried (October balance counted once)", (state.carried_forward, state.available_credit, state.remaining_this_month) == (D("1800.00"), D("6600.00"), D("6600.00")),
              (state.carried_forward, state.available_credit, state.remaining_this_month))
        r = place(name, uid5, 5002, 7000, nov)
        check("H2 a 7,000 November order is covered up to 6,600", r["bonus_applied"] == D("6600.00"), r["bonus_applied"])
        with fresh(name) as c:
            state, _ = mc.load_state(c.cursor(), uid5, nov.date())
        check("H3 November is then exhausted; refreshing does not restore it", state.remaining_this_month == D("0.00"), state.remaining_this_month)

        # --- I. no allocation: explicit None, nothing written
        with fresh(name) as c:
            cur = c.cursor()
            cur.execute("INSERT INTO users (username,email,fullname) VALUES ('t2','t2@example.test','No Alloc') RETURNING id")
            nid = cur.fetchone()[0]
            out = mc.commit_order_credit(cur, 6001, nid, D("500"), now=oct12, record_zero=True)
            c.commit()
        check("I1 customer without an allocation gets None and no ledger row", out is None and ledger(name, aid)[1] == 3)
    finally:
        try:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", [name])
            admin.execute('DROP DATABASE IF EXISTS "%s"' % name)
            print("Dropped throwaway database %s." % name)
        finally:
            admin.close()
    failed = [n for n, ok in results if not ok]
    print("\n%d checks, %d passed, %d failed" % (len(results), len(results) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
