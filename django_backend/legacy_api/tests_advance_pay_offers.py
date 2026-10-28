import json
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from . import views_finance


class AdvancePayOfferVisibilityTests(SimpleTestCase):
    def test_active_filter_normalizes_legacy_database_status_case(self):
        request = RequestFactory().post(
            '/api/advancePay-api', data=json.dumps({'status': 'Active'}),
            content_type='application/json', HTTP_AUTHORIZATION='Bearer test-token',
        )
        with patch('accounts.services.parse_bearer', return_value='test-token'), \
             patch('accounts.services.authenticate_token', return_value=(None, {'username': 'sample'})), \
             patch('legacy_api.views_finance.fetchall', return_value=[]) as fetchall, \
             patch('legacy_api.views_finance.fetchone', return_value={'total': 0}):
            response = views_finance.advance_pay(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)['status'])
        sql = fetchall.call_args.args[0]
        self.assertIn('UPPER(TRIM(o.status))=%s', sql)
        self.assertEqual(fetchall.call_args.args[1], ['ACTIVE', 100, 0])

    def test_all_statuses_does_not_filter_offer_status(self):
        request = RequestFactory().post(
            '/api/advancePay-api', data=json.dumps({'status': 'ALL'}),
            content_type='application/json', HTTP_AUTHORIZATION='Bearer test-token',
        )
        with patch('accounts.services.parse_bearer', return_value='test-token'), \
             patch('accounts.services.authenticate_token', return_value=(None, {'username': 'sample'})), \
             patch('legacy_api.views_finance.fetchall', return_value=[]) as fetchall, \
             patch('legacy_api.views_finance.fetchone', return_value={'total': 0}):
            response = views_finance.advance_pay(request)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('UPPER(TRIM(o.status))=%s', fetchall.call_args.args[0])
        self.assertEqual(fetchall.call_args.args[1], [100, 0])
