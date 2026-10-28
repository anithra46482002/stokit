"""Admin Credit Allocation table (admin-api/advance-allocations): Used / Remaining Credit come from the ledger.

Scope of the two columns is LIFETIME (the PHP-compatible meaning they have always had): used = every valid CREDIT_USED
row, remaining = total potential credit - used (+ net manual corrections). The stored columns are only a cache and are
reported separately. Database-free: the data layer is mocked.
"""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from adminapi import advance_allocations as aa

D = Decimal


def allocation(**extra):
    base = dict(id=4, offer_id=2, user_id=2, payment_amount=D('40000.00'), bonus_percentage=D('12.00'), duration_months=12,
                total_credit=D('57600.00'), used_credit=D('0.00'), remaining_credit=D('57600.00'),
                start_date=date(2026, 10, 23), end_date=date(2027, 10, 23), payment_date=date(2026, 10, 23),
                payment_reference=None, notes=None, status='ACTIVE', created_at=datetime(2026, 10, 23))
    base.update(extra)
    return SimpleNamespace(**base)


def ledger(*rows):
    """rows: (transaction_type, reference_type, amount) -> what the grouped query returns."""
    grouped = {}
    for kind, ref, amount in rows:
        grouped[(kind, ref)] = grouped.get((kind, ref), D('0')) + D(str(amount))
    return [{'allocation_id': 4, 'transaction_type': k, 'reference_type': r, 'total': t} for (k, r), t in grouped.items()]


def balances(alloc, rows):
    with patch.object(aa.AdvancePayTransaction, 'objects') as tx:
        tx.filter.return_value.values.return_value.annotate.return_value = rows
        return aa.ledger_balances([alloc])[alloc.id]


class LedgerBalanceTests(SimpleTestCase):
    def test_no_purchases_shows_zero_used_and_the_full_total_remaining(self):
        b = balances(allocation(), [])
        self.assertEqual((b['used_credit'], b['remaining_credit'], b['total_credit']), (D('0.00'), D('57600.00'), D('57600.00')))
        self.assertTrue(b['ledger_matches_stored'])

    def test_a_3000_order_shows_3000_used_and_54600_remaining_lifetime(self):
        b = balances(allocation(used_credit=D('3000.00'), remaining_credit=D('54600.00')), ledger(('CREDIT_USED', 'ORDER_BONUS', '3000.00')))
        self.assertEqual((b['used_credit'], b['remaining_credit']), (D('3000.00'), D('54600.00')))
        self.assertTrue(b['ledger_matches_stored'])

    def test_the_table_shows_the_ledger_even_when_the_stored_columns_are_stale(self):
        """The reported bug: ledger has the purchase, the legacy columns still say 0 / 57,600."""
        b = balances(allocation(), ledger(('CREDIT_USED', 'ORDER_BONUS', '3000.00')))
        self.assertEqual((b['used_credit'], b['remaining_credit']), (D('3000.00'), D('54600.00')))
        self.assertEqual((b['stored_used_credit'], b['stored_remaining_credit']), (D('0.00'), D('57600.00')))
        self.assertFalse(b['ledger_matches_stored'])

    def test_three_purchases_in_one_month_use_exactly_what_was_applied(self):
        # 2,000 + 2,000 + 800 applied (the third order was 1,500 but only 800 was left); zero-credit rows add nothing.
        rows = ledger(('CREDIT_USED', 'ORDER_BONUS', '2000.00'), ('CREDIT_USED', 'ORDER_BONUS', '2000.00'),
                      ('CREDIT_USED', 'ORDER_BONUS', '800.00'), ('CREDIT_USED', 'ORDER_BONUS', '0.00'))
        b = balances(allocation(), rows)
        self.assertEqual((b['used_credit'], b['remaining_credit']), (D('4800.00'), D('52800.00')))

    def test_manual_corrections_are_not_spending_but_do_adjust_the_remaining_balance(self):
        rows = ledger(('CREDIT_USED', 'ORDER_BONUS', '1000.00'), ('CREDIT_USED', 'MANUAL_ADJUSTMENT', '500.00'),
                      ('CREDIT_ADDED', 'MANUAL_ADJUSTMENT', '200.00'))
        b = balances(allocation(), rows)
        self.assertEqual(b['used_credit'], D('1000.00'))
        self.assertEqual(b['remaining_credit'], D('57600.00') - D('1000.00') - D('500.00') + D('200.00'))

    def test_remaining_never_goes_negative(self):
        b = balances(allocation(), ledger(('CREDIT_USED', 'ORDER_BONUS', '99999.00')))
        self.assertEqual(b['remaining_credit'], D('0.00'))

    def test_invalid_offer_terms_fall_back_to_stored_values_with_a_warning(self):
        b = balances(allocation(bonus_percentage=D('-5'), used_credit=D('10.00'), remaining_credit=D('90.00')), [])
        self.assertEqual((b['used_credit'], b['remaining_credit']), (D('10.00'), D('90.00')))
        self.assertIn('invalid', b['credit_warning'])

    def test_one_grouped_query_per_page_not_one_per_row(self):
        with patch.object(aa.AdvancePayTransaction, 'objects') as tx:
            tx.filter.return_value.values.return_value.annotate.return_value = []
            aa.ledger_balances([allocation(id=1), allocation(id=2), allocation(id=3)])
        tx.filter.assert_called_once()


def _get():
    request = APIRequestFactory().get('/admin-api/advance-allocations')
    force_authenticate(request, user=SimpleNamespace(is_authenticated=True, role='ADMIN', pk=1, principal_type='ADMIN'))
    return aa.AdvanceAllocationAdminView.as_view()(request)


class AdminTableEndpointTests(SimpleTestCase):
    def _response(self, alloc, rows):
        qs = MagicMock()
        qs.__getitem__.return_value = [alloc]
        qs.count.return_value = 1
        user = SimpleNamespace(id=2, username='anithra@1234', fullname='anithra m a')
        offer = SimpleNamespace(id=2, offer_name='special')
        with patch.object(aa.AdvancePayAllocation.objects, 'order_by', return_value=qs), \
                patch.object(aa.LegacyUser.objects, 'filter', return_value=[user]), \
                patch.object(aa.AdvancePayOffer.objects, 'filter', return_value=[offer]), \
                patch.object(aa.AdvancePayTransaction, 'objects') as tx:
            tx.filter.return_value.values.return_value.annotate.return_value = rows
            return _get()

    def test_the_screenshot_customer_after_a_3000_purchase(self):
        response = self._response(allocation(), ledger(('CREDIT_USED', 'ORDER_BONUS', '3000.00')))
        self.assertEqual(response.status_code, 200)
        row = response.data['results'][0]
        self.assertEqual((row['full_name'], row['offer_id'], row['offer_name']), ('anithra m a', 2, 'special'))
        self.assertEqual((row['payment_amount'], row['bonus_percentage'], row['monthly_bonus'], row['duration_months']),
                         ('40000.00', '12.00', '4800.00', 12))
        self.assertEqual((row['total_credit'], row['used_credit'], row['remaining_credit']), ('57600.00', '3000.00', '54600.00'))
        self.assertEqual(row['credit_scope'], 'lifetime')
        self.assertFalse(row['ledger_matches_stored'])

    def test_the_response_keeps_every_field_existing_clients_read(self):
        row = self._response(allocation(), []).data['results'][0]
        for key in ('id', 'user_id', 'username', 'full_name', 'offer_id', 'offer_name', 'payment_amount', 'bonus_percentage',
                    'monthly_bonus', 'duration_months', 'total_credit', 'used_credit', 'remaining_credit', 'start_date',
                    'end_date', 'payment_date', 'payment_reference', 'notes', 'status'):
            self.assertIn(key, row)

    def test_viewing_the_table_never_writes_anything(self):
        alloc = allocation()
        alloc.save = MagicMock()
        self._response(alloc, ledger(('CREDIT_USED', 'ORDER_BONUS', '3000.00')))
        alloc.save.assert_not_called()


class NewAllocationStartsWithTheFullRemainingBalanceTests(SimpleTestCase):
    def test_post_creates_the_allocation_with_remaining_equal_to_total_credit(self):
        offer = SimpleNamespace(id=2, payment_amount=D('40000.00'), bonus_percentage=D('12.00'), duration_months=12, status='ACTIVE')
        created = allocation()
        request = APIRequestFactory().post('/admin-api/advance-allocations', {'offer_id': 2, 'user_id': 2}, format='json')
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True, role='ADMIN', pk=1, principal_type='ADMIN'))
        offer_qs = MagicMock()
        offer_qs.select_for_update.return_value.filter.return_value.first.return_value = offer
        with patch.object(aa.AdvancePayOffer, 'objects', offer_qs), \
                patch.object(aa.LegacyUser.objects, 'filter') as users, \
                patch.object(aa.AdvancePayAllocation.objects, 'create', return_value=created) as create, \
                patch.object(aa.transaction, 'atomic', return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock(return_value=False))):
            users.return_value.first.return_value = SimpleNamespace(id=2)
            response = aa.AdvanceAllocationAdminView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        kwargs = create.call_args.kwargs
        self.assertEqual((kwargs['total_credit'], kwargs['remaining_credit'], kwargs['used_credit']), (D('57600.00'), D('57600.00'), 0))
