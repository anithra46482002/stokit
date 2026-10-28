"""Customer GST Number: the ONLY GST-specific rule is 'exactly 15 characters' when a value is entered.

No checksum, GSTIN format, state code, PAN structure, character class or GST-registration dependency. Database-free:
the validator is exercised directly and through the real create/update views with the data layer mocked.
"""
from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from adminapi import crud

LENGTH_ERROR = 'GST Number must contain exactly 15 characters.'
FIFTEEN = ['123456789012345', 'ABCDEFGHIJKLMNO', '22ABCDE1234F1Z5', 'abcdefghijklmno', '!!!!!!!!!!!!!!!',
           'AB CD EF GH IJK', '00AAAAA0000A0Z0', '99ZZZZZ9999Z9Z9', '000000000000000', '\u00e9' * 15]
WRONG = ['1', '12345678901234', '1234567890123456', '22ABCDE1234F1Z', '22ABCDE1234F1Z55', 'A' * 40]


def _instance(gst='N', number=None):
    return SimpleNamespace(pk=7, gst=gst, gst_number=number)


def _validate(value, gst='N', instance=None, **extra):
    data = {'gst_number': value, **({'gst': gst} if gst is not None else {}), **extra}
    return crud._clean_customer(data, instance=instance)


class GstNumberValidatorTests(SimpleTestCase):
    def test_empty_value_is_accepted_and_stored_as_null(self):
        for gst in ('N', 'Y', None):
            for empty in ('', None):
                clean, errors = _validate(empty, gst=gst)
                self.assertEqual(errors, {}, (gst, empty))
                self.assertIsNone(clean['gst_number'])

    def test_whitespace_only_is_not_treated_as_empty(self):
        clean, errors = _validate('   ')
        self.assertEqual(errors, {'gst_number': LENGTH_ERROR})

    def test_any_15_character_string_is_accepted_whatever_its_content(self):
        for value in FIFTEEN:
            self.assertEqual(len(value), 15, value)
            for gst in ('N', 'Y'):
                clean, errors = _validate(value, gst=gst)
                self.assertEqual(errors, {}, (value, gst))
                self.assertEqual(clean['gst_number'], value)

    def test_the_documented_examples_pass(self):
        for value in ('123456789012345', 'ABCDEFGHIJKLMNO', '22ABCDE1234F1Z5'):
            self.assertEqual(_validate(value)[1], {})

    def test_14_and_16_characters_and_other_lengths_fail_with_only_the_length_message(self):
        for value in WRONG:
            for gst in ('N', 'Y'):
                clean, errors = _validate(value, gst=gst)
                self.assertEqual(errors, {'gst_number': LENGTH_ERROR}, (value, gst))
                self.assertNotIn('gst_number', clean)

    def test_registration_yes_and_no_give_identical_gst_number_validation(self):
        for value in FIFTEEN + WRONG + ['']:
            yes_clean, yes_errors = _validate(value, gst='Y')
            no_clean, no_errors = _validate(value, gst='N')
            self.assertEqual(yes_errors, no_errors, value)
            self.assertEqual(yes_clean.get('gst_number'), no_clean.get('gst_number'), value)

    def test_registration_yes_with_an_empty_number_is_not_rejected(self):
        self.assertEqual(_validate('', gst='Y')[1], {})  # empty stays optional; no registration dependency

    def test_whitespace_is_counted_exactly_as_entered(self):
        clean, errors = _validate(' 12345678901234')
        self.assertEqual(errors, {})
        self.assertEqual(clean['gst_number'], ' 12345678901234')
        self.assertEqual(_validate('  123456789012345  ')[1], {'gst_number': LENGTH_ERROR})
    def test_non_string_json_values_are_measured_by_their_text(self):
        self.assertEqual(_validate(123456789012345)[1], {})
        self.assertEqual(_validate(0)[1], {'gst_number': LENGTH_ERROR})  # a bare 0 is one character, not "empty"
        self.assertEqual(_validate(False)[1], {'gst_number': LENGTH_ERROR})

    def test_create_and_update_apply_identical_rules(self):
        existing = [None, _instance('N'), _instance('Y', '123456789012345'), _instance('Y', None)]
        for value in FIFTEEN + WRONG + ['']:
            for gst in ('N', 'Y'):
                created = _validate(value, gst=gst)
                for instance in existing:
                    self.assertEqual(_validate(value, gst=gst, instance=instance), created, (value, gst))

    def test_changing_only_the_registration_never_fails_because_of_the_stored_number(self):
        for stored in (None, '', 'SHORT', '1' * 15):
            for gst in ('N', 'Y'):
                clean, errors = crud._clean_customer({'gst': gst}, instance=_instance('N', stored))
                self.assertEqual(errors, {}, (stored, gst))
                self.assertEqual(clean['gst'], gst)

    def test_no_gst_number_validator_is_left_in_the_source(self):
        import inspect
        source = inspect.getsource(crud._clean_customer)
        for forbidden in ('checksum', 'GSTIN', 'registered is Yes', 'state code', 'PAN'):
            self.assertNotIn(forbidden, source)
        self.assertEqual(crud.GST_NUMBER_LENGTH, 15)


class UnrelatedCustomerValidationTests(SimpleTestCase):
    """The GST change must not loosen anything else."""

    def test_other_fields_are_still_validated_alongside_a_valid_gst_number(self):
        for key, value in (('status', 'DORMANT'), ('gst', 'Q'), ('gst_type', 'WEIRD'), ('gst_percentage', '150'),
                           ('gst_percentage', 'abc'), ('vip_percentage', '101'), ('color_code', 'red'),
                           ('delivery_charges', '-1'), ('full_name', '')):
            clean, errors = crud._clean_customer({'gst_number': '123456789012345', key: value})
            self.assertIn(key, errors, (key, value))
            self.assertNotIn('gst_number', errors)

    def test_a_bad_gst_number_does_not_hide_other_errors(self):
        clean, errors = crud._clean_customer({'gst_number': '123', 'status': 'DORMANT'})
        self.assertEqual(set(errors), {'gst_number', 'status'})

    def test_text_length_limits_and_phone_rules_still_apply(self):
        self.assertIn('full_name', crud._clean_customer({'full_name': 'x' * 256})[1])
        self.assertIn('phone', crud._clean_customer({'phone': '12345'})[1])


def _row(**extra):
    row = SimpleNamespace(
        id=7, username='shop1', fullname='Shop One', email='shop@example.com', phone=None, shop_name=None,
        status='ACTIVE', city=None, address=None, gst='N', gst_type=None, gst_number=None, gst_percentage=None,
        delivery_charges=Decimal('0'), vip_discount='N', vip_percentage=Decimal('0'), store_maped='N',
        category_id=None, color_code=None, warehouse_id=None, profile_picture=None, created_at=datetime(2026, 1, 1),
        updated_at=None, save=MagicMock())
    for key, value in extra.items():
        setattr(row, key, value)
    return row


def _manager(existing=None, created=None):
    manager = MagicMock()
    manager.filter.return_value.exists.return_value = False
    manager.filter.return_value.exclude.return_value.exists.return_value = False
    manager.filter.return_value.first.return_value = existing
    manager.create.return_value = created
    return manager


def _call(method, payload):
    request = getattr(APIRequestFactory(), method)('/admin-api/customers', payload, format='json')
    force_authenticate(request, user=SimpleNamespace(is_authenticated=True, role='ADMIN', pk=1, principal_type='ADMIN'))
    return crud.CustomerCRUDView.as_view()(request)


class CustomerApiGstNumberTests(SimpleTestCase):
    NEW = {'username': 'shop1', 'password': 'a-long-password', 'full_name': 'Shop One', 'email': 'shop@example.com'}

    def _create(self, **fields):
        created = _row(gst_number=fields.get('gst_number') or None, gst=fields.get('gst', 'N'))
        with patch.object(crud.LegacyUser, 'objects', _manager(created=created)), \
                patch.object(crud.Warehouse.objects, 'values_list', return_value=[]), \
                patch.object(crud.transaction, 'atomic', return_value=nullcontext()):
            return _call('post', {**self.NEW, **fields})

    def _update(self, **fields):
        row = _row()
        with patch.object(crud.LegacyUser, 'objects', _manager(existing=row)), \
                patch.object(crud.Warehouse.objects, 'values_list', return_value=[]):
            response = _call('patch', {'id': 7, **fields})
        return response, row

    def test_create_and_update_accept_15_characters_for_registration_yes_and_no(self):
        for value in ('123456789012345', 'ABCDEFGHIJKLMNO', '22ABCDE1234F1Z5', '!@#$%^&*()_+-=['):
            for gst in ('Y', 'N'):
                self.assertEqual(self._create(gst_number=value, gst=gst).status_code, 201, (value, gst))
                response, row = self._update(gst_number=value, gst=gst)
                self.assertEqual(response.status_code, 200, (value, gst))
                self.assertEqual(row.gst_number, value)
                row.save.assert_called_once()

    def test_create_and_update_reject_14_and_16_characters_identically(self):
        for value in ('12345678901234', '1234567890123456'):
            created = self._create(gst_number=value)
            updated, row = self._update(gst_number=value)
            for response in (created, updated):
                self.assertEqual(response.status_code, 400, value)
                self.assertEqual(response.data['errors'], {'gst_number': LENGTH_ERROR})
                self.assertEqual(response.data['detail'], LENGTH_ERROR)
            row.save.assert_not_called()

    def test_create_and_update_accept_an_empty_number(self):
        self.assertEqual(self._create(gst_number='').status_code, 201)
        response, row = self._update(gst_number='')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(row.gst_number)

    def test_unrelated_validation_still_applies_on_both_endpoints(self):
        self.assertEqual(self._create(gst_number='123456789012345', email='not-an-email').status_code, 400)
        self.assertEqual(self._update(gst_number='123456789012345', status='DORMANT')[0].status_code, 400)
        no_password = {k: v for k, v in self.NEW.items() if k != 'password'}
        with patch.object(crud.LegacyUser, 'objects', _manager()):
            self.assertEqual(_call('post', {**no_password, 'gst_number': '123456789012345'}).status_code, 400)

    def test_unauthenticated_requests_are_still_rejected(self):
        request = APIRequestFactory().post('/admin-api/customers', {**self.NEW, 'gst_number': '123456789012345'}, format='json')
        self.assertIn(crud.CustomerCRUDView.as_view()(request).status_code, (401, 403))
