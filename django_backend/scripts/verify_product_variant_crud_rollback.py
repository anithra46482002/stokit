"""Verify product + variant Edit/Delete against the configured PostgreSQL development database, then ROLL BACK.

Runs the real admin API views (ProductCRUDView / VariantCRUDView) and real SQL. Every write happens inside ONE
transaction that is rolled back at the end, so no product, variant, banner, image, cart or favourite row persists
(a rolled-back INSERT still advances identity sequences; that is the only residue). Authentication is replaced by a
stub admin identity (no password, token or session is read or created). Refuses to run on any other database.

Usage (from django_backend):  python scripts\\verify_product_variant_crud_rollback.py
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection, transaction  # noqa: E402
from rest_framework.test import APIRequestFactory, force_authenticate  # noqa: E402

from adminapi import crud  # noqa: E402

APPROVED_DB = "stokit_postgres_dev"
db = settings.DATABASES["default"]
if db["NAME"] != APPROVED_DB or db["HOST"] not in ("127.0.0.1", "localhost") or str(db["PORT"]) != "5432":
    sys.exit("Refusing to run: the active database is not the approved development database.")

factory = APIRequestFactory(SERVER_NAME="127.0.0.1")
USER = SimpleNamespace(is_authenticated=True, role="ADMIN", pk=1, principal_type="ADMIN")
results = []
TABLES = ("zg_product", "zg_variant", "zg_product_images", "zg_discount_banners", "zg_favorites", "a_cart", "zg_order_items", "zg_stock_log")


class Rollback(Exception):
    pass


def check(label, condition, detail=""):
    results.append((label, bool(condition)))
    print(("PASS  " if condition else "FAIL  ") + label + (("  -> " + str(detail)) if detail != "" else ""))


def call(view, method, path, payload=None, params=None):
    maker = getattr(factory, method)
    if method == "delete":
        request = maker(path + "?" + "&".join("%s=%s" % item for item in (params or {}).items()))
    else:
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
        return cursor.fetchall() if cursor.description else []


def counts():
    return {t: sql("SELECT count(*) FROM " + t)[0][0] for t in TABLES}


def snapshot():
    return {
        "products": sql("SELECT * FROM zg_product ORDER BY product_id"),
        "variants": sql("SELECT * FROM zg_variant ORDER BY variant_id"),
    }


before_counts = counts()
before_snapshot = snapshot()
print("database:", db["NAME"], "| rows before:", before_counts)
category_id = sql("SELECT category_id FROM zg_category ORDER BY category_id LIMIT 1")[0][0]

try:
    with transaction.atomic():
        # ---- 1. the Edit dialog's no-change save works for EVERY existing product and variant, and changes nothing
        listing = product_api("get", page_size=100).data["results"]
        for row in listing:
            payload = dict(id=row["id"], name=row["name"], code=row["code"], price=float(row["price"]), mrp=float(row["mrp"]),
                           discount=float(row["discount"]), no_discount_banner=row["no_discount_banner"], disable_variants=row["disable_variants"],
                           minimum_buying_count=row["minimum_buying_count"], minimum_buying_quantity=row["minimum_buying_count"],
                           category_id=int(row["category_id"]), subcategory_id=int(row["subcategory_id"]) if row.get("subcategory_id") else None,
                           visible=row["visible"], highlight=bool(row.get("highlight")), stock=row.get("stock") or "", gst_applicable=row.get("gst_applicable") or "N",
                           gst_percentage=float(row.get("gst_percentage") or 0), gst_price=float(row.get("gst_price") or 0), description=row.get("description") or "",
                           keywords=row.get("keywords") or "", subtitle=row.get("subtitle") or "", brand=row.get("brand") or "", set_contains=row.get("set_contains") or [])
            check("edit product %s with the dialog's payload" % row["id"], product_api("patch", payload).status_code == 200)
            for v in row.get("variants") or []:
                vp = dict(id=v["id"], product_id=row["id"], name=v["name"], price=float(v["price"]), mrp=float(v.get("mrp") or v["price"]), quantity=int(v["quantity"]),
                          minimum_buying_count=int(v.get("minimum_buying_count") or 1), discount=str(v.get("discount") or "0"), gst=v.get("gst") or "N", gst_price=float(v.get("gst_price") or 0))
                check("edit variant %s of product %s" % (v["id"], row["id"]), variant_api("patch", vp).status_code == 200)
        check("a no-change edit leaves every product and variant row byte-identical", snapshot() == before_snapshot)

        # ---- 2. create a throw-away product with a banner, an image, two variants, a favourite
        created = product_api("post", {"name": "zz_crud_probe", "code": "zzcrud", "price": "100", "mrp": "120", "category_id": category_id, "stock": "In Stock",
                                       "discount_banners": ["uploads/zz_probe_banner.webp"]})
        check("create probe product", created.status_code == 201, created.data)
        pid = created.data["id"]
        sql("INSERT INTO zg_product_images (image_id, product_id, image_path, main) VALUES ((SELECT COALESCE(MAX(image_id),0)+1 FROM zg_product_images), %s, %s, %s)", [pid, "uploads/zz_probe.webp", "1"])
        va = variant_api("post", {"product_id": pid, "name": "A", "price": "10", "quantity": "5"}).data["id"]
        vb = variant_api("post", {"product_id": pid, "name": "B", "price": "20", "quantity": "6"}).data["id"]
        sql("INSERT INTO zg_favorites (id, user_id, product_id) VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM zg_favorites), %s, %s)", ["zz_probe_user", pid])
        check("probe banner stored (real FK child)", sql("SELECT count(*) FROM zg_discount_banners WHERE product_id=%s", [pid])[0][0] == 1)

        # Documented finding: the banner table's FK to zg_product cascades, so banners never blocked deletion;
        # the view still removes them explicitly so it does not depend on that constraint rule.
        rule = sql("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='fk_discount_banners_product'")
        check("banner FK is ON DELETE CASCADE (banners are not a delete blocker)", rule and "ON DELETE CASCADE" in rule[0][0], rule)
        # ---- 3. edit persists
        check("edit probe product", product_api("patch", {"id": pid, "name": "zz_crud_probe2", "price": 111, "minimum_buying_count": 3}).status_code == 200)
        check("edit persisted", sql("SELECT product_name, product_price, moq FROM zg_product WHERE product_id=%s", [pid])[0][0:3] == ("zz_crud_probe2", 111, 3), sql("SELECT product_name, product_price, moq FROM zg_product WHERE product_id=%s", [pid]))
        check("edit probe variant", variant_api("patch", {"id": va, "product_id": pid, "name": "A2", "price": 11, "quantity": 7, "minimum_buying_count": 2}).status_code == 200)
        check("variant edit persisted", sql("SELECT variant_name, variant_price, quantity, minimum_buying_count FROM zg_variant WHERE variant_id=%s", [va])[0][0:4] == ("A2", 11, 7, 2))
        bad = product_api("patch", {"id": pid, "price": "abc"})
        check("invalid product input -> 400, nothing saved", bad.status_code == 400 and sql("SELECT product_price FROM zg_product WHERE product_id=%s", [pid])[0][0] == 111)
        check("product edit kept its image, banner and variants", sql("SELECT count(*) FROM zg_product_images WHERE product_id=%s", [pid])[0][0] == 1
              and sql("SELECT count(*) FROM zg_discount_banners WHERE product_id=%s", [pid])[0][0] == 1 and sql("SELECT count(*) FROM zg_variant WHERE product_id=%s", [pid])[0][0] == 2)

        # ---- 4. variant delete: only that row
        response = variant_api("delete", id=vb)
        check("delete unreferenced variant -> 204", response.status_code == 204)
        check("only that variant is gone", sql("SELECT count(*) FROM zg_variant WHERE variant_id=%s", [vb])[0][0] == 0 and sql("SELECT count(*) FROM zg_variant WHERE variant_id=%s", [va])[0][0] == 1)
        check("deleting it again -> 404", variant_api("delete", id=vb).status_code == 404)

        # ---- 5. protected records are preserved
        protected = sql("SELECT DISTINCT product_id FROM zg_order_items WHERE product_id IS NOT NULL ORDER BY 1")
        check("existing data has an order-referenced product to test with", len(protected) > 0, protected)
        for (ordered_pid,) in protected:
            variants_before = sql("SELECT count(*) FROM zg_variant WHERE product_id=%s", [ordered_pid])[0][0]
            response = product_api("delete", id=ordered_pid)
            check("delete ordered product %s -> 409 with archive instruction" % ordered_pid, response.status_code == 409 and "Hidden" in response.data["detail"], response.data)
            check("ordered product %s and its variants still exist" % ordered_pid, sql("SELECT count(*) FROM zg_product WHERE product_id=%s", [ordered_pid])[0][0] == 1
                  and sql("SELECT count(*) FROM zg_variant WHERE product_id=%s", [ordered_pid])[0][0] == variants_before)
        for (ordered_vid,) in sql("SELECT DISTINCT variant_id FROM zg_order_items WHERE variant_id > 0 ORDER BY 1"):
            response = variant_api("delete", id=ordered_vid)
            check("delete ordered variant %s -> 409" % ordered_vid, response.status_code == 409 and "order history" in response.data["detail"], response.data)
        check("archive workflow: hiding a protected product works", product_api("patch", {"id": protected[0][0], "visible": "0"}).status_code == 200)

        # cart-protected and stock-protected probe product
        sql("INSERT INTO a_cart (id, cart_id, username, product_id, variant_id, qty) VALUES ((SELECT COALESCE(MAX(id),0)+1 FROM a_cart), 'zz', 'zz_probe_user', %s, %s, 1)", [pid, va])
        response = product_api("delete", id=pid)
        check("delete product that is in a customer cart -> 409", response.status_code == 409 and "carts" in response.data["detail"], response.data)
        check("cart-protected product, variant and banner intact", sql("SELECT count(*) FROM zg_product WHERE product_id=%s", [pid])[0][0] == 1
              and sql("SELECT count(*) FROM zg_variant WHERE product_id=%s", [pid])[0][0] == 1 and sql("SELECT count(*) FROM zg_discount_banners WHERE product_id=%s", [pid])[0][0] == 1)
        sql("DELETE FROM a_cart WHERE username='zz_probe_user'")

        # ---- 6. a deletable product (with banner, image, variant, favourite) is removed together with its owned rows only
        other_products = sql("SELECT count(*) FROM zg_product WHERE product_id<>%s", [pid])[0][0]
        response = product_api("delete", id=pid)
        check("delete unreferenced product (banner + image + variant + favourite) -> 204", response.status_code == 204, getattr(response, "data", ""))
        check("product and every owned child row are gone", all(sql("SELECT count(*) FROM " + t + " WHERE product_id=%s", [pid])[0][0] == 0 for t in
                                                                   ("zg_product", "zg_variant", "zg_product_images", "zg_discount_banners", "zg_favorites")))
        check("no other product was deleted", sql("SELECT count(*) FROM zg_product")[0][0] == other_products)
        check("repeat delete -> 404", product_api("delete", id=pid).status_code == 404)
        raise Rollback()
except Rollback:
    print("transaction rolled back")

after_counts = counts()
check("row counts identical after rollback", after_counts == before_counts, after_counts)
check("product and variant rows identical after rollback", snapshot() == before_snapshot)
failed = [label for label, ok in results if not ok]
print("\n%d checks, %d failed" % (len(results), len(failed)))
sys.exit(1 if failed else 0)
