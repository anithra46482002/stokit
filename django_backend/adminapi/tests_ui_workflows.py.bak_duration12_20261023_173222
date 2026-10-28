"""Database-free regression tests for order filters, order creation, and banner image updates."""
from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest import mock

from adminapi import crud, operations, order_pages
from adminapi.finance import REVENUE_STATUS_KEYS, PENDING_STATUS_KEYS, build_order_summary_query
from adminapi.order_pages import _filters


class OrderFilterTests(TestCase):
    def test_from_date_only_does_not_add_today_upper_bound(self):
        where, args = _filters({"from_date": "2026-01-01"}, default_today=True)
        self.assertIn("c.order_date >= %s", where)
        self.assertNotIn("CURRENT_DATE", where)
        self.assertEqual(args, ["2026-01-01 00:00:00"])
    def test_to_date_only_uses_exclusive_next_day_boundary(self):
        where, args = _filters({'to_date': '2026-01-31'}, default_today=True)
        self.assertIn('c.order_date < %s', where)
        self.assertNotIn('CURRENT_DATE', where)
        self.assertEqual(args, ['2026-02-01 00:00:00'])
        # Exclusive next-day boundary includes fractional timestamps on the final day.

    def test_delivery_boy_filter_is_parameterized_and_validated(self):
        where, args = _filters({"delivery_boy_id": "8"}, default_today=False)
        self.assertIn("c.delivery_boy_id = %s", where)
        self.assertEqual(args, [8])
        with self.assertRaisesRegex(ValueError, "delivery_boy_id"):
            _filters({"delivery_boy_id": "0"}, default_today=False)
    def test_no_date_filter_defaults_to_today_for_summary(self):
        where, args = _filters({}, default_today=True)
        self.assertIn("c.order_date >= CURRENT_DATE", where)
        self.assertIn("CURRENT_DATE + INTERVAL '1 day'", where)
        self.assertEqual(args, [])

    def test_status_color_and_warehouse_filters_are_parameterized(self):
        where, args = _filters({"status": "pending", "color_code": "#112233", "warehouse_id": "4"}, default_today=False)
        self.assertIn("c.status = %s", where)
        self.assertIn("u.color_code = %s", where)
        self.assertIn("u.warehouse_id = %s", where)
        self.assertEqual(args, ["pending", "#112233", 4])


class AdminOrderCreateTests(TestCase):
    def test_create_uses_database_product_price_not_client_price(self):
        request = SimpleNamespace(data={
            "full_name": "Sample Customer", "email": "sample@example.test", "phone": "9876543210",
            "address": "10 Test Road", "city": "Kochi", "state": "Kerala", "postal_code": "682001",
            "country": "India", "payment_method": "COD",
            "items": [{"product_id": 3, "quantity": 2, "price": 0.01}],
        })
        request.user = SimpleNamespace(role="ADMIN")
        product = SimpleNamespace(product_id=3, product_name="Test Product", product_price=Decimal("12.00"))
        product_manager = mock.Mock()
        product_manager.filter.return_value.first.return_value = product
        variant_manager = mock.Mock()
        variant_manager.filter.return_value.exists.return_value = False
        checkout_manager = mock.Mock()
        checkout_manager.create.return_value = SimpleNamespace(order_id=55, status="Placed")
        item_manager = mock.Mock()
        history_manager = mock.Mock()
        with mock.patch.object(crud.Product, "objects", product_manager), \
             mock.patch.object(crud.Variant, "objects", variant_manager), \
             mock.patch.object(crud.Checkout, "objects", checkout_manager), \
             mock.patch.object(crud.OrderItem, "objects", item_manager), \
             mock.patch.object(crud.OrderStatusHistory, "objects", history_manager), \
             mock.patch.object(crud.transaction, "atomic", return_value=nullcontext()):
            response = crud.OrderAdminCRUDView().post(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total_amount"], "24.00")
        checkout_manager.create.assert_called_once()
        self.assertEqual(checkout_manager.create.call_args.kwargs["total_amount"], Decimal("24.00"))
        item_manager.create.assert_called_once()
        self.assertEqual(item_manager.create.call_args.kwargs["price"], Decimal("12.00"))
        self.assertEqual(item_manager.create.call_args.kwargs["total_price"], Decimal("24.00"))
        history_manager.create.assert_called_once()

    def test_create_rejects_duplicate_product_variant_lines_before_writing(self):
        request = SimpleNamespace(data={
            'full_name': 'Sample Customer', 'email': 'sample@example.test', 'phone': '9876543210',
            'address': '10 Test Road',
            'items': [{'product_id': 3, 'quantity': 1}, {'product_id': 3, 'quantity': 2}],
        })
        request.user = SimpleNamespace(role='ADMIN')
        product_manager = mock.Mock()
        product_manager.filter.return_value.first.return_value = SimpleNamespace(product_id=3, product_name='Test Product', product_price=Decimal('10.00'))
        variant_manager = mock.Mock()
        variant_manager.filter.return_value.exists.return_value = False
        with mock.patch.object(crud.Product, 'objects', product_manager), mock.patch.object(crud.Variant, 'objects', variant_manager):
            with mock.patch.object(crud.Checkout, 'objects') as checkout_manager:
                response = crud.OrderAdminCRUDView().post(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn('duplicate', response.data['items'].lower())
        product_manager.filter.assert_called_once_with(pk=3)
        checkout_manager.create.assert_not_called()

class WarehouseCoordinateValidationTests(TestCase):
    def test_valid_coordinates_are_parsed_and_out_of_range_values_rejected(self):
        latitude, error = operations.WarehouseAdminView._coordinate("9.12345678", "latitude", -90, 90)
        self.assertIsNone(error)
        self.assertEqual(latitude, Decimal("9.12345678"))
        value, error = operations.WarehouseAdminView._coordinate("91", "latitude", -90, 90)
        self.assertIsNone(value)
        self.assertIn("latitude", error)


class OrderCreatePermissionTests(TestCase):
    def test_only_admin_roles_can_post_orders(self):
        permission = crud.AdminRolePermission()
        view = SimpleNamespace(required_resource="orders")
        admin_request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True, role="ADMIN"), method="POST")
        sales_request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True, role="SALESMAN"), method="POST")
        self.assertTrue(permission.has_permission(admin_request, view))
        self.assertFalse(permission.has_permission(sales_request, view))

class BannerImageUpdateTests(TestCase):
    def _banner(self):
        return SimpleNamespace(
            slider_id=5, image_path="uploads/original.png", text_content="old",
            styled_text="", styled_color="", back="", text_content2="", save=mock.Mock(),
        )

    def test_patch_without_replacement_preserves_existing_image(self):
        banner = self._banner()
        manager = mock.Mock()
        manager.filter.return_value.first.return_value = banner
        request = SimpleNamespace(data={"id": 5, "text_content": "changed"})
        with mock.patch.object(operations.Slider, "objects", manager):
            response = operations.BannerAdminView().patch(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(banner.image_path, "uploads/original.png")
        self.assertEqual(banner.text_content, "changed")
        banner.save.assert_called_once()

    def test_post_creates_banner_with_uploaded_image_path(self):
        banner = self._banner()
        manager = mock.Mock()
        manager.create.return_value = banner
        request = SimpleNamespace(data={"image_path": "uploads/new-banner.png", "text_content": "new"})
        with mock.patch.object(operations.Slider, "objects", manager):
            response = operations.BannerAdminView().post(request)
        self.assertEqual(response.status_code, 201)
        manager.create.assert_called_once()
        self.assertEqual(manager.create.call_args.kwargs["image_path"], "uploads/new-banner.png")
    def test_patch_replaces_image_path_when_supplied(self):
        banner = self._banner()
        manager = mock.Mock()
        manager.filter.return_value.first.return_value = banner
        request = SimpleNamespace(data={"id": 5, "image_path": "uploads/replacement.webp"})
        with mock.patch.object(operations.Slider, "objects", manager):
            response = operations.BannerAdminView().patch(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(banner.image_path, "uploads/replacement.webp")
        banner.save.assert_called_once()

    def test_patch_rejects_non_string_image_path_and_keeps_existing_image(self):
        for bad in (5, None, ["x"], {"a": 1}):
            banner = self._banner()
            manager = mock.Mock()
            manager.filter.return_value.first.return_value = banner
            request = SimpleNamespace(data={"id": 5, "image_path": bad})
            with mock.patch.object(operations.Slider, "objects", manager):
                response = operations.BannerAdminView().patch(request)
            self.assertEqual(response.status_code, 400, bad)
            self.assertEqual(banner.image_path, "uploads/original.png")
            banner.save.assert_not_called()

    def test_patch_null_text_field_is_stored_empty_not_none_literal(self):
        banner = self._banner()
        manager = mock.Mock()
        manager.filter.return_value.first.return_value = banner
        request = SimpleNamespace(data={"id": 5, "text_content": None})
        with mock.patch.object(operations.Slider, "objects", manager):
            response = operations.BannerAdminView().patch(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(banner.text_content, "")


class FinancialSummaryQueryTests(TestCase):
    def test_financial_summary_counts_completed_revenue_and_open_orders_only(self):
        sql, params = build_order_summary_query('FROM zg_checkout c', ' WHERE c.order_date >= %s')
        self.assertIn('LOWER(TRIM(t.status)) IN (%s, %s)', sql)
        self.assertIn('SELECT DISTINCT c.order_id, c.status, c.total_amount', sql)
        self.assertEqual(params[:2], ['delivered', 'fulfilled'])
        self.assertEqual(params[2:], list(PENDING_STATUS_KEYS))
        self.assertNotIn('cancelled', params)
        self.assertNotIn('failed', params)
        self.assertIn('WHERE c.order_date >= %s', sql)

    def test_revenue_statuses_include_legacy_lowercase_and_exclude_cancelled(self):
        self.assertEqual(REVENUE_STATUS_KEYS, ('delivered', 'fulfilled'))
        self.assertNotIn('cancelled', REVENUE_STATUS_KEYS)
        self.assertNotIn('pending', REVENUE_STATUS_KEYS)


class OrderManageReadOnlyTests(TestCase):
    class Cursor:
        def __init__(self):
            self.queries = []
            self.current_sql = ''
            self.columns = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @property
        def description(self):
            return [(name,) for name in self.columns]

        def execute(self, sql, params=None):
            self.current_sql = sql
            self.queries.append((sql, params or []))
            if sql.lstrip().startswith('SELECT DISTINCT c.order_id'):
                self.columns = ['order_id', 'full_name', 'order_date', 'total_amount', 'payment_method', 'status', 'delivery_boy_id', 'item_count']
            elif sql.lstrip().startswith('SELECT COUNT(*) AS total_orders'):
                self.columns = ['total_orders', 'revenue', 'pending_orders']
            elif 'SELECT id, fullname FROM delivery_boys' in sql:
                self.columns = ['id', 'fullname']
            elif 'SELECT DISTINCT color_code' in sql:
                self.columns = ['color_code']
            elif 'SELECT DISTINCT warehouse_id' in sql:
                self.columns = ['warehouse_id']
            elif 'SELECT DISTINCT status' in sql:
                self.columns = ['status']

        def fetchall(self):
            if 'SELECT COUNT(*) AS total_orders' in self.current_sql:
                return [(0, Decimal('0.00'), 0)]
            return []

    def test_order_management_get_is_read_only_and_handles_empty_data(self):
        cursor = self.Cursor()
        request = SimpleNamespace(query_params={})
        with mock.patch.object(order_pages.connection, 'cursor', return_value=cursor):
            response = order_pages.OrderManageView().get(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['stats'], {'total_orders': 0, 'revenue': '0.00', 'pending_orders': 0})
        self.assertFalse(any(sql.lstrip().upper().startswith(('UPDATE', 'INSERT', 'DELETE')) for sql, _ in cursor.queries))

    def test_invalid_calendar_date_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'real date'):
            _filters({'from_date': '2026-02-30'}, default_today=False)


class AdminOrderVariantTests(TestCase):
    def _request(self, item):
        request = SimpleNamespace(data={
            'full_name': 'Sample Customer', 'email': 'sample@example.test', 'phone': '9876543210',
            'address': '10 Test Road', 'items': [item],
        })
        request.user = SimpleNamespace(role='ADMIN')
        return request

    def test_create_requires_variant_when_product_has_variants(self):
        product_manager = mock.Mock()
        product_manager.filter.return_value.first.return_value = SimpleNamespace(product_id=3, product_name='Variant Product', product_price=Decimal('10.00'))
        variant_manager = mock.Mock()
        variant_manager.filter.return_value.exists.return_value = True
        with mock.patch.object(crud.Product, 'objects', product_manager), mock.patch.object(crud.Variant, 'objects', variant_manager):
            with mock.patch.object(crud.Checkout, 'objects') as checkout_manager:
                response = crud.OrderAdminCRUDView().post(self._request({'product_id': 3, 'quantity': 1}))
        self.assertEqual(response.status_code, 400)
        self.assertIn('choose a variant', response.data['items'].lower())
        checkout_manager.create.assert_not_called()

    def test_create_rejects_variant_not_owned_by_product(self):
        product_manager = mock.Mock()
        product_manager.filter.return_value.first.return_value = SimpleNamespace(product_id=3, product_name='Variant Product', product_price=Decimal('10.00'))
        variant_manager = mock.Mock()
        variant_manager.filter.return_value.first.return_value = None
        with mock.patch.object(crud.Product, 'objects', product_manager), mock.patch.object(crud.Variant, 'objects', variant_manager):
            with mock.patch.object(crud.Checkout, 'objects') as checkout_manager:
                response = crud.OrderAdminCRUDView().post(self._request({'product_id': 3, 'variant_id': 99, 'quantity': 1}))
        self.assertEqual(response.status_code, 400)
        self.assertIn('does not belong', response.data['items'].lower())
        checkout_manager.create.assert_not_called()

    def test_create_uses_database_variant_price(self):
        product_manager = mock.Mock()
        product_manager.filter.return_value.first.return_value = SimpleNamespace(product_id=3, product_name='Variant Product', product_price=Decimal('10.00'))
        variant_manager = mock.Mock()
        variant_manager.filter.return_value.first.return_value = SimpleNamespace(variant_id=99, variant_name='Large', variant_price=Decimal('15.00'))
        checkout_manager = mock.Mock()
        checkout_manager.create.return_value = SimpleNamespace(order_id=77, status='Placed')
        item_manager = mock.Mock()
        history_manager = mock.Mock()
        with mock.patch.object(crud.Product, 'objects', product_manager), \
             mock.patch.object(crud.Variant, 'objects', variant_manager), \
             mock.patch.object(crud.Checkout, 'objects', checkout_manager), \
             mock.patch.object(crud.OrderItem, 'objects', item_manager), \
             mock.patch.object(crud.OrderStatusHistory, 'objects', history_manager), \
             mock.patch.object(crud.transaction, 'atomic', return_value=nullcontext()):
            response = crud.OrderAdminCRUDView().post(self._request({'product_id': 3, 'variant_id': 99, 'quantity': 2}))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['total_amount'], '30.00')
        self.assertEqual(item_manager.create.call_args.kwargs['price'], Decimal('15.00'))
        self.assertEqual(item_manager.create.call_args.kwargs['variant_name'], 'Large')
