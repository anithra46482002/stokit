from types import SimpleNamespace
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory
from adminapi.permissions import AdminRolePermission

class AdminRolePolicyTests(SimpleTestCase):
    def setUp(self):
        self.permission = AdminRolePermission()
        self.factory = APIRequestFactory()

    def check(self, role, method, resource):
        request = getattr(self.factory, method.lower())('/admin-api/test')
        request.user = SimpleNamespace(is_authenticated=True, role=role)
        view = SimpleNamespace(required_resource=resource)
        return self.permission.has_permission(request, view)

    def test_unassigned_admin_is_denied(self):
        self.assertFalse(self.check(None, 'GET', 'catalogue'))
        self.assertFalse(self.check(None, 'POST', 'orders'))

    def test_salesman_can_read_customers_but_cannot_write_catalogue(self):
        self.assertTrue(self.check('SALESMAN', 'GET', 'customers'))
        self.assertFalse(self.check('SALESMAN', 'POST', 'catalogue'))
        self.assertFalse(self.check('SALESMAN', 'DELETE', 'customers'))

    def test_warehouse_staff_can_adjust_inventory_but_not_customers(self):
        self.assertTrue(self.check('WAREHOUSE_STAFF', 'PATCH', 'inventory'))
        self.assertFalse(self.check('WAREHOUSE_STAFF', 'GET', 'customers'))

    def test_delivery_role_is_limited_to_orders(self):
        self.assertTrue(self.check('DELIVERY_BOY', 'GET', 'orders'))
        self.assertFalse(self.check('DELIVERY_BOY', 'GET', 'reports'))
        self.assertFalse(self.check('DELIVERY_BOY', 'POST', 'notifications'))

    def test_super_admin_can_access_all_resources(self):
        self.assertTrue(self.check('SUPER_ADMIN', 'DELETE', 'catalogue'))
        self.assertTrue(self.check('SUPER_ADMIN', 'POST', 'staff'))
