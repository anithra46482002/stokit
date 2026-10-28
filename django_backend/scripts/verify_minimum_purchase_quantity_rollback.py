"""Verify Minimum Purchase Quantity (minimum_buying_count) against the configured PostgreSQL database, then ROLL BACK.

Runs the real admin API views (ProductCRUDView / VariantCRUDView) and real SQL against the configured database.
Safety: no schema change, no migration, no real account. Every write happens inside ONE transaction that is
rolled back at the end, so no product or variant row persists. (A rolled-back INSERT still advances the
identity sequences of zg_product / zg_variant; that is the only residue.) Authentication is replaced by a
stub admin identity, so no password, token or session is read or created. The script refuses to run unless the
active database is the approved development database.

Usage (from django_backend):  python scripts\\verify_minimum_purchase_quantity_rollback.py
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import IntegrityError, connection, transaction  # noqa: E402
from rest_framework.test import APIRequestFactory, force_authenticate  # noqa: E402

from adminapi import crud  # noqa: E402

APPROVED_DB = "stokit_postgres_dev"
db = settings.DATABASES["default"]
if db["NAME"] != APPROVED_DB or db["HOST"] not in ("127.0.0.1", "localhost") or str(db["PORT"]) != "5432":
    sys.exit("Refusing to run: the active database is not the approved development database.")

factory = APIRequestFactory(SERVER_NAME="127.0.0.1")
USER = SimpleNamespace(is_authenticated=True, role="ADMIN", pk=1, principal_type="ADMIN")
results = []


class Rollback(Exception):
    pass


def check(label, condition, detail=""):
    results.append((label, bool(condition)))
    print(("PASS  " if condition else "FAIL  ") + label + (("  -> " + str(detail)) if detail != "" else ""))


def call(view, method, path, payload=None, params=None):
    maker = getattr(factory, method)
    request = maker(path, payload, format="json") if method != "get" else maker(path, params or {})
    force_authenticate(request, user=USER)
    return view.as_view()(request)


def product_api(method, payload=None, **params):
    return call(crud.ProductCRUDView, method, "/admin-api/products", payload, params)


def variant_api(method, payload=None, **params):
    return call(crud.VariantCRUDView, method, "/admin-api/product-variants", payload, params)


def sql(query, args=()):
    with connection.cursor() as cursor:
        cursor.execute(query, list(args))
        return cursor.fetchall()


def variant_row(variant_id):
    return sql("SELECT quantity, minimum_buying_count, variant_name FROM zg_variant WHERE variant_id=%s", [variant_id])[0]


def moq(product_id):
    return sql("SELECT moq FROM zg_product WHERE product_id=%s", [product_id])[0][0]


def listed_variants(product_id):
    response = variant_api("get", product_id=product_id)
    return {row["id"]: row for row in response.data["results"]}


before_variants = sql("SELECT variant_id, quantity, minimum_buying_count FROM zg_variant ORDER BY variant_id")
before_counts = (sql("SELECT count(*) FROM zg_product")[0][0], sql("SELECT count(*) FROM zg_variant")[0][0])
category_id = sql("SELECT category_id FROM zg_category ORDER BY category_id LIMIT 1")[0][0]
print("database:", db["NAME"], "| existing variants:", len(before_variants), "| products:", before_counts[0])

try:
    with transaction.atomic():
        # ---- product: create / GET / PATCH, column zg_product.moq -------------------------------------
        created = product_api("post", {"name": "zz_min_purchase_probe", "code": "zzprobe", "price": "100", "mrp": "120",
                                       "category_id": category_id, "minimum_buying_count": 10})
        check("product POST with minimum_buying_count=10 -> 201", created.status_code == 201, created.status_code)
        pid = created.data["id"]
        check("product POST returns both field names", created.data["minimum_buying_count"] == 10 == created.data["minimum_buying_quantity"])
        check("zg_product.moq holds 10 after POST", moq(pid) == 10, moq(pid))
        listed = product_api("get", id=pid).data["results"][0]
        check("product GET returns the saved value (both names)", listed["minimum_buying_count"] == 10 == listed["minimum_buying_quantity"])

        omitted = product_api("post", {"name": "zz_min_purchase_probe_default", "code": "zzdef", "price": "5", "mrp": "5", "category_id": category_id})
        check("product POST without the field defaults to 1", omitted.status_code == 201 and moq(omitted.data["id"]) == 1, moq(omitted.data["id"]))

        legacy = product_api("post", {"name": "zz_min_purchase_probe_legacy", "code": "zzleg", "price": "5", "mrp": "5", "category_id": category_id, "minimum_buying_quantity": 7})
        check("legacy minimum_buying_quantity payload still creates moq=7", legacy.status_code == 201 and moq(legacy.data["id"]) == 7)

        conflict = product_api("post", {"name": "zz_conflict", "code": "zzc", "price": "5", "mrp": "5", "category_id": category_id, "minimum_buying_count": 4, "minimum_buying_quantity": 9})
        check("conflicting aliases on POST -> 400, nothing created", conflict.status_code == 400 and sql("SELECT count(*) FROM zg_product WHERE code='zzc'")[0][0] == 0, conflict.data)
        same = product_api("post", {"name": "zz_same", "code": "zzs", "price": "5", "mrp": "5", "category_id": category_id, "minimum_buying_count": 4, "minimum_buying_quantity": 4})
        check("matching aliases are accepted", same.status_code == 201 and moq(same.data["id"]) == 4)

        # ---- variants: independent values, column zg_variant.minimum_buying_count ----------------------
        a = variant_api("post", {"product_id": pid, "name": "A 5kg", "price": "100", "mrp": "120", "quantity": 50, "minimum_buying_count": 5})
        b = variant_api("post", {"product_id": pid, "name": "B 12kg", "price": "100", "mrp": "120", "quantity": 60, "minimum_buying_count": 12})
        c = variant_api("post", {"product_id": pid, "name": "C default", "price": "100", "mrp": "120", "quantity": 70})
        check("variant POSTs -> 201", (a.status_code, b.status_code, c.status_code) == (201, 201, 201), (a.status_code, b.status_code, c.status_code))
        va, vb, vc = a.data["id"], b.data["id"], c.data["id"]
        check("variant POST responses return the saved value", (a.data["minimum_buying_count"], b.data["minimum_buying_count"], c.data["minimum_buying_count"]) == (5, 12, 1))
        check("zg_variant stores 5 / 12 / 1 independently", (variant_row(va)[1], variant_row(vb)[1], variant_row(vc)[1]) == (5, 12, 1))
        check("stock quantity stays independent (50 / 60 / 70)", (variant_row(va)[0], variant_row(vb)[0], variant_row(vc)[0]) == (50, 60, 70))
        got = listed_variants(pid)
        check("variant GET returns the stored values", [got[v]["minimum_buying_count"] for v in (va, vb, vc)] == [5, 12, 1])
        embedded = {row["id"]: row for row in product_api("get", id=pid).data["results"][0]["variants"]}
        check("product list embeds each variant's own value", [embedded[v]["minimum_buying_count"] for v in (va, vb, vc)] == [5, 12, 1])
        check("parent product value (10) is separate from the variants", moq(pid) == 10)

        p = variant_api("patch", {"id": va, "name": "A renamed"})
        check("variant PATCH without the field preserves it", p.status_code == 200 and variant_row(va)[1] == 5 and variant_row(va)[2] == "A renamed", p.data)
        p = variant_api("patch", {"id": vb, "minimum_buying_count": 20})
        check("variant PATCH updates only the selected variant", p.status_code == 200 and (variant_row(va)[1], variant_row(vb)[1], variant_row(vc)[1]) == (5, 20, 1))
        check("variant PATCH response returns the persisted value", p.data["minimum_buying_count"] == 20)
        p = variant_api("patch", {"id": vc, "quantity": 99})
        check("changing stock quantity does not touch the count", variant_row(vc)[:2] == (99, 1))

        # ---- the product never overwrites variant values -------------------------------------------------
        p = product_api("patch", {"id": pid, "minimum_buying_quantity": 3})
        check("product PATCH via legacy alias updates moq", p.status_code == 200 and moq(pid) == 3 and p.data["minimum_buying_count"] == 3)
        p = product_api("patch", {"id": pid, "minimum_buying_count": 8})
        check("product PATCH via minimum_buying_count updates moq", p.status_code == 200 and moq(pid) == 8)
        check("product updates leave variant values at 5 / 20 / 1", (variant_row(va)[1], variant_row(vb)[1], variant_row(vc)[1]) == (5, 20, 1))
        p = product_api("patch", {"id": pid, "name": "zz_min_purchase_probe renamed"})
        check("unrelated product PATCH preserves moq", p.status_code == 200 and moq(pid) == 8)
        p = product_api("patch", {"id": pid, "minimum_buying_count": 2, "minimum_buying_quantity": 3})
        check("conflicting aliases on PATCH -> 400 and moq unchanged", p.status_code == 400 and moq(pid) == 8, p.data)

        # ---- invalid values are rejected before any write ----------------------------------------------
        bad_values = ["", None, 0, -1, 1.5, "1.5", "1e2", "2.0", "+3", True, "abc", 2147483648]
        rejected = {"variant_post": 0, "variant_patch": 0, "product_patch": 0, "product_post": 0}
        variants_before = sql("SELECT count(*) FROM zg_variant")[0][0]
        for value in bad_values:
            r = variant_api("post", {"product_id": pid, "name": "bad", "price": "1", "quantity": 1, "minimum_buying_count": value})
            rejected["variant_post"] += int(r.status_code == 400 and "minimum_buying_count" in r.data)
            r = variant_api("patch", {"id": va, "minimum_buying_count": value})
            rejected["variant_patch"] += int(r.status_code == 400 and "minimum_buying_count" in r.data)
            r = product_api("patch", {"id": pid, "minimum_buying_count": value})
            rejected["product_patch"] += int(r.status_code == 400 and "minimum_buying_count" in r.data)
            r = product_api("post", {"name": "zz_bad", "code": "zzbad", "price": "1", "mrp": "1", "category_id": category_id, "minimum_buying_count": value})
            rejected["product_post"] += int(r.status_code == 400 and "minimum_buying_count" in r.data)
        check("all %d invalid values rejected by every endpoint" % len(bad_values), all(v == len(bad_values) for v in rejected.values()), rejected)
        check("rejected requests wrote nothing", sql("SELECT count(*) FROM zg_variant")[0][0] == variants_before
              and moq(pid) == 8 and variant_row(va)[1] == 5 and sql("SELECT count(*) FROM zg_product WHERE code='zzbad'")[0][0] == 0)

        # ---- database CHECK constraint (>= 1) ------------------------------------------------------------
        try:
            with transaction.atomic():
                sql("UPDATE zg_variant SET minimum_buying_count = 0 WHERE variant_id=%s", [va])
            check("database CHECK rejects 0", False)
        except IntegrityError:
            check("database CHECK rejects 0", True)
        check("value unchanged after the rejected UPDATE", variant_row(va)[1] == 5)

        raise Rollback()
except Rollback:
    pass

after_variants = sql("SELECT variant_id, quantity, minimum_buying_count FROM zg_variant ORDER BY variant_id")
after_counts = (sql("SELECT count(*) FROM zg_product")[0][0], sql("SELECT count(*) FROM zg_variant")[0][0])
check("rollback left no probe rows (product/variant counts unchanged)", after_counts == before_counts, after_counts)
check("pre-existing variants unchanged after rollback", after_variants == before_variants)
failed = [label for label, ok in results if not ok]
print("\n%d checks, %d failed" % (len(results), len(failed)))
sys.exit(1 if failed else 0)
