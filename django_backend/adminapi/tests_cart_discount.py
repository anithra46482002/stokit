from decimal import Decimal
from django.test import SimpleTestCase
from .cart_discount import calculate_cart_discount, money

class CartDiscountCalculationTests(SimpleTestCase):
    def test_disabled_discount(self):
        result = calculate_cart_discount([{"amount": "100.00", "product_discounted": False}], False, "50", "10")
        self.assertEqual(result["applied_discount"], Decimal("0.00"))
    def test_below_and_equal_threshold_do_not_qualify(self):
        for subtotal in ("49.99", "50.00"):
            result = calculate_cart_discount([{"amount": subtotal}], True, "50", "10")
            self.assertFalse(result["eligible"])
            self.assertEqual(result["applied_discount"], Decimal("0.00"))
    def test_greater_than_threshold_applies_fixed_amount(self):
        result = calculate_cart_discount([{"amount": "50.01"}], True, "50", "10")
        self.assertTrue(result["eligible"])
        self.assertEqual(result["applied_discount"], Decimal("10.00"))
    def test_product_discounted_lines_are_excluded(self):
        result = calculate_cart_discount([{"amount": "500", "product_discounted": True}, {"amount": "70", "product_discounted": False}], True, "60", "12")
        self.assertEqual(result["eligible_subtotal"], Decimal("70.00"))
        self.assertEqual(result["applied_discount"], Decimal("12.00"))
    def test_discount_is_capped_at_eligible_subtotal(self):
        result = calculate_cart_discount([{"amount": "5.00"}], True, "1.00", "20.00")
        self.assertEqual(result["applied_discount"], Decimal("5.00"))
    def test_money_rounds_half_up_and_rejects_invalid(self):
        self.assertEqual(money("1.235"), Decimal("1.24"))
        for invalid in ("-1", "NaN", "Infinity", "bad"):
            with self.assertRaises(ValueError): money(invalid)


    def test_discount_flag_without_percentage_still_excludes_product(self):
        result = calculate_cart_discount([
            {"amount": "500", "has_disc": 1, "discount_percent": 0, "discount_value": 0},
            {"amount": "70"},
        ], True, "60", "12")
        self.assertEqual(result["eligible_subtotal"], Decimal("70.00"))
        self.assertEqual(result["applied_discount"], Decimal("12.00"))

    def test_any_product_discount_field_excludes_line(self):
        for line in (
            {"amount": "100", "discount_percent": "5"},
            {"amount": "100", "discount_value": "2"},
            {"amount": "100", "product_discount": "10"},
            {"amount": "100", "line_discount": "1"},
            {"amount": "100", "product_discounted": True},
        ):
            with self.subTest(line=line):
                result = calculate_cart_discount([line, {"amount": "60"}], True, "50", "10")
                self.assertEqual(result["eligible_subtotal"], Decimal("60.00"))
                self.assertEqual(result["applied_discount"], Decimal("10.00"))

    def test_active_vip_disables_cart_discount_for_entire_cart(self):
        result = calculate_cart_discount([{"amount": "500"}], True, "50", "10", vip_applied=True)
        self.assertEqual(result["eligible_subtotal"], Decimal("500.00"))
        self.assertFalse(result["eligible"])
        self.assertEqual(result["applied_discount"], Decimal("0.00"))

    def test_mixed_cart_discount_is_capped_to_only_eligible_lines(self):
        result = calculate_cart_discount([
            {"amount": "500", "product_discounted": True},
            {"amount": "70"},
        ], True, "60", "100")
        self.assertEqual(result["eligible_subtotal"], Decimal("70.00"))
        self.assertEqual(result["applied_discount"], Decimal("70.00"))


class LoadCartDiscountConfigTests(SimpleTestCase):
    """The customer cart/checkout read the same persisted settings the admin page saves."""

    def _patched(self, row=None, error=None):
        from unittest import mock
        from . import cart_discount
        manager = mock.Mock()
        if error is not None:
            manager.filter.side_effect = error
        else:
            manager.filter.return_value.first.return_value = row
        return mock.patch.object(cart_discount.CartDiscountSettings, "objects", manager)

    def test_maps_the_saved_row_to_decimals(self):
        from types import SimpleNamespace
        from .cart_discount import load_cart_discount_config
        row = SimpleNamespace(enabled=True, minimum_subtotal=Decimal("8000.00"), fixed_discount_amount=Decimal("800.00"))
        with self._patched(row):
            config = load_cart_discount_config()
        self.assertEqual(config, {"enabled": True, "minimum_subtotal": Decimal("8000.00"),
                                  "fixed_discount_amount": Decimal("800.00"), "configured": True})

    def test_missing_row_means_not_configured_never_a_hardcoded_default(self):
        from .cart_discount import load_cart_discount_config
        with self._patched(None):
            config = load_cart_discount_config()
        self.assertEqual(config, {"enabled": False, "minimum_subtotal": Decimal("0.00"),
                                  "fixed_discount_amount": Decimal("0.00"), "configured": False})

    def test_every_call_reads_storage_again(self):
        from types import SimpleNamespace
        from unittest import mock
        from . import cart_discount
        manager = mock.Mock()
        manager.filter.return_value.first.side_effect = [
            SimpleNamespace(enabled=True, minimum_subtotal="8000", fixed_discount_amount="800"),
            SimpleNamespace(enabled=True, minimum_subtotal="9000", fixed_discount_amount="900")]
        with mock.patch.object(cart_discount.CartDiscountSettings, "objects", manager):
            first = cart_discount.load_cart_discount_config()
            second = cart_discount.load_cart_discount_config()
        self.assertEqual((first["minimum_subtotal"], second["minimum_subtotal"]), (Decimal("8000.00"), Decimal("9000.00")))
        self.assertEqual(manager.filter.call_count, 2)

    def test_storage_errors_are_logged_and_re_raised_not_swallowed(self):
        from django.db import OperationalError
        from .cart_discount import load_cart_discount_config
        with self._patched(error=OperationalError("connection refused")):
            with self.assertLogs("adminapi.db", level="ERROR"):
                with self.assertRaises(OperationalError):
                    load_cart_discount_config()

    def test_line_discounts_add_up_to_the_applied_discount(self):
        result = calculate_cart_discount([{"amount": "6000"}, {"amount": "3000"}, {"amount": "400", "product_discounted": True}],
                                         True, "8000", "800")
        self.assertEqual(result["line_discounts"], [Decimal("533.33"), Decimal("266.67"), Decimal("0.00")])
        self.assertEqual(sum(result["line_discounts"]), result["applied_discount"])