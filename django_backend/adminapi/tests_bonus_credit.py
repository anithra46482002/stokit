from decimal import Decimal

from django.test import SimpleTestCase

from adminapi.bonus_credit import _money, _monthly_bonus


class BonusCreditAdapterTests(SimpleTestCase):
    """The credit rules themselves are tested in tests_monthly_credit.py; this covers the adapter helpers."""

    def test_monthly_amount_uses_decimal_cents(self):
        self.assertEqual(_money(Decimal('43200') / Decimal('12')), Decimal('3600.00'))

    def test_monthly_bonus_depends_on_each_customers_selected_offer(self):
        # Offer A: 30,000 payment at 10% gives 3,000/month.
        self.assertEqual(_monthly_bonus(Decimal('30000'), Decimal('10')), Decimal('3000.00'))
        # Offer B: 50,000 payment at 12% gives 6,000/month.
        self.assertEqual(_monthly_bonus(Decimal('50000'), Decimal('12')), Decimal('6000.00'))
        # Same payment with a different bonus percentage must change the release amount.
        self.assertEqual(_monthly_bonus(Decimal('30000'), Decimal('5')), Decimal('1500.00'))