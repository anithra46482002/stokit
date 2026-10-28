"""Verify the real cart workflow against the configured PostgreSQL database, then ROLL EVERYTHING BACK.

Safety: no schema change, no migration, no real account. Two synthetic usernames that must have no cart rows are
used; every write happens inside one transaction that is rolled back at the end, so no cart, order or product row
persists. (A rolled-back INSERT still advances the a_cart.id identity sequence; that is the only residue.)
Authentication is replaced by a stub identity, so no password, token or session is read or created.

Usage (from django_backend):  set DJANGO_ENV_FILE=.env.postgres  &&  python scripts\\verify_cart_flow_rollback.py
"""
import json
import os
import sys
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.db import connection, transaction  # noqa: E402
from django.test import RequestFactory  # noqa: E402

from legacy_api import views_cart, views_commerce  # noqa: E402

rf = RequestFactory(SERVER_NAME="127.0.0.1")  # an allowed host, so image URLs can be built
BEARER = {"HTTP_AUTHORIZATION": "Bearer " + "0" * 64}
PROBE_A, PROBE_B = "zz_cart_probe_user_a", "zz_cart_probe_user_b"
results = []


class Rollback(Exception):
    pass


def check(label, condition, detail=""):
    results.append((label, bool(condition)))
    print(("PASS  " if condition else "FAIL  ") + label + (("  -> " + str(detail)) if detail != "" else ""))


def identity(username):
    return mock.patch("accounts.services.authenticate_token",
                      return_value=(SimpleNamespace(pk=0, user_id=0), {"id": 0, "username": username}))


def call(view, request, username):
    with identity(username):
        return json.loads(view(request).content)


def add(username, product_id, *variants):
    body = {"product_id": str(product_id), "variants": [{"variant_id": v, "qty": q} for v, q in variants]}
    return call(views_commerce.product_api_cart,
                rf.post("/api/product-api-cart", json.dumps(body), content_type="application/json", **BEARER), username)


def act(username, name, variant_id, product_id):
    body = {"product_id": product_id, "variant_id": variant_id, "action": name}
    return call(views_cart.cart_action,
                rf.post("/api/cart_action", json.dumps(body), content_type="application/json", **BEARER), username)


def cart(username):
    return call(views_commerce.cart_api_test, rf.get("/api/cart_api_test", **BEARER), username)


def lines(c):
    out = []
    for bucket in ("discount_available", "discount_not_available"):
        for key, group in c["cart_items"][bucket].items():
            out += [(key, i["product_name"], i["variant_id"], i["quantity"]) for i in group["items"]]
    return out


def checkout(username):
    real_fetchone = views_commerce.fetchone

    def fetchone(sql, params=()):
        if sql.startswith("SELECT id,profile_picture,shop_name"):   # synthetic customer; cart SQL stays real
            return {"id": 0, "profile_picture": None, "shop_name": "probe", "fullname": "probe", "address": "",
                    "city": "", "created_at": datetime(2026, 1, 1), "username": username, "phone": "", "email": "",
                    "status": "ACTIVE", "vip_discount": None, "vip_percentage": 0, "store_maped": "N",
                    "delivery_charges": 0}
        return real_fetchone(sql, params)

    with mock.patch.object(views_commerce, "fetchone", fetchone):
        return call(views_commerce.checkout, rf.get("/api/checkout", **BEARER), username)["checkout_data"]


def pick_products():
    with connection.cursor() as c:
        c.execute("SELECT product_id FROM zg_product p WHERE view='1' AND NOT EXISTS "
                  "(SELECT 1 FROM zg_variant v WHERE v.product_id=p.product_id) ORDER BY product_id LIMIT 2")
        return [r[0] for r in c.fetchall()]


def main():
    with connection.cursor() as c:
        c.execute("SELECT count(*) FROM a_cart WHERE username IN (%s,%s)", [PROBE_A, PROBE_B])
        if c.fetchone()[0]:
            sys.exit("Probe usernames already have cart rows; refusing to run.")
        c.execute("SELECT count(*) FROM a_cart")
        before = c.fetchone()[0]
    products = pick_products()
    if len(products) < 2:
        sys.exit("Need two visible products without variants in the catalogue; BLOCKED.")
    pa, pb = products
    print("Using catalogue products", pa, "and", pb, "(variant 0) for synthetic users", PROBE_A, PROBE_B)
    try:
        with transaction.atomic():
            r1, r2 = add(PROBE_A, pa, (0, 2)), add(PROBE_A, pb, (0, 3))
            check("add product A", r1.get("status") == "success", r1.get("inserted_items"))
            check("add product B", r2.get("status") == "success", r2.get("inserted_items"))
            c1 = cart(PROBE_A)
            got = lines(c1)
            check("cart holds both products", len(got) == 2, got)
            check("cart group keys are the real product ids", sorted(k for k, *_ in got) == sorted([str(pa), str(pb)]))
            check("cart quantities", sorted(q for *_, q in got) == [2, 3])
            check("total_cart_items counts every line", c1["cart_items"]["final_summary"]["total_cart_items"] == 5)
            r3 = add(PROBE_A, pa, (0, 1))
            check("adding A again increments (3 pieces), no new line",
                  sorted(q for *_, q in lines(cart(PROBE_A))) == [3, 3] and len(lines(cart(PROBE_A))) == 2, r3.get("status"))
            check("user isolation: other user's cart is empty", lines(cart(PROBE_B)) == [])
            check("user isolation: other user cannot remove my line",
                  act(PROBE_B, "remove", 0, pa)["affected_rows"] == 0 and len(lines(cart(PROBE_A))) == 2)
            full = checkout(PROBE_A)
            check("checkout counts both lines", full["cart_summary"]["total_items"] == 2, full["cart_summary"])
            check("stale legacy key with two variant-0 lines is rejected and changes nothing",
                  act(PROBE_A, "remove", 0, 1).get("status") is False and len(lines(cart(PROBE_A))) == 2)
            key_a = next(k for k, name, v, q in lines(cart(PROBE_A)) if k == str(pa))
            rm = act(PROBE_A, "remove", 0, int(key_a))
            check("remove product A deletes exactly one line", rm.get("affected_rows") == 1, rm)
            after = lines(cart(PROBE_A))
            check("product A gone, product B untouched", [k for k, *_ in after] == [str(pb)] and after[0][3] == 3, after)
            inc = act(PROBE_A, "increase", 0, pb)
            check("increase B changes only B", inc.get("affected_rows") == 1 and lines(cart(PROBE_A))[0][3] == 4)
            rest = checkout(PROBE_A)
            check("checkout uses the remaining item only", rest["cart_summary"]["total_items"] == 1
                  and rest["cart_summary"]["total_quantity"] == 4, rest["cart_summary"])
            raise Rollback()
    except Rollback:
        pass
    with connection.cursor() as c:
        c.execute("SELECT count(*) FROM a_cart")
        after_count = c.fetchone()[0]
        c.execute("SELECT count(*) FROM a_cart WHERE username IN (%s,%s)", [PROBE_A, PROBE_B])
        probe_left = c.fetchone()[0]
    check("rollback left a_cart row count unchanged", after_count == before, "%s -> %s" % (before, after_count))
    check("no probe rows persisted", probe_left == 0)
    failed = [label for label, ok in results if not ok]
    print("\n%d checks, %d failed" % (len(results), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
