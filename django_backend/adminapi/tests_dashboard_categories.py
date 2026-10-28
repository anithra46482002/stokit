"""Database-free regression tests for the dashboard and category endpoints (ORM calls are mocked)."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from adminapi import crud, views


def _user(role="ADMIN"):
    return SimpleNamespace(is_authenticated=True, role=role, pk=1, principal_type="ADMIN")


class CategoryDeleteTests(SimpleTestCase):
    def _delete(self, role="ADMIN"):
        request = APIRequestFactory().delete("/admin-api/categories?id=3")
        force_authenticate(request, user=_user(role))
        return crud.CategoryCRUDView.as_view()(request)

    def test_category_with_products_cannot_be_deleted(self):
        # Regression: Product was not imported in crud.py, so this path raised NameError (HTTP 500).
        row = MagicMock()
        with patch.object(crud.Category.objects, "filter") as cat, \
                patch.object(crud.Subcategory.objects, "filter") as sub, \
                patch.object(crud.Product.objects, "filter") as prod:
            cat.return_value.first.return_value = row
            sub.return_value.exists.return_value = False
            prod.return_value.exists.return_value = True
            response = self._delete()
        self.assertEqual(response.status_code, 409)
        row.delete.assert_not_called()

    def test_salesman_cannot_delete_category(self):
        self.assertEqual(self._delete("SALESMAN").status_code, 403)


class CategoryListTests(SimpleTestCase):
    @override_settings(LEGACY_BASE_URL="https://example.invalid/admin/manage/")
    def test_list_returns_absolute_image_url(self):
        item = SimpleNamespace(category_id=1, category_name="Gifts", category_image="uploads/a.webp", category_active=True)
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.count.return_value = 1
        qs.__getitem__.return_value = [item]
        with patch.object(crud.Category.objects, "order_by", return_value=qs):
            request = APIRequestFactory().get("/admin-api/categories")
            force_authenticate(request, user=_user())
            response = crud.CategoryCRUDView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["image_url"], "https://example.invalid/admin/manage/uploads/a.webp")


class DashboardTests(SimpleTestCase):
    def test_revenue_uses_normalized_completed_order_statuses(self):
        self.assertEqual(views.REVENUE_STATUSES, ('delivered', 'fulfilled'))
        self.assertNotIn('cancelled', views.REVENUE_STATUSES)
        self.assertNotIn('pending', views.REVENUE_STATUSES)