"""Cart regression tests: several products in one cart, quantity changes, removal, isolation, totals.

Evidence level: UNIT / REGRESSION against a stateful in-memory stand-in for the SQL helper layer. The real
views (product_api_cart, cart_action, cart_api_test, checkout) and the real routing/auth gate run; only
the SQL helper layer is replaced by a stateful in-memory fake.
The fake rejects any SQL it does not recognise, so a change to the cart SQL fails loudly here instead of
silently passing.
"""
import json
from contextlib import contextmanager, nullcontext
from datetime import datetime
from decimal import Decimal
from unittest import mock

from django.test import Client, RequestFactory, SimpleTestCase

from legacy_api import views_cart, views_commerce, views_finance
from legacy_api.tests_auth import BEARER, authed, body_of, post

rf = RequestFactory()
ALICE = {"id": 7, "username": "alice", "email": "alice@example.invalid", "fullname": "Alice",
         "phone": "111", "address": "a"}
BOB = {"id": 8, "username": "bob", "email": "bob@example.invalid", "fullname": "Bob",
       "phone": "222", "address": "b"}

# product_id -> catalogue row. 11/12 have no variant rows (carted as variant 0); 13 has two variants.
PRODUCTS = {
    11: {"name": "Product A", "price": 100.0, "view": "1"},
    12: {"name": "Product B", "price": 50.0, "view": "1", "has_disc": 1, "discount_percent": 10, "product_discount": 10},
    13: {"name": "Product C", "price": 20.0, "view": "1", "gst_applicable": "Y", "gst_price": 2.5},
    14: {"name": "Hidden", "price": 5.0, "view": "0"},
    # Product 15 has no variants: GST follows the product flag and the product GST amount (20). The stale product
    # percentage (18) is deliberately left in place to prove it no longer affects any calculation.
    15: {"name": "Stale Percentage GST", "price": 100.0, "view": "1", "gst_applicable": "Y", "gst_percentage": 18, "gst_price": 20.0},
    # Product 16 is the business example: three GST-enabled variants with configured amounts 120 / 135 / 145 and
    # selling prices that are deliberately unrelated to those amounts.
    16: {"name": "Example Product", "price": 1.0, "view": "1", "gst_applicable": "Y", "gst_price": 0},
}
VARIANTS = {101: {"product_id": 13, "name": "Small", "price": 20.0, "gst": "N", "gst_price": 12.0},
            102: {"product_id": 13, "name": "Large", "price": 30.0, "gst": "Y", "gst_price": 4.25},
            201: {"product_id": 16, "name": "V120", "price": 999.0, "gst": "Y", "gst_price": 120.0},
            202: {"product_id": 16, "name": "V135", "price": 50.0, "gst": "Y", "gst_price": 135.0},
            203: {"product_id": 16, "name": "V145", "price": 1000.0, "gst": "Y", "gst_price": 145.0}}


class FakeCartDb:
    """Just enough of the SQL used by the cart endpoints to keep real rows in memory."""

    def __init__(self, customer_gst_percentage=Decimal("5")):
        self.lines = []
        self.next_id = 1
        self.statements = []
        # The authenticated customer's saved users.gst_percentage (what Customer Management stores).
        self.customer_gst_percentage = customer_gst_percentage

    # -- helpers
    def rows(self, username, variant_id=None, product_id=None):
        return [r for r in self.lines if r["username"] == username
                and (variant_id is None or r["variant_id"] == variant_id)
                and (product_id is None or r["product_id"] == product_id)]

    def count(self, username):
        return len(self.rows(username))

    def qty_of(self, username, product_id, variant_id):
        rows = self.rows(username, variant_id, product_id)
        return rows[0]["qty"] if rows else None

    def _joined(self, username):
        out = []
        for r in sorted(self.rows(username), key=lambda x: int(x["cart_id"])):
            product, variant = PRODUCTS.get(r["product_id"]), VARIANTS.get(r["variant_id"])
            if product is None:
                continue
            out.append({
                "cart_id": r["cart_id"], "product_id": r["product_id"], "variant_id": r["variant_id"],
                "qty": r["qty"], "created_at": datetime(2026, 10, 22, 9, 0, 0), "product_name": product["name"],
                "has_disc": product.get("has_disc", 0), "discount_percent": product.get("discount_percent", 0),
                "discount_value": 0, "product_discount": product.get("product_discount", 0),
                "product_gst_applicable": product.get("gst_applicable", "N"),
                "product_gst_percentage": product.get("gst_percentage"),
                "product_gst_price": product.get("gst_price", 0),
                "variant_name": variant["name"] if variant else ("" if r["variant_id"] == 0 else None),
                "variant_price": variant["price"] if variant else (product["price"] if r["variant_id"] == 0 else None),
                "variant_gst": variant.get("gst", "N") if variant else "N",
                # Mirrors the real SQL: variant 0 uses the product's configured GST amount.
                "variant_gst_price": variant.get("gst_price", 0) if variant else (
                    product.get("gst_price", 0) if r["variant_id"] == 0 else 0),
                "variant_quantity": 10 if (variant or r["variant_id"] == 0) else None,
                "stock_qty": 10 if (variant or r["variant_id"] == 0) else None,
                "main_image": product.get("image"), "image_path": None,
            })
        return out

    # -- SQL doubles
    def fetchone(self, sql, params=()):
        self.statements.append(sql)
        params = list(params)
        if "FROM zg_product WHERE product_id=%s AND view='1'" in sql:
            p = PRODUCTS.get(params[0])
            return {"product_id": params[0]} if p and p["view"] == "1" else None
        if "FROM zg_variant WHERE product_id=%s" in sql:
            return {"x": 1} if any(v["product_id"] == params[0] for v in VARIANTS.values()) else None
        if "FROM zg_variant WHERE variant_id=%s AND product_id=%s" in sql:
            v = VARIANTS.get(params[0])
            return {"x": 1} if v and v["product_id"] == params[1] else None
        if sql.startswith("SELECT qty FROM a_cart WHERE username=%s AND product_id=%s AND variant_id=%s"):
            rows = self.rows(params[0], params[2], params[1])
            return {"qty": rows[0]["qty"]} if rows else None
        if sql.startswith("SELECT id, email, gst_percentage, delivery_charges, vip_discount, vip_percentage FROM users"):
            return {"id": 7, "email": "alice@example.invalid", "gst_percentage": self.customer_gst_percentage,
                    "delivery_charges": 0, "vip_discount": None, "vip_percentage": 0}
        if sql.startswith("SELECT email, gst_percentage, delivery_charges, vip_discount, vip_percentage FROM users"):
            return {"email": "alice@example.invalid", "gst_percentage": self.customer_gst_percentage,
                    "delivery_charges": 0, "vip_discount": None, "vip_percentage": 0}
        if sql.startswith("SELECT delivery_charges, vip_discount, vip_percentage FROM users"):
            return {"delivery_charges": 0, "vip_discount": None, "vip_percentage": 0}
        if sql.startswith("SELECT id,profile_picture,shop_name"):
            return {"id": 7, "profile_picture": None, "shop_name": "Shop", "fullname": "Alice", "address": "a",
                    "city": "c", "created_at": datetime(2026, 1, 1), "username": params[0], "phone": "1",
                    "email": "a@example.invalid", "status": "ACTIVE", "vip_discount": None, "vip_percentage": 0,
                    "store_maped": "N", "delivery_charges": 0, "gst_percentage": self.customer_gst_percentage}
        raise AssertionError("unexpected fetchone SQL: " + sql)

    def fetchall(self, sql, params=()):
        self.statements.append(sql)
        params = list(params)
        if sql.startswith("SELECT product_id, qty FROM a_cart WHERE username=%s AND variant_id=%s"):
            return [{"product_id": r["product_id"], "qty": r["qty"]}
                    for r in sorted(self.rows(params[0], params[1]), key=lambda x: x["id"])]
        if "FROM a_cart c LEFT JOIN zg_product p" in sql:
            return self._joined(params[0])
        if "FROM zg_checkout o LEFT JOIN zg_order_items oi" in sql:
            return []
        raise AssertionError("unexpected fetchall SQL: " + sql)

    def execute(self, sql, params=()):
        self.statements.append(sql)
        params = list(params)
        if sql.startswith("INSERT INTO a_cart"):
            cart_id, username, product_id, variant_id, qty = params
            self.lines.append({"id": self.next_id, "cart_id": str(cart_id), "username": username,
                               "product_id": product_id, "variant_id": variant_id, "qty": qty})
            self.next_id += 1
            return 1
        if sql.startswith("UPDATE a_cart SET qty=LEAST(qty+%s, %s) WHERE username=%s AND product_id=%s"):
            add, cap, username, product_id, variant_id = params
            hit = self.rows(username, variant_id, product_id)
            for r in hit:
                r["qty"] = min(r["qty"] + add, cap)
            return len(hit)
        if sql.startswith("UPDATE a_cart SET qty=LEAST(qty+1, %s) WHERE username=%s AND variant_id=%s AND product_id=%s"):
            cap, username, variant_id, product_id = params
            hit = self.rows(username, variant_id, product_id)
            for r in hit:
                r["qty"] = min(r["qty"] + 1, cap)
            return len(hit)
        if sql.startswith("UPDATE a_cart SET qty=qty-1 WHERE username=%s AND variant_id=%s AND product_id=%s"):
            username, variant_id, product_id = params
            hit = self.rows(username, variant_id, product_id)
            for r in hit:
                r["qty"] -= 1
            return len(hit)
        if sql.startswith("DELETE FROM a_cart WHERE username=%s AND variant_id=%s AND product_id=%s"):
            username, variant_id, product_id = params
            hit = self.rows(username, variant_id, product_id)
            self.lines = [r for r in self.lines if r not in hit]
            return len(hit)
        raise AssertionError("unexpected execute SQL: " + sql)


@contextmanager
def cart_env(db, user=ALICE):
    """Authenticated request context whose SQL layer is the stateful fake."""
    with authed(user), mock.patch("django.db.transaction.atomic", return_value=nullcontext()), \
            mock.patch.object(views_commerce, "current_available_credit", return_value=(0.0, 0.0, 0.0)), \
            mock.patch.object(views_cart, "lock_user_cart") as lock_cart, \
            mock.patch.object(views_commerce, "lock_user_cart") as lock_commerce:
        patches = []
        for module in (views_cart, views_commerce, views_finance):
            for name in ("fetchone", "fetchall", "execute"):
                if hasattr(module, name):
                    patches.append(mock.patch.object(module, name, getattr(db, name)))
        for p in patches:
            p.start()
        try:
            yield SimpleLocks(lock_cart, lock_commerce)
        finally:
            for p in patches:
                p.stop()


class SimpleLocks:
    def __init__(self, cart, commerce):
        self.cart, self.commerce = cart, commerce


def add(product_id, *variants):
    """Add-to-cart exactly as Flutter sends it: product_id as a STRING plus [{variant_id, qty}]."""
    body = {"product_id": str(product_id), "variants": [{"variant_id": v, "qty": q} for v, q in variants]}
    return views_commerce.product_api_cart(post("/api/product-api-cart", body, **BEARER))


def action(name, variant_id, product_id):
    body = {"product_id": product_id, "variant_id": variant_id, "action": name}
    return views_cart.cart_action(post("/api/cart_action", body, **BEARER))


def fetch_cart():
    return body_of(views_commerce.cart_api_test(rf.get("/api/cart_api_test", **BEARER)))


def cart_lines(cart):
    """[(group key, product name, variant_id, quantity)] across both discount buckets."""
    out = []
    for bucket in ("discount_available", "discount_not_available"):
        for key, group in cart["cart_items"][bucket].items():
            for item in group["items"]:
                out.append((key, item["product_name"], item["variant_id"], item["quantity"]))
    return out


def names(cart):
    return sorted(line[1] for line in cart_lines(cart))


class AddMultipleProductsTests(SimpleTestCase):
    def test_a_different_products_both_stay_in_the_cart(self):
        db = FakeCartDb()
        with cart_env(db):
            self.assertEqual(body_of(add(11, (0, 2)))["status"], "success")
            self.assertEqual(body_of(add(12, (0, 3)))["status"], "success")
            cart = fetch_cart()
        self.assertEqual(db.count("alice"), 2)
        self.assertEqual(names(cart), ["Product A", "Product B"])
        self.assertEqual(cart["cart_items"]["final_summary"]["total_cart_items"], 5)
        self.assertEqual(cart["cart_items"]["final_summary"]["items_subtotal"], 335.0)  # 200 + 150 less B's 10%

    def test_a_product_with_variants_and_a_variantless_product_coexist(self):
        db = FakeCartDb()
        with cart_env(db):
            add(13, (101, 1), (102, 4))
            add(11, (0, 1))
            cart = fetch_cart()
        self.assertEqual(sorted((l[1], l[2], l[3]) for l in cart_lines(cart)),
                         [("Product A", 0, 1), ("Product C", 101, 1), ("Product C", 102, 4)])
        # Variant 101 is GST-disabled despite a stored non-zero GST amount; only variant 102 is taxed:
        # 4.25 configured x 4 units x customer 5% / 100 = 0.85 (selling price is irrelevant).
        self.assertEqual(cart["cart_items"]["final_summary"]["GST"], 0.85)

    def test_all_gst_disabled_products_have_zero_cart_gst(self):
        db = FakeCartDb()
        with cart_env(db):
            add(13, (101, 2))
            add(11, (0, 1))
            cart = fetch_cart()
        self.assertEqual(cart["cart_items"]["final_summary"]["GST"], 0.0)

    def test_variant_gst_is_authoritative_when_parent_product_flag_is_disabled(self):
        db = FakeCartDb()
        previous = PRODUCTS[13].get('gst_applicable')
        PRODUCTS[13]['gst_applicable'] = 'N'
        try:
            with cart_env(db):
                add(13, (102, 2))
                cart = fetch_cart()
        finally:
            if previous is None:
                PRODUCTS[13].pop('gst_applicable', None)
            else:
                PRODUCTS[13]['gst_applicable'] = previous
        self.assertEqual(cart['cart_items']['final_summary']['GST'], 0.43)
    def _set(self, mapping, key, value):
        """Temporarily change fixture data; restored automatically after the test."""
        previous = mapping[key]
        mapping[key] = value
        self.addCleanup(mapping.__setitem__, key, previous)

    @staticmethod
    def _line_gst(cart):
        """{(product name, variant id): per-line gst_amount} across both discount buckets."""
        out = {}
        for bucket in ("discount_available", "discount_not_available"):
            for group in cart["cart_items"][bucket].values():
                for item in group["items"]:
                    out[(item["product_name"], item["variant_id"])] = item["gst_amount"]
        return out

    @staticmethod
    def _checkout():
        return body_of(views_commerce.checkout(rf.get("/api/checkout", **BEARER)))["checkout_data"]["cart_summary"]

    def _example_cart(self, db):
        add(16, (201, 1), (202, 1), (203, 1))

    def test_checkout_preview_uses_the_same_authoritative_gst_flags(self):
        db = FakeCartDb(customer_gst_percentage=Decimal("10"))
        with cart_env(db):
            add(13, (102, 2))
            summary = self._checkout()
        # 4.25 configured x 2 units x customer 10% / 100 = 0.85; items total 60 (30 x 2) is untouched.
        self.assertEqual(summary["gst_amount"], 0.85)
        self.assertEqual(summary["total_with_gst"], 60.85)

    def test_business_example_three_variants_at_5_percent_total_20(self):
        db = FakeCartDb()  # customer saved GST percentage = 5
        with cart_env(db):
            self._example_cart(db)
            cart = fetch_cart()
            checkout = self._checkout()
        lines = self._line_gst(cart)
        self.assertEqual([lines[("Example Product", v)] for v in (201, 202, 203)], [6.0, 6.75, 7.25])
        self.assertEqual(cart["cart_items"]["final_summary"]["GST"], 20.0)
        self.assertEqual(checkout["gst_amount"], 20.0)

    def test_gst_does_not_depend_on_the_selling_price(self):
        db = FakeCartDb()
        self._set(VARIANTS[201], "price", 1.0)
        self._set(VARIANTS[202], "price", 123456.0)
        self._set(VARIANTS[203], "price", 0.0)
        with cart_env(db):
            self._example_cart(db)
            gst = fetch_cart()["cart_items"]["final_summary"]["GST"]
        self.assertEqual(gst, 20.0)

    def test_quantity_two_doubles_the_calculated_gst(self):
        db = FakeCartDb()
        with cart_env(db):
            add(16, (201, 2))
            cart = fetch_cart()
            checkout = self._checkout()
        self.assertEqual(cart["cart_items"]["final_summary"]["GST"], 12.0)  # 120 x 2 x 5 / 100
    def test_variant_gst_is_used_even_when_parent_product_flag_is_disabled(self):
        db = FakeCartDb()
        self._set(PRODUCTS[16], 'gst_applicable', 'N')
        with cart_env(db):
            self._example_cart(db)
            cart = fetch_cart()
            checkout = self._checkout()
        self.assertEqual(cart['cart_items']['final_summary']['GST'], 20.0)
        self.assertEqual(checkout['gst_amount'], 20.0)

    def test_variant_level_gst_disabled_is_zero_for_that_variant_only(self):
        db = FakeCartDb()
        self._set(VARIANTS[202], 'gst', 'N')
        with cart_env(db):
            self._example_cart(db)
            cart = fetch_cart()
        lines = self._line_gst(cart)
        self.assertEqual(lines[('Example Product', 202)], 0.0)
        self.assertEqual(cart['cart_items']['final_summary']['GST'], 13.25)
        self.assertEqual(cart["cart_items"]["final_summary"]["GST"], 13.25)  # 6.00 + 7.25

    def test_missing_or_invalid_flags_fail_safe_to_zero(self):
        for flag in (None, "", "maybe", "n"):
            db = FakeCartDb()
            with self.subTest(flag=flag):
                with cart_env(db):
                    self._set(VARIANTS[201], "gst", flag)
                    add(16, (201, 1))
                    self.assertEqual(fetch_cart()["cart_items"]["final_summary"]["GST"], 0.0)

    def test_mixed_cart_sums_only_eligible_products_and_variants(self):
        db = FakeCartDb()
        with cart_env(db):
            add(16, (201, 1))      # eligible: 6.00
            add(11, (0, 3))        # product GST disabled
            add(13, (101, 2))      # variant GST disabled despite a stored amount (12)
            add(13, (102, 1))      # eligible: 4.25 x 5% = 0.2125 -> 0.21
            cart = fetch_cart()
            checkout = self._checkout()
        self.assertEqual(cart["cart_items"]["final_summary"]["GST"], 6.21)
        self.assertEqual(checkout["gst_amount"], 6.21)

    def test_missing_or_zero_customer_percentage_uses_variant_configured_gst_amount(self):
        for saved in (None, "", 0, Decimal("0"), Decimal("0.00")):
            db = FakeCartDb(customer_gst_percentage=saved)
            with self.subTest(saved=saved):
                with cart_env(db):
                    self._example_cart(db)
                    self.assertEqual(fetch_cart()["cart_items"]["final_summary"]["GST"], 400.0)
                    self.assertEqual(self._checkout()["gst_amount"], 400.0)
    def test_invalid_customer_percentages_cannot_trigger_gst(self):
        for saved in (-5, Decimal("-0.01"), 100.01, 101, 250, "abc", "NaN", "Infinity", "-Infinity", float("inf")):
            db = FakeCartDb(customer_gst_percentage=saved)
            with self.subTest(saved=saved):
                with cart_env(db):
                    self._example_cart(db)
                    self.assertEqual(fetch_cart()["cart_items"]["final_summary"]["GST"], 0.0)
                    self.assertEqual(self._checkout()["gst_amount"], 0.0)

    def test_changing_the_customers_saved_percentage_changes_cart_gst(self):
        db = FakeCartDb()
        with cart_env(db):
            self._example_cart(db)
            at_5 = fetch_cart()["cart_items"]["final_summary"]["GST"]
            db.customer_gst_percentage = Decimal("10")
            at_10 = fetch_cart()["cart_items"]["final_summary"]["GST"]
            db.customer_gst_percentage = Decimal("100")
            at_100 = fetch_cart()["cart_items"]["final_summary"]["GST"]
        self.assertEqual((at_5, at_10, at_100), (20.0, 40.0, 400.0))

    def test_client_cannot_forge_the_gst_percentage(self):
        db = FakeCartDb()
        forged = "?gst_percentage=99&customer_gst_percentage=99&gst=999&GST=999&gst_amount=999"
        with cart_env(db):
            self._example_cart(db)
            cart = body_of(views_commerce.cart_api_test(rf.get("/api/cart_api_test" + forged, **BEARER)))
            checkout = body_of(views_commerce.checkout(rf.get("/api/checkout" + forged, **BEARER)))["checkout_data"]["cart_summary"]
        self.assertEqual(cart["cart_items"]["final_summary"]["GST"], 20.0)
        self.assertEqual(checkout["gst_amount"], 20.0)

    def test_stale_product_percentage_is_ignored_and_price_is_never_taxed(self):
        db = FakeCartDb()
        with cart_env(db):
            add(15, (0, 2))   # price 100, stale product pct 18, configured GST amount 20
            first = fetch_cart()["cart_items"]["final_summary"]["GST"]
            action("increase", 0, 15)
            updated = fetch_cart()["cart_items"]["final_summary"]["GST"]
            checkout = self._checkout()
        self.assertEqual(first, 2.0)      # 20 x 2 x 5 / 100 (NOT 100 x 18% x 2 = 36, NOT 100 x 5% x 2 = 10)
        self.assertEqual(updated, 3.0)    # quantity change immediately changes GST
        self.assertEqual(checkout["gst_amount"], 3.0)

    def test_enabled_gst_without_a_configured_amount_does_not_invent_gst(self):
        db = FakeCartDb()
        self._set(PRODUCTS[15], "gst_price", 0)
        with cart_env(db):
            add(15, (0, 2))
            cart = fetch_cart()
        self.assertEqual(cart["cart_items"]["final_summary"]["GST"], 0.0)

    def test_cart_and_checkout_agree_for_a_mixed_cart(self):
        db = FakeCartDb(customer_gst_percentage=Decimal("7.5"))
        with cart_env(db):
            add(16, (201, 3), (203, 1))
            add(15, (0, 4))
            add(13, (102, 5))
            cart_gst = fetch_cart()["cart_items"]["final_summary"]["GST"]
            checkout_gst = self._checkout()["gst_amount"]
        self.assertEqual(cart_gst, checkout_gst)
        self.assertEqual(cart_gst, round(27.0 + 10.88 + 6.0 + 1.59, 2))  # 120x3 / 145 / 20x4 / 4.25x5 at 7.5%

    def test_cart_groups_are_keyed_by_real_product_id_so_flutter_can_send_it_back(self):
        db = FakeCartDb()
        with cart_env(db):
            add(11, (0, 1))
            add(12, (0, 1))
            cart = fetch_cart()
        keys = {line[1]: line[0] for line in cart_lines(cart)}
        self.assertEqual(keys, {"Product A": "11", "Product B": "12"})

    def test_cart_response_keeps_the_legacy_keys_and_never_leaks_the_internal_marker(self):
        db = FakeCartDb()
        with cart_env(db):
            add(11, (0, 1))
            cart = fetch_cart()
        self.assertEqual(sorted(cart["cart_items"]), ["discount", "discount_available", "discount_not_available",
                                                      "final_summary", "mov"])
        self.assertNotIn("_product_id", json.dumps(cart))
        item = cart_lines(cart)[0]
        self.assertEqual(item[1:], ("Product A", 0, 1))

    def test_empty_cart_keeps_the_legacy_group_shape(self):
        db = FakeCartDb()
        with cart_env(db):
            cart = fetch_cart()
        self.assertEqual(cart["cart_items"]["discount_available"]["1"]["items"], [])
        self.assertEqual(cart["cart_items"]["discount_not_available"]["2"]["items"], [])

    def test_b_adding_the_same_product_again_increments_one_line(self):
        db = FakeCartDb()
        with cart_env(db):
            add(11, (0, 2))
            add(12, (0, 1))
            add(11, (0, 3))
            cart = fetch_cart()
        self.assertEqual(db.count("alice"), 2)
        self.assertEqual(db.qty_of("alice", 11, 0), 5)
        self.assertEqual(db.qty_of("alice", 12, 0), 1)
        self.assertEqual(names(cart), ["Product A", "Product B"])

    def test_add_never_removes_or_overwrites_existing_lines(self):
        db = FakeCartDb()
        with cart_env(db):
            add(11, (0, 2))
            before = [dict(r) for r in db.lines]
            add(12, (0, 1))
            add(13, (101, 1))
        for old in before:
            self.assertIn(old, db.lines)
        self.assertFalse(any(sql.startswith("DELETE") for sql in db.statements))

    def test_add_takes_the_per_user_cart_lock(self):
        db = FakeCartDb()
        with cart_env(db) as locks:
            add(11, (0, 1))
        locks.commerce.assert_called_once_with("alice")


class ChangeAndRemoveTests(SimpleTestCase):
    def setUp(self):
        self.db = FakeCartDb()

    def seed(self):
        add(11, (0, 2))
        add(12, (0, 3))

    def test_c_remove_one_variantless_product_leaves_the_other(self):
        with cart_env(self.db):
            self.seed()
            cart = fetch_cart()
            key_a = next(l[0] for l in cart_lines(cart) if l[1] == "Product A")
            result = body_of(action("remove", 0, int(key_a)))   # what Flutter sends: the group key as product_id
            after = fetch_cart()
        self.assertTrue(result["status"])
        self.assertEqual(result["affected_rows"], 1)
        self.assertEqual(names(after), ["Product B"])
        self.assertEqual(self.db.qty_of("alice", 12, 0), 3)

    def test_c_remove_one_variant_of_a_product_leaves_other_products_and_variants(self):
        with cart_env(self.db):
            add(13, (101, 1), (102, 2))
            add(11, (0, 1))
            result = body_of(action("remove", 101, 999))        # product_id is only a hint for real variants
            after = fetch_cart()
        self.assertEqual(result["affected_rows"], 1)
        self.assertEqual(sorted((l[1], l[2]) for l in cart_lines(after)), [("Product A", 0), ("Product C", 102)])

    def test_d_increase_and_decrease_change_only_the_targeted_line(self):
        with cart_env(self.db):
            self.seed()
            self.assertTrue(body_of(action("increase", 0, 12))["status"])
            self.assertEqual(self.db.qty_of("alice", 12, 0), 4)
            self.assertEqual(self.db.qty_of("alice", 11, 0), 2)
            self.assertTrue(body_of(action("decrease", 0, 12))["status"])
            self.assertEqual(self.db.qty_of("alice", 12, 0), 3)
            self.assertEqual(self.db.qty_of("alice", 11, 0), 2)

    def test_d_decrease_of_the_last_piece_deletes_only_that_line(self):
        with cart_env(self.db):
            add(11, (0, 1))
            add(12, (0, 4))
            body_of(action("decrease", 0, 11))
        self.assertIsNone(self.db.qty_of("alice", 11, 0))
        self.assertEqual(self.db.qty_of("alice", 12, 0), 4)

    def test_increase_is_capped_at_the_maximum_line_quantity(self):
        with cart_env(self.db):
            add(11, (0, views_commerce.MAX_CART_QTY))
            action("increase", 0, 11)
        self.assertEqual(self.db.qty_of("alice", 11, 0), views_commerce.MAX_CART_QTY)

    def test_stale_group_key_with_several_variantless_lines_changes_nothing(self):
        with cart_env(self.db):
            self.seed()
            before = [dict(r) for r in self.db.lines]
            for name in ("remove", "increase", "decrease"):
                result = body_of(action(name, 0, 1))             # legacy fixed group key, not a product
                self.assertFalse(result["status"])
                self.assertIn("ambiguous", result["message"])
        self.assertEqual(self.db.lines, before)

    def test_legacy_group_key_still_works_when_only_one_variantless_line_exists(self):
        with cart_env(self.db):
            add(11, (0, 2))
            result = body_of(action("remove", 0, 1))
        self.assertEqual(result["affected_rows"], 1)
        self.assertEqual(self.db.count("alice"), 0)

    def test_removing_a_line_that_is_not_in_the_cart_changes_nothing(self):
        with cart_env(self.db):
            add(11, (0, 2))
            result = body_of(action("remove", 101, 13))
        self.assertEqual(result, {"status": True, "affected_rows": 0, "message": "Cart updated successfully."})
        self.assertEqual(self.db.qty_of("alice", 11, 0), 2)

    def test_decrease_of_a_missing_line_is_reported_as_not_found(self):
        with cart_env(self.db):
            result = body_of(action("decrease", 101, 13))
        self.assertFalse(result["status"])
        self.assertEqual(result["message"], "Product not found in cart.")

    def test_cart_action_takes_the_per_user_cart_lock(self):
        with cart_env(self.db) as locks:
            action("remove", 0, 11)
        locks.cart.assert_called_once_with("alice")

    def test_invalid_action_inputs_are_rejected_without_touching_the_cart(self):
        with cart_env(self.db):
            add(11, (0, 2))
            before = [dict(r) for r in self.db.lines]
            for body in ({"variant_id": 0, "action": "explode", "product_id": 11},
                         {"variant_id": 0, "product_id": 11},
                         {"action": "remove", "product_id": 11},
                         {"action": "remove", "variant_id": -1, "product_id": 11},
                         {"action": "remove", "variant_id": "x", "product_id": 11},
                         {"action": "remove", "variant_id": 0, "product_id": "abc"}):
                with self.subTest(body=body):
                    result = body_of(views_cart.cart_action(post("/api/cart_action", body, **BEARER)))
                    self.assertFalse(result["status"])
        self.assertEqual(self.db.lines, before)

    def test_cart_action_only_allows_post(self):
        with cart_env(self.db):
            response = views_cart.cart_action(rf.get("/api/cart_action", **BEARER))
        self.assertEqual(response.status_code, 405)


class UserIsolationTests(SimpleTestCase):
    def test_e_carts_do_not_leak_between_users(self):
        db = FakeCartDb()
        with cart_env(db, ALICE):
            add(11, (0, 2))
            add(12, (0, 1))
        with cart_env(db, BOB):
            bob_cart = fetch_cart()
            add(13, (101, 1))
            bob_after = fetch_cart()
        with cart_env(db, ALICE):
            alice_cart = fetch_cart()
        self.assertEqual(cart_lines(bob_cart), [])
        self.assertEqual(names(bob_after), ["Product C"])
        self.assertEqual(names(alice_cart), ["Product A", "Product B"])

    def test_e_another_users_action_cannot_touch_my_lines(self):
        db = FakeCartDb()
        with cart_env(db, ALICE):
            add(11, (0, 2))
        with cart_env(db, BOB):
            result = body_of(action("remove", 0, 11))
            body_of(action("increase", 0, 11))
        self.assertEqual(result["affected_rows"], 0)
        self.assertEqual(db.qty_of("alice", 11, 0), 2)

    def test_the_username_in_the_body_is_ignored(self):
        db = FakeCartDb()
        with cart_env(db, ALICE):
            body = {"product_id": "11", "username": "mallory", "variants": [{"variant_id": 0, "qty": 1}]}
            views_commerce.product_api_cart(post("/api/product-api-cart", body, **BEARER))
        self.assertEqual(db.count("alice"), 1)
        self.assertEqual(db.count("mallory"), 0)


class InvalidAddTests(SimpleTestCase):
    def test_invalid_product_ids_are_rejected(self):
        db = FakeCartDb()
        with cart_env(db):
            self.assertEqual(add(999, (0, 1)).status_code, 404)    # unknown product
            self.assertEqual(add(14, (0, 1)).status_code, 404)     # hidden product
            for bad in (0, -3, "abc", None):
                body = {"product_id": bad, "variants": [{"variant_id": 0, "qty": 1}]}
                response = views_commerce.product_api_cart(post("/api/product-api-cart", body, **BEARER))
                self.assertEqual(response.status_code, 400, bad)
        self.assertEqual(db.count("alice"), 0)

    def test_invalid_quantities_are_rejected_and_nothing_is_saved(self):
        db = FakeCartDb()
        with cart_env(db):
            for qty in (0, -1, "x", None, views_commerce.MAX_CART_QTY + 1):
                response = add(11, (0, qty))
                self.assertEqual(response.status_code, 400, qty)
                self.assertEqual(body_of(response)["status"], "error")
        self.assertEqual(db.count("alice"), 0)

    def test_invalid_variants_are_rejected(self):
        db = FakeCartDb()
        with cart_env(db):
            self.assertEqual(add(11, (101, 1)).status_code, 400)   # variant of another product
            self.assertEqual(add(13, (0, 1)).status_code, 400)     # variant 0 on a product that has variants
            self.assertEqual(add(13, (555, 1)).status_code, 400)   # unknown variant
            body = {"product_id": "11", "variants": "nope"}
            self.assertEqual(views_commerce.product_api_cart(post("/api/product-api-cart", body, **BEARER)).status_code, 400)
        self.assertEqual(db.count("alice"), 0)

    def test_one_bad_variant_does_not_block_the_valid_ones(self):
        db = FakeCartDb()
        with cart_env(db):
            response = add(13, (101, 1), (555, 2), (102, 0))
        self.assertEqual(body_of(response)["inserted_items"], 1)
        self.assertEqual(db.count("alice"), 1)


class UnauthenticatedTests(SimpleTestCase):
    def test_cart_routes_reject_missing_and_malformed_tokens_before_touching_data(self):
        client = Client()
        for path, method in (("/api/product-api-cart", "post"), ("/api/cart_action", "post"),
                             ("/api/cart_api_test", "get"), ("/api/checkout", "get")):
            for headers in ({}, {"HTTP_AUTHORIZATION": "Bearer"}, {"HTTP_AUTHORIZATION": "Basic abc"}):
                with self.subTest(path=path, headers=headers):
                    response = getattr(client, method)(path, **headers)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(json.loads(response.content)["status"], "session_expired")


class CheckoutTotalsTests(SimpleTestCase):
    def checkout(self):
        return body_of(views_commerce.checkout(rf.get("/api/checkout", **BEARER)))["checkout_data"]["cart_summary"]

    def test_checkout_counts_every_persisted_line_and_follows_removals(self):
        db = FakeCartDb()
        with cart_env(db):
            add(11, (0, 2))      # 2 x 100            = 200
            add(12, (0, 3))      # 3 x 50 less 10%    = 135
            full = self.checkout()
            action("remove", 0, 11)
            remaining = self.checkout()
        self.assertEqual((full["total_items"], full["total_quantity"], full["total_price"]), (2, 5, 335))
        self.assertEqual((remaining["total_items"], remaining["total_quantity"], remaining["total_price"]), (1, 3, 135))

    def test_cart_summary_follows_changes_to_one_line_only(self):
        db = FakeCartDb()
        with cart_env(db):
            add(11, (0, 2))
            add(12, (0, 3))
            action("increase", 0, 12)
            summary = fetch_cart()["cart_items"]["final_summary"]
        self.assertEqual(summary["total_cart_items"], 6)
        self.assertEqual(db.qty_of("alice", 11, 0), 2)


from legacy_api.cart_discount_testing import module_fixtures
setUpModule, tearDownModule = module_fixtures()  # no saved cart-discount row: promotion unconfigured, no DB access
