"""Regression tests: the customer cart and order placement use the persisted admin Cart Discount Settings.

No database is touched: the settings storage (adminapi.CartDiscountSettings.objects) and the order SQL helpers are
mocked, so no real customer, cart, order or settings record is read or modified.
"""
from contextlib import nullcontext
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.db import OperationalError
from django.test import RequestFactory, SimpleTestCase, override_settings

from adminapi.cart_discount import allocate_discount, load_cart_discount_config
from .cart_discount_testing import patch_cart_discount_settings, settings_row
from .views_commerce import _build_cart_response
from .views_orders import order_post


def line(amount, **extra):
    amount = float(amount)
    base = {"sub_total": amount, "discounted_subtotal": amount, "discount_amount": 0.0, "discount_percent": 0.0, "quantity": 1}
    base.update(extra)
    return base


def cart_for(settings_values, undiscounted, discounted=(), **kwargs):
    """Cart response built against a saved (mocked) settings row; settings_values=None means no row saved."""
    row = None if settings_values is None else settings_row(*settings_values)
    with patch_cart_discount_settings(row):
        return _build_cart_response("sample-user", list(discounted), list(undiscounted), 0, **kwargs)["cart_items"]


ENABLED = (True, "8000.00", "800.00")


class ThresholdAndAmountTests(SimpleTestCase):
    def test_below_threshold_does_not_apply(self):
        cart = cart_for(ENABLED, [line("7999.99")])
        self.assertFalse(cart["mov"]["cart_discount_applied"])
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 0.0)
        self.assertEqual(cart["mov"]["cart_discount_percent"], 0.0)

    def test_exactly_equal_to_threshold_does_not_apply(self):
        cart = cart_for(ENABLED, [line("8000.00")])
        self.assertFalse(cart["mov"]["cart_discount_applied"])
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 0.0)
        self.assertEqual(cart["mov"]["difference"], 0.0)

    def test_just_above_threshold_applies_the_saved_fixed_amount(self):
        cart = cart_for(ENABLED, [line("8000.01")])
        self.assertTrue(cart["mov"]["cart_discount_applied"])
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 800.0)
        self.assertEqual(cart["discount_not_available"]["2"]["items"][0]["discounted_subtotal"], 7200.01)

    def test_fixed_discount_is_a_currency_amount_not_a_percentage(self):
        cart = cart_for(ENABLED, [line("15000")])
        mov, summary = cart["mov"], cart["final_summary"]
        self.assertTrue(mov["enabled"])
        self.assertEqual((mov["min_order_value"], mov["current_order_value"], mov["difference"]), (8000.0, 15000.0, 7000.0))
        self.assertEqual(mov["cart_discount"], 800.0)            # configured fixed amount, compatibility field name
        self.assertEqual(mov["cart_discount_amount"], 800.0)     # amount actually applied
        self.assertEqual(mov["cart_discount_percent"], 0.0)      # fixed amount: never a derived or old 10% figure
        self.assertEqual(summary["cart_discount_amount"], 800.0)
        self.assertEqual(summary["order_total_before_credit"], 14200.0)
        self.assertEqual(summary["payable_amount"], 14200.0)

    def test_disabled_configuration_never_applies(self):
        cart = cart_for((False, "8000.00", "800.00"), [line("50000")])
        self.assertFalse(cart["mov"]["enabled"])
        self.assertFalse(cart["mov"]["cart_discount_applied"])
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 0.0)
        self.assertEqual(cart["final_summary"]["order_total_before_credit"], 50000.0)

    def test_changing_the_saved_threshold_changes_eligibility(self):
        eligible = [cart_for((True, minimum, "800.00"), [line("9000")])["mov"]["cart_discount_applied"]
                    for minimum in ("8000.00", "8999.99", "9000.00", "10000.00")]
        self.assertEqual(eligible, [True, True, False, False])  # strictly greater than the saved minimum

    def test_changing_the_saved_amount_changes_the_discount(self):
        applied = [cart_for((True, "8000.00", amount), [line("9000")])["final_summary"]["cart_discount_amount"]
                   for amount in ("800.00", "1250.50", "300.00")]
        self.assertEqual(applied, [800.0, 1250.5, 300.0])

    def test_discount_never_exceeds_the_eligible_subtotal(self):
        cart = cart_for((True, "100.00", "5000.00"), [line("250")])
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 250.0)
        self.assertEqual(cart["discount_not_available"]["2"]["items"][0]["discounted_subtotal"], 0.0)

    def test_settings_are_read_fresh_on_every_call_not_cached(self):
        first = cart_for((True, "8000.00", "800.00"), [line("9000")])["final_summary"]["cart_discount_amount"]
        second = cart_for((True, "8000.00", "100.00"), [line("9000")])["final_summary"]["cart_discount_amount"]
        self.assertEqual((first, second), (800.0, 100.0))


class NoHardcodedValuesTests(SimpleTestCase):
    def test_old_hardcoded_14000_minimum_and_10_percent_are_not_used(self):
        # Above the old 14000 minimum but below the saved 20000 minimum: the old code would have discounted 10%.
        cart = cart_for((True, "20000.00", "800.00"), [line("15000")])
        self.assertFalse(cart["mov"]["cart_discount_applied"])
        self.assertEqual(cart["mov"]["min_order_value"], 20000.0)
        # Below the old 14000 minimum but above the saved 5000 minimum: applies the saved fixed amount, not 10%.
        cart = cart_for((True, "5000.00", "300.00"), [line("6000")])
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 300.0)

    def test_source_no_longer_contains_the_hardcoded_line_or_values(self):
        for name in ("views_commerce.py", "views_orders.py"):
            source = (Path(__file__).with_name(name)).read_text(encoding="utf-8")
            self.assertNotIn("14000", source, name)
            self.assertNotIn("cart_discount_fixed = 10", source, name)
            self.assertNotIn("True, 14000.0, 10.0", source, name)

    def test_missing_configuration_does_not_activate_a_fallback(self):
        cart = cart_for(None, [line("50000")])
        self.assertFalse(cart["mov"]["enabled"])
        self.assertEqual((cart["mov"]["min_order_value"], cart["mov"]["cart_discount"]), (0.0, 0.0))
        self.assertFalse(cart["mov"]["cart_discount_applied"])
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 0.0)
        self.assertEqual(cart["final_summary"]["order_total_before_credit"], 50000.0)

    def test_unreadable_settings_raise_instead_of_discounting(self):
        with patch_cart_discount_settings(error=OperationalError("connection refused")):
            with self.assertRaises(OperationalError):
                _build_cart_response("sample-user", [], [line("50000")], 0)
            with self.assertRaises(OperationalError):
                load_cart_discount_config()


class EligibleLinesTests(SimpleTestCase):
    def test_vip_customer_gets_no_cart_discount(self):
        cart = cart_for(ENABLED, [line("15000")], vip_applied=True, vip_percentage=20)
        self.assertFalse(cart["mov"]["cart_discount_applied"])
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 0.0)
        self.assertEqual(cart["final_summary"]["vip_discount"], 3000.0)

    def test_threshold_uses_only_the_eligible_subtotal_not_the_whole_cart(self):
        discounted = line(20000, discounted_subtotal=16000.0, discount_amount=4000.0, discount_percent=20.0)
        cart = cart_for(ENABLED, [line("7000")], [discounted])   # whole cart 27000, eligible subtotal only 7000
        self.assertFalse(cart["mov"]["cart_discount_applied"])
        self.assertEqual(cart["mov"]["current_order_value"], 7000.0)
        cart = cart_for(ENABLED, [line("9000")], [discounted])
        self.assertTrue(cart["mov"]["cart_discount_applied"])
        self.assertEqual(cart["discount_available"]["1"]["items"][0]["discounted_subtotal"], 16000.0)  # untouched
        self.assertEqual(cart["final_summary"]["product_discount_amount"], 4000.0)
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 800.0)

    def test_fixed_amount_is_split_over_eligible_lines_and_counted_once(self):
        cart = cart_for(ENABLED, [line("6000"), line("3000")])
        items = cart["discount_not_available"]["2"]["items"]
        shares = [item["discount_amount"] for item in items]
        self.assertEqual(sum(Decimal(str(s)) for s in shares), Decimal("800.00"))
        self.assertEqual(shares, [533.33, 266.67])
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 800.0)
        self.assertEqual(cart["final_summary"]["discount_not_available_total"], 8200.0)
        self.assertEqual(cart["final_summary"]["original_price"], 8200.0)

    def test_allocation_is_exact_to_the_cent(self):
        for amounts, discount in ((["1", "1", "1"], "1.00"), (["0.01", "0.02"], "0.03"), (["7", "5", "3"], "2.50")):
            shares = allocate_discount(amounts, discount)
            self.assertEqual(sum(shares), Decimal(discount))
            self.assertTrue(all(Decimal("0") <= s <= Decimal(a) for s, a in zip(shares, amounts)))


class ResponseContractTests(SimpleTestCase):
    def test_flutter_fields_and_types_are_stable(self):
        cart = cart_for(ENABLED, [line("15000")])
        self.assertEqual(set(cart), {"discount_available", "discount_not_available", "final_summary", "discount", "mov"})
        mov = cart["mov"]
        self.assertEqual(set(mov), {"enabled", "min_order_value", "current_order_value", "difference", "cart_discount",
                                    "cart_discount_applied", "cart_discount_percent", "cart_discount_amount"})
        self.assertIs(type(mov["enabled"]), bool)
        self.assertIs(type(mov["cart_discount_applied"]), bool)
        for key in ("min_order_value", "current_order_value", "difference", "cart_discount",
                    "cart_discount_percent", "cart_discount_amount"):
            self.assertIs(type(mov[key]), float, key)
        self.assertIs(type(cart["final_summary"]["cart_discount_amount"]), float)
        item = cart["discount_not_available"]["2"]["items"][0]
        for key in ("sub_total", "discounted_subtotal", "discount_amount", "discount_percent"):
            self.assertIs(type(item[key]), float, key)
        self.assertEqual(set(cart["discount_not_available"]["2"]), {"items", "total_price", "product_discount", "subtotal"})

    def test_types_are_identical_when_the_promotion_does_not_apply(self):
        mov = cart_for(None, [line("100")])["mov"]
        self.assertEqual(set(mov), {"enabled", "min_order_value", "current_order_value", "difference", "cart_discount",
                                    "cart_discount_applied", "cart_discount_percent", "cart_discount_amount"})
        self.assertIs(type(mov["cart_discount_percent"]), float)


class OrderPlacementAgreementTests(SimpleTestCase):
    USER = {"id": 7, "fullname": "Test User", "phone": "0000000000", "address": "Test Address",
            "email": "test@example.com", "delivery_charges": Decimal("0.00"), "vip_discount": "N",
            "vip_percentage": Decimal("0"), "gst_percentage": Decimal("0")}

    @staticmethod
    def row(product_id, price, **extra):
        base = {"product_id": product_id, "variant_id": 0, "qty": 1, "product_name": f"P{product_id}", "has_disc": 0,
                "discount_percent": 0, "discount_value": 0, "product_discount": 0, "variant_name": "",
                "price": Decimal(str(price)), "stock_qty": 1}
        base.update(extra)
        return base

    def place(self, rows, settings_row_=None, error=None, user=None):
        request = RequestFactory().post("/api/order_post", HTTP_AUTHORIZATION="Bearer test")
        with override_settings(STOKIT_MIN_ORDER_VALUE=Decimal("0.00")), \
             patch("accounts.services.parse_bearer", return_value="test"), \
             patch("accounts.services.authenticate_token", return_value=(None, {"username": "sample-user"})), \
             patch("legacy_api.views_orders.transaction.atomic", side_effect=lambda: nullcontext()), \
             patch("legacy_api.views_orders.fetchone", return_value=user or self.USER), \
             patch("legacy_api.views_orders.fetchall", return_value=rows), \
             patch("legacy_api.views_orders.execute") as execute, \
             patch("legacy_api.views_orders.apply_order_credit") as credit, \
             patch("legacy_api.views_orders._insert_checkout_with_unique_id", return_value=123456) as create_order, \
             patch_cart_discount_settings(settings_row_, error=error):
            response = order_post(request)
        return response, create_order, credit, execute

    def test_cart_total_and_order_total_agree_and_discount_is_applied_once(self):
        rows = [self.row(1, "6000.00"), self.row(2, "3000.00")]
        cart = cart_for(ENABLED, [line("6000"), line("3000")])
        response, create_order, credit, _execute = self.place(rows, settings_row(*ENABLED))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(create_order.call_args[0][1], Decimal("8200.00"))           # stored order subtotal
        self.assertEqual(float(credit.call_args[0][2]), cart["final_summary"]["order_total_before_credit"])
        self.assertEqual(float(credit.call_args[0][2]), 8200.0)
        self.assertIn(b'"total_amount": 8200.0', response.content)
        self.assertIn(b'"discount_amount": 800.0', response.content)

    def test_order_at_or_below_the_saved_threshold_gets_no_discount(self):
        for amount in ("7999.00", "8000.00"):
            response, create_order, credit, _ = self.place([self.row(1, amount)], settings_row(*ENABLED))
            self.assertEqual(create_order.call_args[0][1], Decimal(amount))
            self.assertEqual(float(credit.call_args[0][2]), float(amount))

    def test_order_follows_a_changed_saved_amount(self):
        response, create_order, credit, _ = self.place([self.row(1, "9000.00")], settings_row(True, "8000.00", "100.00"))
        self.assertEqual(create_order.call_args[0][1], Decimal("8900.00"))

    def test_order_ignores_product_discounted_lines_for_eligibility(self):
        discounted = self.row(1, "20000.00", has_disc=1, discount_percent=20)   # line total 16000, not eligible
        rows = [discounted, self.row(2, "7000.00")]                           # eligible subtotal 7000 <= 8000
        response, create_order, credit, _ = self.place(rows, settings_row(*ENABLED))
        self.assertEqual(create_order.call_args[0][1], Decimal("23000.00"))
        rows = [discounted, self.row(2, "9000.00")]
        response, create_order, credit, _ = self.place(rows, settings_row(*ENABLED))
        self.assertEqual(create_order.call_args[0][1], Decimal("24200.00"))  # 16000 + 9000 - 800

    def test_vip_customer_order_gets_no_cart_discount(self):
        vip = {**self.USER, "vip_discount": "Y", "vip_percentage": Decimal("20")}
        response, create_order, credit, _ = self.place([self.row(1, "15000.00")], settings_row(*ENABLED), user=vip)
        self.assertEqual(create_order.call_args[0][1], Decimal("15000.00"))
        self.assertEqual(float(credit.call_args[0][2]), 12000.0)  # VIP 20% only

    def test_order_without_saved_settings_applies_no_discount(self):
        response, create_order, credit, _ = self.place([self.row(1, "50000.00")], None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(create_order.call_args[0][1], Decimal("50000.00"))

    def test_unreadable_settings_fail_safely_without_creating_an_order(self):
        response, create_order, credit, execute = self.place([self.row(1, "50000.00")], error=OperationalError("down"))
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Internal server error", response.content)
        create_order.assert_not_called()
        credit.assert_not_called()
        execute.assert_not_called()


class FixedDiscountDisplayTests(SimpleTestCase):
    """Reported case: 27 x 305 = 8235, fixed 800 discount; Flutter must not show a false ~9% under the product."""

    def cart(self, settings_values=ENABLED, **kwargs):
        item = line("8235", price=305.0, quantity=27, gst_amount=2700.0)
        row = settings_row(*settings_values)
        with patch_cart_discount_settings(row):
            return _build_cart_response("sample-user", [], [item], 50, **kwargs)["cart_items"]

    def test_fixed_discount_creates_no_false_percentage(self):
        cart = self.cart()
        item = cart["discount_not_available"]["2"]["items"][0]
        self.assertEqual(item["discount_percent"], 0.0)
        self.assertEqual(cart["mov"]["cart_discount_percent"], 0.0)
        self.assertEqual(cart["discount_not_available"]["2"]["product_discount"], 0.0)
        self.assertIs(type(item["discount_percent"]), float)
        self.assertIs(type(cart["mov"]["cart_discount_percent"]), float)

    def test_amounts_and_totals_are_unchanged(self):
        cart = self.cart()
        item, summary, mov = cart["discount_not_available"]["2"]["items"][0], cart["final_summary"], cart["mov"]
        self.assertEqual((item["sub_total"], item["discount_amount"], item["discounted_subtotal"]), (8235.0, 800.0, 7435.0))
        self.assertEqual((mov["cart_discount"], mov["cart_discount_amount"], mov["cart_discount_applied"]), (800.0, 800.0, True))
        self.assertEqual((mov["min_order_value"], mov["current_order_value"], mov["difference"]), (8000.0, 8235.0, 235.0))
        self.assertEqual(summary["cart_discount_amount"], 800.0)       # applied once, not twice
        self.assertEqual(summary["discount_not_available_total"], 7435.0)
        self.assertEqual(summary["original_price"], 7435.0)
        self.assertEqual((summary["GST"], summary["delivery"]), (2700.0, 50.0))
        self.assertEqual(summary["payable_amount"], 10185.0)
        self.assertEqual(summary["final_total_price"], 10185.0)

    def test_genuine_product_discount_percentage_is_preserved(self):
        discounted = line(20000, discounted_subtotal=16000.0, discount_amount=4000.0, discount_percent=20.0)
        with patch_cart_discount_settings(settings_row(*ENABLED)):
            cart = _build_cart_response("sample-user", [discounted], [line("9000")], 0)["cart_items"]
        self.assertEqual(cart["discount_available"]["1"]["items"][0]["discount_percent"], 20.0)
        self.assertEqual(cart["discount_available"]["1"]["product_discount"], 20.0)
        self.assertEqual(cart["discount_not_available"]["2"]["items"][0]["discount_percent"], 0.0)
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 800.0)

class ProductTotalDisplayTests(SimpleTestCase):
    """Flutter's item row shows `sub_total`; the group footer "Total :" shows the group `subtotal`.
    The fixed cart discount must reduce neither: it reaches the customer only through the summary/payable amount."""

    def cart(self, **kwargs):
        item = line("8235", price=305.0, quantity=27, gst_amount=2700.0)
        with patch_cart_discount_settings(settings_row(*ENABLED)):
            return _build_cart_response("sample-user", [], [item], 50, **kwargs)["cart_items"]

    def test_product_total_fields_flutter_displays_are_the_original_8235(self):
        cart = self.cart()
        group = cart["discount_not_available"]["2"]
        self.assertEqual(group["items"][0]["sub_total"], 8235.0)      # item row Total (CartItemModel.totalPrice)
        self.assertEqual(group["subtotal"], 8235.0)                    # group footer Total (CartProductGroup.subtotal)
        self.assertEqual(group["total_price"], 8235.0)
        self.assertEqual(group["product_discount"], 0.0)               # no false percentage / no struck-through total
        self.assertEqual(group["items"][0]["discount_percent"], 0.0)
        self.assertEqual(cart["mov"]["current_order_value"], 8235.0)

    def test_fixed_discount_is_still_applied_exactly_once_to_the_payment(self):
        cart = self.cart()
        summary, mov = cart["final_summary"], cart["mov"]
        self.assertEqual(summary["cart_discount_amount"], 800.0)
        self.assertEqual(mov["cart_discount_amount"], 800.0)
        self.assertEqual(summary["items_subtotal"], 8235.0)
        self.assertEqual(summary["discount_not_available_total"], 7435.0)   # 8235 - 800 once
        self.assertEqual(summary["original_price"], 7435.0)
        self.assertEqual((summary["GST"], summary["delivery"]), (2700.0, 50.0))
        self.assertEqual(summary["order_total_before_credit"], 10185.0)
        self.assertEqual(summary["payable_amount"], 10185.0)
        self.assertEqual(summary["final_total_price"], 10185.0)
        self.assertEqual(cart["discount_not_available"]["2"]["items"][0]["discount_amount"], 800.0)

    def test_group_subtotal_is_not_reduced_when_the_promotion_does_not_apply(self):
        with patch_cart_discount_settings(settings_row(False, "8000.00", "800.00")):
            cart = _build_cart_response("u", [], [line("8235")], 0)["cart_items"]
        group = cart["discount_not_available"]["2"]
        self.assertEqual((group["subtotal"], group["total_price"]), (8235.0, 8235.0))
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 0.0)

    def test_genuine_product_discount_group_still_shows_its_discounted_subtotal(self):
        discounted = line(20000, discounted_subtotal=16000.0, discount_amount=4000.0, discount_percent=20.0)
        with patch_cart_discount_settings(settings_row(*ENABLED)):
            cart = _build_cart_response("u", [discounted], [line("9000")], 0)["cart_items"]
        group = cart["discount_available"]["1"]
        self.assertEqual((group["total_price"], group["subtotal"], group["product_discount"]), (20000.0, 16000.0, 20.0))
        self.assertEqual(group["items"][0]["discount_percent"], 20.0)
        self.assertEqual(cart["discount_not_available"]["2"]["subtotal"], 9000.0)
        self.assertEqual(cart["final_summary"]["cart_discount_amount"], 800.0)

    def test_response_field_names_and_types_are_unchanged(self):
        group = self.cart()["discount_not_available"]["2"]
        self.assertEqual(set(group), {"items", "total_price", "product_discount", "subtotal"})
        for key in ("total_price", "product_discount", "subtotal"):
            self.assertIs(type(group[key]), float, key)