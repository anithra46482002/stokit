from django.test import SimpleTestCase

from .discount_rules import cart_discount_amount, customer_has_vip, product_has_discount


class DiscountRuleTests(SimpleTestCase):
    def test_any_existing_product_discount_marks_line_ineligible(self):
        for kwargs in (
            {"has_disc": 1},
            {"has_disc": "Y"},
            {"discount_percent": "5"},
            {"discount_value": "1.00"},
            {"product_discount": "10"},
        ):
            with self.subTest(kwargs=kwargs):
                self.assertTrue(product_has_discount(**kwargs))

    def test_zero_discount_fields_without_flag_are_eligible(self):
        self.assertFalse(product_has_discount(has_disc=0, discount_percent=0, discount_value=0, product_discount=0))

    def test_vip_is_active_only_with_flag_and_positive_percentage(self):
        self.assertTrue(customer_has_vip("Y", "10"))
        self.assertFalse(customer_has_vip("N", "10"))
        self.assertFalse(customer_has_vip("Y", "0"))

    def test_vip_blocks_cart_discount_amount(self):
        self.assertEqual(str(cart_discount_amount("100", "10", vip_applied=True)), "0.00")
        self.assertEqual(str(cart_discount_amount("100", "10", vip_applied=False)), "10.00")
