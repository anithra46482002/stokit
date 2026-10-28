from django.urls import path

from .views import AdminLoginView, AdminRefreshView, DashboardView, CategoryListView, ProductListView, CustomerListView, OrderListView
from .crud import CategoryCRUDView, SubcategoryCRUDView, ProductCRUDView, VariantCRUDView, ProductImageCRUDView, CustomerCRUDView, OrderAdminCRUDView
from .operations import BannerAdminView, NotificationAdminView, WarehouseAdminView, InventoryAdminView, StaffAdminView, AdvancePaymentAdminView, ReportsAdminView, LocationAdminView, TargetAdminView, TargetAssignmentAdminView
from .advance_allocations import AdvanceAllocationAdminView
from .allocation_management import AllocationManagementView
from .uploads import ImageUploadView
from .offers import AdvancePaymentOffersView
from .cart_discount import CartDiscountSettingsView
from .order_pages import OrderManageView, OrderBulkAssignView, OrderDetailView, OrderStatusView

urlpatterns = [
    path("auth/login", AdminLoginView.as_view(), name="admin-login"),
    path("auth/refresh", AdminRefreshView.as_view(), name="admin-refresh"),
    path("uploads", ImageUploadView.as_view(), name="admin-uploads"),
    path("dashboard", DashboardView.as_view(), name="admin-dashboard"),
    path("reports", ReportsAdminView.as_view(), name="admin-reports"),
    path("categories", CategoryCRUDView.as_view(), name="admin-categories"),
    path("subcategories", SubcategoryCRUDView.as_view(), name="admin-subcategories"),
    path("products", ProductCRUDView.as_view(), name="admin-products"),
    path("product-variants", VariantCRUDView.as_view(), name="admin-product-variants"),
    path("product-images", ProductImageCRUDView.as_view(), name="admin-product-images"),
    path("customers", CustomerCRUDView.as_view(), name="admin-customers"),
    path("orders", OrderAdminCRUDView.as_view(), name="admin-orders"),
    path("orders/manage", OrderManageView.as_view(), name="admin-orders-manage"),
    path("orders/bulk-assign", OrderBulkAssignView.as_view(), name="admin-orders-bulk-assign"),
    path("orders/<int:order_id>/detail", OrderDetailView.as_view(), name="admin-order-detail"),
    path("orders/<int:order_id>/status", OrderStatusView.as_view(), name="admin-order-status"),
    path("banners", BannerAdminView.as_view(), name="admin-banners"),
    path("notifications", NotificationAdminView.as_view(), name="admin-notifications"),
    path("warehouses", WarehouseAdminView.as_view(), name="admin-warehouses"),
    path("inventory", InventoryAdminView.as_view(), name="admin-inventory"),
    path("cart-discount-settings", CartDiscountSettingsView.as_view(), name="admin-cart-discount-settings"),
    path("staff", StaffAdminView.as_view(), name="admin-staff"),
    path("advance-payments", AdvancePaymentOffersView.as_view(), name="admin-advance-payments"),
    path("advance-allocations", AdvanceAllocationAdminView.as_view(), name="admin-advance-allocations"),
    path("allocations", AllocationManagementView.as_view(), name="admin-allocations"),
    path("allocations/<int:allocation_id>", AllocationManagementView.as_view(), name="admin-allocation-detail"),
    path("locations", LocationAdminView.as_view(), name="admin-locations"),
    path("targets", TargetAdminView.as_view(), name="admin-targets"),
    path("targets/assignments", TargetAssignmentAdminView.as_view(), name="admin-target-assignments"),
]
