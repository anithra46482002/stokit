"""GST regression tests: customer GST percentage x admin-configured GST amount (never the selling price).

Evidence level: UNIT / REGRESSION against the in-memory SQL stand-in from tests_cart plus pure rule tests.
Uses isolated fake data only; no database, no migrations.
"""
import inspect
from decimal import Decimal

from django.test import RequestFactory, SimpleTestCase

from legacy_api import views_commerce
from legacy_api.tests_auth import BEARER, body_of
from legacy_api.tests_cart import PRODUCTS, FakeCartDb, add, cart_env, fetch_cart
from legacydb import gst_rules
from legacydb.gst_rules import (calculate_gst_amount, customer_gst_rate, effective_gst_settings,
                                validate_gst_configuration)

rf = RequestFactory()
D = Decimal


def _summary(cart):
    return cart["cart_items"]["final_summary"]


def line(amount, qty=1, pct=5, **extra):
    kwargs = dict(quantity=qty, product_gst_applicable="Y", variant_gst="Y", is_variant=True,
                  configured_amount=amount, customer_gst_percentage=pct)
    kwargs.update(extra)
    return calculate_gst_amount(**kwargs)


class CentralRuleTests(SimpleTestCase):
    def test_business_example_120_135_145_at_5_percent_is_20(self):
        lines = [line(120), line(135), line(145)]
        self.assertEqual(lines, [D("6.00"), D("6.75"), D("7.25")])
        self.assertEqual(sum(lines), D("20.00"))

    def test_the_rule_has_no_price_input_so_it_cannot_depend_on_the_selling_price(self):
        for fn in (calculate_gst_amount, effective_gst_settings):
            self.assertFalse({"unit_price", "price", "selling_price"} & set(inspect.signature(fn).parameters))

    def test_quantity_multiplies_the_configured_amount_before_the_percentage(self):
        self.assertEqual(line(120, qty=2), D("12.00"))
        self.assertEqual(line(135, qty=3), D("20.25"))
        self.assertEqual(line(120, qty=0), D("0.00"))
        self.assertEqual(line(120, qty=-4), D("0.00"))

    def test_rounding_is_half_up_to_cents_once_per_line(self):
        self.assertEqual(line(Decimal("4.25"), qty=1, pct=5), D("0.21"))    # 0.2125
        self.assertEqual(line(Decimal("8.50"), qty=1, pct=5), D("0.43"))    # 0.425 -> half up
        self.assertEqual(line(Decimal("0.10"), qty=1, pct=5), D("0.01"))    # 0.005 -> half up

    def test_variant_level_flag_controls_variant_gst_even_if_parent_product_flag_is_disabled(self):
        for flag in ('N', 'n', None, '', 'maybe', 0):
            self.assertEqual(line(120, product_gst_applicable=flag), D('6.00'), flag)
    def test_variant_level_disabled_is_zero_for_a_variant_line(self):
        for flag in ("N", None, "", "x"):
            self.assertEqual(line(120, variant_gst=flag), D("0.00"), flag)

    def test_product_without_variants_follows_product_flag_and_product_amount(self):
        self.assertEqual(calculate_gst_amount(quantity=2, product_gst_applicable="Y", is_variant=False,
                                              configured_amount=50, customer_gst_percentage=5), D("5.00"))
        self.assertEqual(calculate_gst_amount(quantity=2, product_gst_applicable="N", is_variant=False,
                                              configured_amount=50, customer_gst_percentage=5), D("0.00"))

    def test_an_amount_alone_never_enables_gst_and_enabled_without_amount_is_zero(self):
        self.assertEqual(line(0), D("0.00"))
        self.assertEqual(line(None), D("0.00"))
        self.assertEqual(line(-5), D("0.00"))  # negative configured amount fails safe

    def test_blank_or_zero_customer_percentage_uses_configured_gst_amount_directly(self):
        for pct in (None, "", "   ", 0, "0", D("0.00")):
            self.assertEqual(line(120, pct=pct), D("120.00"), repr(pct))
            self.assertEqual(customer_gst_rate(pct), D("0.00"), repr(pct))
    def test_invalid_customer_percentages_are_zero_gst(self):
        for pct in (-1, "-0.5", 100.01, 101, 1000, "abc", "NaN", "Infinity", "-Infinity", float("nan"), float("inf"), True):
            self.assertEqual(line(120, pct=pct), D("0.00"), repr(pct))

    def test_boundary_percentages_are_accepted(self):
        self.assertEqual(line(120, pct=100), D("120.00"))
        self.assertEqual(line(120, pct=D("0.01")), D("0.01"))

    def test_no_hardcoded_rate_any_saved_percentage_is_used_as_is(self):
        for pct in (5, 9, 12, 18, 28, D("7.5")):
            self.assertEqual(line(100, pct=pct), (D("100") * D(str(pct)) / 100).quantize(D("0.01")))

    def test_disabled_settings_report_zero_numbers(self):
        s = effective_gst_settings(product_gst_applicable="N", configured_amount=9, customer_gst_percentage=18)
        self.assertEqual(s, {"applicable": "N", "percentage": D("0.00"), "amount": D("0.00")})
        s = effective_gst_settings(product_gst_applicable="Y", variant_gst="Y", is_variant=True,
                                   configured_amount=9, customer_gst_percentage=5)
        self.assertEqual((s["applicable"], s["percentage"], s["amount"]), ("Y", D("5"), D("9")))

    def test_the_product_percentage_column_is_no_longer_an_input(self):
        self.assertNotIn("gst_percentage", inspect.signature(effective_gst_settings).parameters)
        self.assertNotIn("gst_percentage", inspect.signature(calculate_gst_amount).parameters)

    def test_admin_validation_gives_clear_errors(self):
        self.assertIn("between 0 and 100", validate_gst_configuration(percentage=150))
        self.assertIn("cannot be negative", validate_gst_configuration(amount=-1))
        self.assertIn("finite", validate_gst_configuration(percentage="abc"))
        self.assertIsNone(validate_gst_configuration(percentage=18, amount=0))

    def test_module_constants_have_no_gst_rate(self):
        self.assertFalse([n for n in dir(gst_rules) if "RATE" in n.upper() and n != "customer_gst_rate"])


class CartCheckoutFlowTests(SimpleTestCase):
    def _toggle(self, mapping, key, value):
        previous = mapping[key]
        mapping[key] = value
        self.addCleanup(mapping.__setitem__, key, previous)

    def test_enabled_to_disabled_then_back_recalculates_current_cart(self):
        db = FakeCartDb()
        with cart_env(db):
            add(15, (0, 2))  # configured amount 20, customer 5%, qty 2
            enabled = _summary(fetch_cart())["GST"]
            self._toggle(PRODUCTS[15], "gst_applicable", "N")
            disabled = _summary(fetch_cart())
            checkout = body_of(views_commerce.checkout(rf.get("/api/checkout", **BEARER)))["checkout_data"]["cart_summary"]
            self._toggle(PRODUCTS[15], "gst_applicable", "Y")
            re_enabled = _summary(fetch_cart())["GST"]
        self.assertEqual(enabled, 2.0)
        self.assertEqual(disabled["GST"], 0.0)
        self.assertEqual(disabled["order_total_before_credit"], disabled["original_price"])
        self.assertEqual(checkout["gst_amount"], 0.0)
        self.assertEqual(re_enabled, 2.0)

    def test_client_supplied_gst_values_cannot_override_backend(self):
        db = FakeCartDb()
        self._toggle(PRODUCTS[15], "gst_applicable", "N")
        forged = "?gst=999&GST=999&gst_amount=999&gst_percentage=28&total=1&payable_amount=1"
        with cart_env(db):
            add(15, (0, 2))
            cart = body_of(views_commerce.cart_api_test(rf.get("/api/cart" + forged, **BEARER)))
            checkout = body_of(views_commerce.checkout(rf.get("/api/checkout" + forged, **BEARER)))["checkout_data"]["cart_summary"]
        self.assertEqual(_summary(cart)["GST"], 0.0)
        self.assertEqual(_summary(cart)["payable_amount"], 200.0)
        self.assertEqual(checkout["gst_amount"], 0.0)

    def test_gst_is_added_once_on_top_of_the_list_price(self):
        db = FakeCartDb()
        with cart_env(db):
            add(15, (0, 1))
            s = _summary(fetch_cart())
        self.assertEqual(s["items_subtotal"], 100.0)
        self.assertEqual(s["GST"], 1.0)   # 20 x 5% - not 5% (or 18%) of the 100 price
        self.assertEqual(s["order_total_before_credit"], 101.0)

    def test_flutter_summary_keys_remain_present(self):
        db = FakeCartDb()
        with cart_env(db):
            add(15, (0, 1))
            cart = fetch_cart()
            checkout = body_of(views_commerce.checkout(rf.get("/api/checkout", **BEARER)))["checkout_data"]["cart_summary"]
        for key in ("GST", "items_subtotal", "original_price", "order_total_before_credit", "payable_amount",
                    "credit_release", "delivery", "vip_discount", "final_total_price", "total_cart_items"):
            self.assertIn(key, _summary(cart))
        for key in ("gst_amount", "total_with_gst", "total_price", "delivery", "currency", "total_items", "total_quantity"):
            self.assertIn(key, checkout)
        item = next(iter(cart["cart_items"]["discount_not_available"].values()))["items"][0]
        self.assertIn("gst_amount", item)


from legacy_api.cart_discount_testing import module_fixtures
setUpModule, tearDownModule = module_fixtures()  # no saved cart-discount row: promotion unconfigured, no DB access
