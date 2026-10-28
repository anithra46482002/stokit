"""Database-free regression tests for product relationship and variant field validation."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from adminapi import crud


def _user(role="ADMIN"):
    return SimpleNamespace(is_authenticated=True, role=role, pk=1, principal_type="ADMIN")


class ProductSubcategoryValidationTests(SimpleTestCase):
    def _patch(self, payload):
        request = APIRequestFactory().patch("/admin-api/products", payload, format="json")
        force_authenticate(request, user=_user())
        return crud.ProductCRUDView.as_view()(request)

    def test_category_change_cannot_leave_product_with_subcategory_from_another_category(self):
        row = SimpleNamespace(
            product_id=10, category_id=1, subcategory_id=5, product_name="Tea",
            code="T1", product_price=Decimal("10"), mrp=Decimal("10"),
            product_discount=Decimal("0"), view="1", highlight=False, save=MagicMock(),
        )
        with patch.object(crud.Product.objects, "filter") as products, \
                patch.object(crud.Category.objects, "filter") as categories, \
                patch.object(crud.Subcategory.objects, "filter") as subcategories:
            products.return_value.first.return_value = row
            categories.return_value.exists.return_value = True
            subcategories.return_value.exists.return_value = False
            response = self._patch({"id": 10, "category_id": 2})
        self.assertEqual(response.status_code, 400)
        self.assertIn("subcategory_id", response.data)
        row.save.assert_not_called()

    def test_subcategory_change_requires_subcategory_from_selected_category(self):
        row = SimpleNamespace(
            product_id=10, category_id=1, subcategory_id=5, product_name="Tea",
            code="T1", product_price=Decimal("10"), mrp=Decimal("10"),
            product_discount=Decimal("0"), view="1", highlight=False, save=MagicMock(),
        )
        with patch.object(crud.Product.objects, "filter") as products, \
                patch.object(crud.Subcategory.objects, "filter") as subcategories:
            products.return_value.first.return_value = row
            subcategories.return_value.exists.return_value = False
            response = self._patch({"id": 10, "subcategory_id": 99})
        self.assertEqual(response.status_code, 400)
        self.assertIn("subcategory_id", response.data)
        row.save.assert_not_called()


class ProductNoDiscountBannerValidationTests(SimpleTestCase):
    def test_accepts_exact_yes_no_values(self):
        self.assertEqual(crud.ProductCRUDView._validated_no_discount_banner('Y'), 'Y')
        self.assertEqual(crud.ProductCRUDView._validated_no_discount_banner('N'), 'N')
        self.assertEqual(crud.ProductCRUDView._validated_no_discount_banner(' y '), 'Y')
        self.assertEqual(crud.ProductCRUDView._validated_no_discount_banner(' n '), 'N')

    def test_rejects_unsupported_values(self):
        for value in ('', 'YES', 'NO', 'true', '0', None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    crud.ProductCRUDView._validated_no_discount_banner(value)

    def test_patch_saves_yes_and_returns_saved_value(self):
        row = SimpleNamespace(product_id=10, product_name='Tea', code='T1',
            product_price=Decimal('10'), mrp=Decimal('10'), product_discount=Decimal('0'),
            category_id=1, subcategory_id=None, no_discount_banner='N', disable_variants='N', view='1', highlight=False,
            save=MagicMock())
        request = APIRequestFactory().patch('/admin-api/products',
            {'id': 10, 'no_discount_banner': 'Y'}, format='json')
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, 'filter') as products:
            products.return_value.first.return_value = row
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(row.no_discount_banner, 'Y')
        self.assertEqual(response.data['no_discount_banner'], 'Y')
        row.save.assert_called_once()

    def test_invalid_patch_does_not_save_or_change_value(self):
        row = SimpleNamespace(product_id=10, product_name='Tea', code='T1',
            product_price=Decimal('10'), mrp=Decimal('10'), product_discount=Decimal('0'),
            category_id=1, subcategory_id=None, no_discount_banner='N', disable_variants='N', view='1', highlight=False,
            save=MagicMock())
        request = APIRequestFactory().patch('/admin-api/products',
            {'id': 10, 'no_discount_banner': 'YES'}, format='json')
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, 'filter') as products:
            products.return_value.first.return_value = row
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(row.no_discount_banner, 'N')
        row.save.assert_not_called()


class ProductFlutterDetailFieldSyncTests(SimpleTestCase):
    def test_admin_description_and_keywords_update_flutter_detail_columns(self):
        row = SimpleNamespace(
            product_id=10, category_id=1, subcategory_id=None, product_name='Tea', code='T1',
            product_price=Decimal('10'), mrp=Decimal('10'), product_discount=Decimal('0'),
            view='1', highlight=False, stock='', color='', gst_applicable='N',
            gst_percentage=Decimal('0'), gst_price=Decimal('0'), product_description='',
            product_keywords='', product_details='', additional_details='', no_discount_banner='N', disable_variants='N', save=MagicMock(),
        )
        request = APIRequestFactory().patch(
            '/admin-api/products',
            {'id': 10, 'description': 'Flutter-visible description', 'keywords': 'tea, green tea'},
            format='json',
        )
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, 'filter') as products:
            products.return_value.first.return_value = row
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(row.product_description, 'Flutter-visible description')
        self.assertEqual(row.product_details, 'Flutter-visible description')
        self.assertEqual(row.product_keywords, 'tea, green tea')
        self.assertEqual(row.additional_details, 'tea, green tea')
        row.save.assert_called_once()


class VariantPatchValidationTests(SimpleTestCase):
    def _patch(self, payload):
        request = APIRequestFactory().patch("/admin-api/product-variants", payload, format="json")
        force_authenticate(request, user=_user())
        return crud.VariantCRUDView.as_view()(request)

    def _row(self):
        return SimpleNamespace(
            variant_id=3, product_id=10, variant_name="500g",
            variant_price=Decimal("10"), mrp=Decimal("12"), quantity=5,
            disc="0", gst="N", gst_price=Decimal("0"), save=MagicMock(),
        )

    def test_discount_outside_create_range_is_rejected_on_patch(self):
        row = self._row()
        with patch.object(crud.Variant.objects, "filter") as variants:
            variants.return_value.first.return_value = row
            response = self._patch({"id": 3, "discount": "101"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("discount", response.data)
        row.save.assert_not_called()

    def test_invalid_gst_flag_is_rejected_on_patch(self):
        row = self._row()
        with patch.object(crud.Variant.objects, "filter") as variants:
            variants.return_value.first.return_value = row
            response = self._patch({"id": 3, "gst": "MAYBE"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("gst", response.data)
        row.save.assert_not_called()

    def test_non_finite_amount_is_rejected_on_patch(self):
        row = self._row()
        with patch.object(crud.Variant.objects, "filter") as variants:
            variants.return_value.first.return_value = row
            response = self._patch({"id": 3, "price": "NaN"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("price", response.data)
        row.save.assert_not_called()


class ProductFiniteValidationTests(SimpleTestCase):
    def test_non_finite_product_price_is_rejected_without_saving(self):
        row = SimpleNamespace(
            product_id=10, category_id=1, subcategory_id=None, product_name="Tea",
            code="T1", product_price=Decimal("10"), mrp=Decimal("10"),
            product_discount=Decimal("0"), view="1", highlight=False, save=MagicMock(),
        )
        request = APIRequestFactory().patch("/admin-api/products", {"id": 10, "price": "NaN"}, format="json")
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, "filter") as products:
            products.return_value.first.return_value = row
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        row.save.assert_not_called()


class VariantCreateValidationTests(SimpleTestCase):
    def test_non_finite_variant_amount_is_rejected(self):
        request = APIRequestFactory().post(
            "/admin-api/product-variants",
            {"product_id": 10, "name": "500g", "price": "NaN", "quantity": 5},
            format="json",
        )
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, "filter") as products:
            products.return_value.exists.return_value = True
            response = crud.VariantCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("finite", response.data["detail"])

class ProductSubcategoryIdValidationTests(SimpleTestCase):
    def test_non_numeric_subcategory_id_returns_400_without_saving(self):
        row = SimpleNamespace(
            product_id=10, category_id=1, subcategory_id=None, product_name="Tea",
            code="T1", product_price=Decimal("10"), mrp=Decimal("10"),
            product_discount=Decimal("0"), view="1", highlight=False, save=MagicMock(),
        )
        request = APIRequestFactory().patch(
            "/admin-api/products", {"id": 10, "subcategory_id": "not-an-id"}, format="json"
        )
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, "filter") as products:
            products.return_value.first.return_value = row
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("subcategory_id", response.data)
        row.save.assert_not_called()


class VariantQuantityValidationTests(SimpleTestCase):
    def test_fractional_quantity_is_rejected_on_patch(self):
        row = SimpleNamespace(
            variant_id=3, product_id=10, variant_name="500g",
            variant_price=Decimal("10"), mrp=Decimal("12"), quantity=5,
            disc="0", gst="N", gst_price=Decimal("0"), save=MagicMock(),
        )
        request = APIRequestFactory().patch(
            "/admin-api/product-variants", {"id": 3, "quantity": 1.5}, format="json"
        )
        force_authenticate(request, user=_user())
        with patch.object(crud.Variant.objects, "filter") as variants:
            variants.return_value.first.return_value = row
            response = crud.VariantCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("quantity", response.data)
        row.save.assert_not_called()

    def test_fractional_quantity_is_rejected_on_create(self):
        request = APIRequestFactory().post(
            "/admin-api/product-variants",
            {"product_id": 10, "name": "500g", "price": 10, "quantity": 1.5},
            format="json",
        )
        force_authenticate(request, user=_user())
        response = crud.VariantCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 400)

class ProductDisableVariantsAndDiscountPersistenceTests(SimpleTestCase):
    """Database-free tests: both product-level Y/N settings validate, persist and survive unrelated edits."""

    def _row(self, **overrides):
        values = dict(product_id=10, product_name='Tea', code='T1', product_price=Decimal('10'),
            mrp=Decimal('10'), product_discount=Decimal('0'), category_id=1, subcategory_id=None,
            no_discount_banner='N', disable_variants='N', view='1', highlight=False, stock='', color='',
            gst_applicable='N', gst_percentage=Decimal('0'), gst_price=Decimal('0'),
            product_description='', product_keywords='', product_details='', additional_details='',
            warehouse_id=0, save=MagicMock())
        values.update(overrides)
        return SimpleNamespace(**values)

    def _patch(self, row, payload):
        request = APIRequestFactory().patch('/admin-api/products', payload, format='json')
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, 'filter') as products:
            products.return_value.first.return_value = row
            return crud.ProductCRUDView.as_view()(request)

    def test_validator_accepts_only_y_or_n(self):
        view = crud.ProductCRUDView
        self.assertEqual(view._validated_disable_variants('Y'), 'Y')
        self.assertEqual(view._validated_disable_variants(' n '), 'N')
        for value in ('', 'YES', 'NO', 'true', '0', None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    view._validated_disable_variants(value)

    def test_disable_variants_yes_and_no_persist_and_return_strings(self):
        for value in ('Y', 'N'):
            with self.subTest(value=value):
                row = self._row(disable_variants='N' if value == 'Y' else 'Y')
                response = self._patch(row, {'id': 10, 'disable_variants': value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(row.disable_variants, value)
                self.assertEqual(response.data['disable_variants'], value)
                row.save.assert_called_once()

    def test_discount_yes_and_no_persist_and_return_strings(self):
        for value in ('Y', 'N'):
            with self.subTest(value=value):
                row = self._row(no_discount_banner='N' if value == 'Y' else 'Y')
                response = self._patch(row, {'id': 10, 'no_discount_banner': value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(row.no_discount_banner, value)
                self.assertEqual(response.data['no_discount_banner'], value)

    def test_invalid_disable_variants_is_rejected_without_change(self):
        row = self._row(disable_variants='Y')
        response = self._patch(row, {'id': 10, 'disable_variants': 'MAYBE'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('disable_variants', response.data)
        self.assertEqual(row.disable_variants, 'Y')
        row.save.assert_not_called()

    def test_unrelated_edit_does_not_reset_either_setting(self):
        row = self._row(no_discount_banner='Y', disable_variants='Y')
        response = self._patch(row, {'id': 10, 'name': 'Green Tea'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(row.no_discount_banner, 'Y')
        self.assertEqual(row.disable_variants, 'Y')
        self.assertEqual(response.data['no_discount_banner'], 'Y')
        self.assertEqual(response.data['disable_variants'], 'Y')

    def test_partial_update_of_one_setting_leaves_the_other_untouched(self):
        row = self._row(no_discount_banner='Y', disable_variants='N')
        self._patch(row, {'id': 10, 'disable_variants': 'Y'})
        self.assertEqual(row.no_discount_banner, 'Y')
        self.assertEqual(row.disable_variants, 'Y')

    def test_list_response_includes_both_settings_with_safe_default(self):
        request = APIRequestFactory().get('/admin-api/products')
        force_authenticate(request, user=_user())
        good = self._row(no_discount_banner='Y', disable_variants='Y')
        odd = self._row(product_id=11, no_discount_banner=None, disable_variants='?')
        with patch.object(crud.Product.objects, 'order_by') as ordered, \
                patch.object(crud.ProductImage.objects, 'filter') as images, \
                patch.object(crud.Category.objects, 'filter') as categories, \
                patch.object(crud.Variant.objects, 'filter') as variants:
            ordered.return_value.count.return_value = 2
            ordered.return_value.__getitem__.return_value = [good, odd]
            images.return_value.order_by.return_value = []
            categories.return_value.values_list.return_value = []
            variants.return_value.order_by.return_value = []
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        first, second = response.data['results']
        self.assertEqual((first['no_discount_banner'], first['disable_variants']), ('Y', 'Y'))
        self.assertEqual((second['no_discount_banner'], second['disable_variants']), ('N', 'N'))

    def test_list_can_be_limited_to_one_product_by_id(self):
        request = APIRequestFactory().get('/admin-api/products', {'id': 10, 'page_size': 1})
        force_authenticate(request, user=_user())
        row = self._row(no_discount_banner='Y', disable_variants='N')
        with patch.object(crud.Product.objects, 'order_by') as ordered, \
                patch.object(crud.ProductImage.objects, 'filter') as images, \
                patch.object(crud.Category.objects, 'filter') as categories, \
                patch.object(crud.Variant.objects, 'filter') as variants:
            filtered = ordered.return_value.filter.return_value
            filtered.count.return_value = 1
            filtered.__getitem__.return_value = [row]
            images.return_value.order_by.return_value = []
            categories.return_value.values_list.return_value = []
            variants.return_value.order_by.return_value = []
            response = crud.ProductCRUDView.as_view()(request)
        ordered.return_value.filter.assert_called_once_with(product_id=10)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['disable_variants'], 'N')

    def test_list_rejects_a_non_numeric_product_id(self):
        request = APIRequestFactory().get('/admin-api/products', {'id': 'abc'})
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, 'order_by'):
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 400)


class MinimumBuyingQuantityTests(SimpleTestCase):
    def test_quantity_validator_accepts_positive_whole_numbers(self):
        for value, expected in ((1, 1), ('12', 12), ('2147483647', 2147483647)):
            with self.subTest(value=value):
                self.assertEqual(crud.ProductCRUDView._validated_minimum_buying_quantity(value), expected)

    def test_quantity_validator_rejects_invalid_values(self):
        for value in (None, True, False, 0, -1, 1.5, '1.5', '2.0', '', '  ', '1e2', '+3', 'abc', '2147483648'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    crud.ProductCRUDView._validated_minimum_buying_quantity(value)

    def test_patch_persists_and_returns_minimum_buying_quantity(self):
        row = SimpleNamespace(
            product_id=10, product_name='Tea', code='T1', product_price=Decimal('10'),
            mrp=Decimal('10'), product_discount=Decimal('0'), category_id=1, subcategory_id=None,
            no_discount_banner='N', disable_variants='N', moq=1, view='1', highlight=False,
            set_contains='[]', save=MagicMock(),
        )
        request = APIRequestFactory().patch('/admin-api/products',
            {'id': 10, 'minimum_buying_quantity': 6}, format='json')
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, 'filter') as products:
            products.return_value.first.return_value = row
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(row.moq, 6)
        self.assertEqual(response.data['minimum_buying_quantity'], 6)
        row.save.assert_called_once()
        self.assertIn('moq', row.save.call_args.kwargs['update_fields'])

    def test_invalid_patch_quantity_does_not_save(self):
        row = SimpleNamespace(
            product_id=10, product_name='Tea', code='T1', product_price=Decimal('10'),
            mrp=Decimal('10'), product_discount=Decimal('0'), category_id=1, subcategory_id=None,
            no_discount_banner='N', disable_variants='N', moq=1, view='1', highlight=False,
            set_contains='[]', save=MagicMock(),
        )
        request = APIRequestFactory().patch('/admin-api/products',
            {'id': 10, 'minimum_buying_quantity': '1.5'}, format='json')
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, 'filter') as products:
            products.return_value.first.return_value = row
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn('minimum_buying_quantity', response.data)
        self.assertEqual(row.moq, 1)
        row.save.assert_not_called()


    def test_create_uses_compatible_default_when_quantity_is_omitted(self):
        created = SimpleNamespace(
            product_id=21, product_name='Tea', code='T2', product_price=Decimal('10'),
            category_id=1, subcategory_id=None, subtitle='', brand='', set_contains='[]',
            no_discount_banner='N', disable_variants='N', moq=1,
        )
        request = APIRequestFactory().post('/admin-api/products',
            {'name': 'Tea', 'code': 'T2', 'price': '10', 'mrp': '10', 'category_id': 1}, format='json')
        force_authenticate(request, user=_user())
        with patch.object(crud.Category.objects, 'filter') as categories, \
                patch.object(crud.Product.objects, 'create', return_value=created) as create_product:
            categories.return_value.exists.return_value = True
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['minimum_buying_quantity'], 1)
        self.assertEqual(create_product.call_args.kwargs['moq'], 1)

    def test_create_persists_requested_minimum_buying_quantity(self):
        created = SimpleNamespace(
            product_id=22, product_name='Tea', code='T3', product_price=Decimal('10'),
            category_id=1, subcategory_id=None, subtitle='', brand='', set_contains='[]',
            no_discount_banner='N', disable_variants='N', moq=6,
        )
        request = APIRequestFactory().post('/admin-api/products',
            {'name': 'Tea', 'code': 'T3', 'price': '10', 'mrp': '10', 'category_id': 1, 'minimum_buying_quantity': 6}, format='json')
        force_authenticate(request, user=_user())
        with patch.object(crud.Category.objects, 'filter') as categories, \
                patch.object(crud.Product.objects, 'create', return_value=created) as create_product:
            categories.return_value.exists.return_value = True
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['minimum_buying_quantity'], 6)
        self.assertEqual(create_product.call_args.kwargs['moq'], 6)


# ---------------------------------------------------------------------------------------------------
# Minimum Purchase Quantity (`minimum_buying_count`) - mocked tests (no database).
# The real-database checks live in scripts/verify_minimum_purchase_quantity_rollback.py.
# ---------------------------------------------------------------------------------------------------
INVALID_MINIMUM_VALUES = (None, '', '  ', 0, -1, '0', '-3', 1.5, '1.5', 2.0, '2.0', '1e2', '+3', True, False, 'abc', 2147483648)


def _product_row(moq=1, **extra):
    return SimpleNamespace(
        product_id=10, product_name='Tea', code='T1', product_price=Decimal('10'), mrp=Decimal('10'),
        product_discount=Decimal('0'), category_id=1, subcategory_id=None, no_discount_banner='N',
        disable_variants='N', moq=moq, view='1', highlight=False, set_contains='[]', save=MagicMock(), **extra)


def _variant_row(variant_id=3, minimum=5, quantity=5):
    return SimpleNamespace(
        variant_id=variant_id, product_id=10, variant_name='500g', variant_price=Decimal('10'),
        mrp=Decimal('12'), quantity=quantity, disc='0', gst='N', gst_price=Decimal('0'),
        minimum_buying_count=minimum, save=MagicMock())


class MinimumPurchaseQuantityValidatorTests(SimpleTestCase):
    def test_accepts_positive_whole_numbers(self):
        for value, expected in ((1, 1), ('12', 12), (' 7 ', 7), ('2147483647', 2147483647)):
            with self.subTest(value=value):
                self.assertEqual(crud._validated_minimum_purchase_quantity(value), expected)

    def test_rejects_empty_zero_negative_decimal_exponent_boolean_and_text(self):
        for value in INVALID_MINIMUM_VALUES:
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    crud._validated_minimum_purchase_quantity(value)
                self.assertTrue(str(caught.exception))

    def test_message_is_field_specific(self):
        with self.assertRaises(ValueError) as caught:
            crud._validated_minimum_purchase_quantity('1.5')
        self.assertEqual(str(caught.exception), 'Minimum purchase quantity must be a positive whole number.')


class ProductMinimumPurchaseAliasTests(SimpleTestCase):
    def _post(self, payload):
        body = {'name': 'Tea', 'code': 'T9', 'price': '10', 'mrp': '10', 'category_id': 1, **payload}
        request = APIRequestFactory().post('/admin-api/products', body, format='json')
        force_authenticate(request, user=_user())
        created = SimpleNamespace(product_id=30, product_name='Tea', code='T9', product_price=Decimal('10'),
                                  category_id=1, subcategory_id=None, subtitle='', brand='', set_contains='[]',
                                  no_discount_banner='N', disable_variants='N', moq=1)
        with patch.object(crud.Category.objects, 'filter') as categories, \
                patch.object(crud.Product.objects, 'create') as create_product:
            categories.return_value.exists.return_value = True
            def make(**kwargs):
                created.moq = kwargs['moq']
                return created
            create_product.side_effect = make
            response = crud.ProductCRUDView.as_view()(request)
        return response, create_product

    def _patch(self, row, payload):
        request = APIRequestFactory().patch('/admin-api/products', {'id': 10, **payload}, format='json')
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, 'filter') as products:
            products.return_value.first.return_value = row
            return crud.ProductCRUDView.as_view()(request)

    def test_create_with_minimum_buying_count_one_and_greater_than_one(self):
        for value in (1, 10):
            with self.subTest(value=value):
                response, create_product = self._post({'minimum_buying_count': value})
                self.assertEqual(response.status_code, 201)
                self.assertEqual(create_product.call_args.kwargs['moq'], value)
                self.assertEqual(response.data['minimum_buying_count'], value)
                self.assertEqual(response.data['minimum_buying_quantity'], value)

    def test_create_defaults_to_one_when_neither_name_is_sent(self):
        response, create_product = self._post({})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(create_product.call_args.kwargs['moq'], 1)

    def test_legacy_minimum_buying_quantity_payload_is_still_supported(self):
        response, create_product = self._post({'minimum_buying_quantity': 6})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(create_product.call_args.kwargs['moq'], 6)
        self.assertEqual(response.data['minimum_buying_count'], 6)

    def test_matching_aliases_are_accepted_and_conflicting_aliases_return_400(self):
        response, create_product = self._post({'minimum_buying_count': 4, 'minimum_buying_quantity': 4})
        self.assertEqual(response.status_code, 201)
        response, create_product = self._post({'minimum_buying_count': 4, 'minimum_buying_quantity': 9})
        self.assertEqual(response.status_code, 400)
        self.assertIn('minimum_buying_count', response.data)
        self.assertIn('minimum_buying_quantity', response.data)
        create_product.assert_not_called()

    def test_create_rejects_invalid_values_without_writing(self):
        for value in INVALID_MINIMUM_VALUES:
            with self.subTest(value=value):
                response, create_product = self._post({'minimum_buying_count': value})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['minimum_buying_count'], crud.MIN_PURCHASE_QUANTITY_MESSAGE
                                 if value != 2147483648 else 'Minimum purchase quantity is too large.')
                create_product.assert_not_called()

    def test_invalid_legacy_alias_error_names_the_legacy_field(self):
        response, create_product = self._post({'minimum_buying_quantity': '1.5'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('minimum_buying_quantity', response.data)
        create_product.assert_not_called()

    def test_patch_updates_the_existing_moq_column_through_either_name(self):
        for key in ('minimum_buying_count', 'minimum_buying_quantity'):
            with self.subTest(key=key):
                row = _product_row(moq=1)
                response = self._patch(row, {key: 6})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(row.moq, 6)
                self.assertIn('moq', row.save.call_args.kwargs['update_fields'])
                self.assertEqual(response.data['minimum_buying_count'], 6)
                self.assertEqual(response.data['minimum_buying_quantity'], 6)

    def test_patch_without_the_field_preserves_the_saved_value(self):
        row = _product_row(moq=12)
        response = self._patch(row, {'name': 'Tea (new)'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(row.moq, 12)
        self.assertNotIn('moq', row.save.call_args.kwargs['update_fields'])
        self.assertEqual(response.data['minimum_buying_count'], 12)

    def test_patch_rejects_invalid_and_conflicting_values_without_saving(self):
        for payload in ([{'minimum_buying_count': value} for value in INVALID_MINIMUM_VALUES]
                        + [{'minimum_buying_count': 2, 'minimum_buying_quantity': 3}]):
            with self.subTest(payload=payload):
                row = _product_row(moq=12)
                response = self._patch(row, payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(row.moq, 12)
                row.save.assert_not_called()

    def test_product_list_returns_both_names_and_each_variants_own_value(self):
        product = _product_row(moq=10)
        product.stock = ''
        product.color = ''
        product.gst_applicable = 'N'
        product.gst_percentage = Decimal('0')
        product.gst_price = Decimal('0')
        product.product_description = ''
        product.product_keywords = ''
        product.product_details = ''
        product.additional_details = ''
        product.warehouse_id = 0
        variants = [_variant_row(1, minimum=5), _variant_row(2, minimum=12)]
        request = APIRequestFactory().get('/admin-api/products', {'id': 10})
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, 'order_by') as order_by, \
                patch.object(crud.ProductImage.objects, 'filter') as images, \
                patch.object(crud.Category.objects, 'filter') as categories, \
                patch.object(crud.Variant.objects, 'filter') as variant_filter:
            queryset = order_by.return_value
            queryset.filter.return_value = queryset
            queryset.count.return_value = 1
            queryset.__getitem__.return_value = [product]
            images.return_value.order_by.return_value = []
            categories.return_value.values_list.return_value = []
            variant_filter.return_value.order_by.return_value = variants
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        item = response.data['results'][0]
        self.assertEqual((item['minimum_buying_count'], item['minimum_buying_quantity']), (10, 10))
        self.assertEqual([v['minimum_buying_count'] for v in item['variants']], [5, 12])

    def test_legacy_rows_with_zero_or_null_moq_are_reported_as_one(self):
        for stored in (0, None):
            with self.subTest(stored=stored):
                fields = crud.ProductCRUDView._minimum_purchase_fields_out(_product_row(moq=stored))
                self.assertEqual(fields, {'minimum_buying_count': 1, 'minimum_buying_quantity': 1})


class VariantMinimumPurchaseQuantityTests(SimpleTestCase):
    def _post(self, payload, created_minimum=None):
        body = {'product_id': 10, 'name': '25 kg bag', 'price': '100', 'mrp': '120', 'quantity': 50, **payload}
        request = APIRequestFactory().post('/admin-api/product-variants', body, format='json')
        force_authenticate(request, user=_user())
        def make(**kwargs):
            return SimpleNamespace(variant_id=77, product_id=kwargs['product_id'], variant_name=kwargs['variant_name'],
                                   variant_price=kwargs['variant_price'], mrp=kwargs['mrp'], quantity=kwargs['quantity'],
                                   disc=kwargs['disc'], gst=kwargs['gst'], gst_price=kwargs['gst_price'],
                                   minimum_buying_count=kwargs['minimum_buying_count'])
        with patch.object(crud.Product.objects, 'filter') as products, \
                patch.object(crud.Variant.objects, 'create', side_effect=make) as create_variant:
            products.return_value.exists.return_value = True
            response = crud.VariantCRUDView.as_view()(request)
        return response, create_variant

    def _patch(self, rows, payload):
        request = APIRequestFactory().patch('/admin-api/product-variants', payload, format='json')
        force_authenticate(request, user=_user())
        with patch.object(crud.Variant.objects, 'filter') as variants:
            variants.side_effect = lambda pk=None, **kw: SimpleNamespace(first=lambda: rows.get(pk))
            response = crud.VariantCRUDView.as_view()(request)
        return response

    def test_create_defaults_to_one_only_when_the_field_is_omitted(self):
        response, create_variant = self._post({})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(create_variant.call_args.kwargs['minimum_buying_count'], 1)
        self.assertEqual(response.data['minimum_buying_count'], 1)

    def test_create_persists_a_custom_value_and_returns_it(self):
        response, create_variant = self._post({'minimum_buying_count': 12})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(create_variant.call_args.kwargs['minimum_buying_count'], 12)
        self.assertEqual(response.data['minimum_buying_count'], 12)
        self.assertEqual(response.data['quantity'], 50, 'stock quantity is a separate field')

    def test_create_rejects_invalid_values_before_any_database_write(self):
        for value in INVALID_MINIMUM_VALUES:
            with self.subTest(value=value):
                response, create_variant = self._post({'minimum_buying_count': value})
                self.assertEqual(response.status_code, 400)
                self.assertIn('minimum_buying_count', response.data)
                create_variant.assert_not_called()

    def test_patch_updates_only_the_selected_variant(self):
        a, b = _variant_row(1, minimum=5), _variant_row(2, minimum=12)
        response = self._patch({1: a, 2: b}, {'id': 2, 'minimum_buying_count': 20})
        self.assertEqual(response.status_code, 200)
        self.assertEqual((a.minimum_buying_count, b.minimum_buying_count), (5, 20))
        a.save.assert_not_called()
        self.assertEqual(b.save.call_args.kwargs['update_fields'], ['minimum_buying_count'])
        self.assertEqual(response.data['minimum_buying_count'], 20)

    def test_patch_without_the_field_preserves_the_saved_value(self):
        row = _variant_row(1, minimum=9)
        response = self._patch({1: row}, {'id': 1, 'quantity': 40, 'name': 'renamed'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(row.minimum_buying_count, 9)
        self.assertNotIn('minimum_buying_count', row.save.call_args.kwargs['update_fields'])
        self.assertEqual(response.data['minimum_buying_count'], 9)

    def test_patch_rejects_invalid_values_without_changing_or_saving(self):
        for value in INVALID_MINIMUM_VALUES:
            with self.subTest(value=value):
                row = _variant_row(1, minimum=9)
                response = self._patch({1: row}, {'id': 1, 'minimum_buying_count': value})
                self.assertEqual(response.status_code, 400)
                self.assertIn('minimum_buying_count', response.data)
                row.save.assert_not_called()

    def test_get_returns_each_variants_stored_value(self):
        rows = [_variant_row(1, minimum=5), _variant_row(2, minimum=12), _variant_row(3, minimum=1)]
        queryset = MagicMock()
        queryset.filter.return_value = queryset
        queryset.count.return_value = 3
        queryset.__getitem__.return_value = rows
        request = APIRequestFactory().get('/admin-api/product-variants', {'product_id': 10})
        force_authenticate(request, user=_user())
        with patch.object(crud.Variant.objects, 'order_by', return_value=queryset):
            response = crud.VariantCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['minimum_buying_count'] for r in response.data['results']], [5, 12, 1])

    def test_product_patch_never_touches_variant_rows(self):
        row = _product_row(moq=10)
        request = APIRequestFactory().patch('/admin-api/products', {'id': 10, 'minimum_buying_count': 3}, format='json')
        force_authenticate(request, user=_user())
        with patch.object(crud.Product.objects, 'filter') as products, \
                patch.object(crud.Variant.objects, 'filter') as variants, \
                patch.object(crud.Variant.objects, 'update', create=True) as variant_update:
            products.return_value.first.return_value = row
            response = crud.ProductCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(row.moq, 3)
        variants.assert_not_called()
        variant_update.assert_not_called()
