from django.conf import settings
from django.core import signing
from django.db import OperationalError, ProgrammingError
from django.db.models import Count, Sum
from django.db.models.functions import Lower, Trim
from .finance import REVENUE_STATUS_KEYS
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.hashers import verify_php_password
from legacydb.models import AdminAccount, Category, Checkout, LegacyUser, OrderItem, Product, Salesman, DeliveryBoy, Variant
from accounts.models import AdminRoleAssignment
from .permissions import AdminRolePermission
from .auth import active_admin_role
from .db_errors import log_db_error


REVENUE_STATUSES = REVENUE_STATUS_KEYS
LOW_STOCK_THRESHOLD = 5


class AdminLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))
        if not username or not password:
            return Response({"success": False, "message": "Username and password are required."}, status=400)
        try:
            account = AdminAccount.objects.filter(username=username).first()
            principal_type = 'ADMIN'
            if account is None:
                account = Salesman.objects.filter(username=username).first()
                principal_type = 'SALESMAN'
            if account is None:
                account = DeliveryBoy.objects.filter(username=username).first()
                principal_type = 'DELIVERY_BOY'
        except (OperationalError, ProgrammingError) as exc:
            # Keep the failure explicit: a missing relation is a provisioning blocker, not a bad password.
            category, _ = log_db_error('Admin login lookup', exc)
            if category == 'table_missing':
                code = 'schema_not_provisioned'
                message = 'The configured PostgreSQL schema is missing a required admin-authentication table. Contact the database administrator.'
            elif category == 'database_unavailable':
                code = 'database_unavailable'
                message = 'The configured PostgreSQL database is unavailable.'
            elif category == 'permission_denied':
                code = 'database_permission_denied'
                message = 'The configured PostgreSQL role cannot read the admin-authentication tables.'
            else:
                code = 'admin_database_error'
                message = 'Admin login could not query the configured PostgreSQL schema.'
            return Response({'success': False, 'code': code, 'message': message}, status=503)
        if not account or not verify_php_password(password, account.password):
            return Response({"success": False, "message": "Invalid username or password."}, status=401)
        try:
            # Do not issue a successful login response unless the role store can be queried.
            # A missing role table or unavailable database is an infrastructure failure, not
            # a successful authentication session.
            role = active_admin_role(principal_type, account.pk, raise_on_error=True)
        except (OperationalError, ProgrammingError) as exc:
            category, _ = log_db_error('Admin login role lookup', exc)
            if category == 'table_missing':
                code = 'schema_not_provisioned'
                message = 'The configured PostgreSQL schema is missing a required admin-authentication table. Contact the database administrator.'
            elif category == 'database_unavailable':
                code = 'database_unavailable'
                message = 'The configured PostgreSQL database is unavailable.'
            elif category == 'permission_denied':
                code = 'database_permission_denied'
                message = 'The configured PostgreSQL role cannot read the admin-authentication tables.'
            else:
                code = 'admin_database_error'
                message = 'Admin login could not query the configured PostgreSQL schema.'
            return Response({'success': False, 'code': code, 'message': message}, status=503)
        if role is None:
            return Response({
                'success': False,
                'code': 'admin_role_not_configured',
                'message': 'This account has no active admin role assignment. Contact an administrator.',
            }, status=403)
        if principal_type == 'ADMIN':
            token = signing.dumps({'admin_id': account.pk}, salt='stokit.admin-token')
        else:
            token = signing.dumps({'principal_type': principal_type, 'principal_id': account.pk}, salt='stokit.admin-token')
        return Response({'success': True, 'token': token, 'user': {
            'id': account.pk, 'username': account.username, 'email': account.email,
            'fullname': account.fullname, 'role': role, 'principal_type': principal_type,
            'permissions_configured': role is not None,
        }})


class DashboardView(APIView):
    required_resource = "dashboard"
    permission_classes = [AdminRolePermission]

    def get(self, request):
        revenue = Checkout.objects.annotate(_normalized_status=Lower(Trim('status'))).filter(_normalized_status__in=REVENUE_STATUSES).aggregate(total=Sum('total_amount'))['total'] or 0
        # Normalize historical case/whitespace; only completed orders count as revenue.
        low_variants = list(Variant.objects.filter(quantity__lte=LOW_STOCK_THRESHOLD).order_by("quantity", "variant_id")[:10])
        product_names = dict(Product.objects.filter(pk__in=[v.product_id for v in low_variants]).values_list("pk", "product_name"))
        return Response({
            "customers": LegacyUser.objects.count(),
            "products": Product.objects.count(),
            "categories": Category.objects.count(),
            "orders": Checkout.objects.count(),
            "revenue": str(revenue),
            "low_stock_threshold": LOW_STOCK_THRESHOLD,
            "orders_by_status": list(Checkout.objects.values("status").annotate(count=Count("order_id")).order_by("status")),
            "recent_orders": list(Checkout.objects.order_by("-order_date").values(
                "order_id", "full_name", "email", "total_amount", "status", "order_date"
            )[:5]),
            "low_stock": [
                {"variant_id": v.variant_id, "product": product_names.get(v.product_id, ""), "variant": v.variant_name, "stock": v.quantity}
                for v in low_variants
            ],
        })


class CategoryListView(APIView):
    required_resource = "catalogue"
    permission_classes = [AdminRolePermission]

    def get(self, request):
        qs = Category.objects.order_by("category_name")
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(category_name__icontains=search)
        page = max(1, int(request.query_params.get("page", 1) or 1))
        size = min(100, max(1, int(request.query_params.get("page_size", 20) or 20)))
        total = qs.count()
        rows = qs[(page - 1) * size:page * size]
        return Response({"count": total, "page": page, "page_size": size, "results": [
            {"id": x.category_id, "name": x.category_name, "image": x.category_image, "active": x.category_active}
            for x in rows
        ]})


class ProductListView(APIView):
    required_resource = "catalogue"
    permission_classes = [AdminRolePermission]

    def get(self, request):
        qs = Product.objects.order_by("-product_id")
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(product_name__icontains=search)
        if request.query_params.get("category_id"):
            qs = qs.filter(category_id=request.query_params["category_id"])
        page = max(1, int(request.query_params.get("page", 1) or 1))
        size = min(100, max(1, int(request.query_params.get("page_size", 20) or 20)))
        total = qs.count()
        rows = qs[(page - 1) * size:page * size]
        return Response({"count": total, "page": page, "page_size": size, "results": [
            {"id": x.product_id, "name": x.product_name, "code": x.code, "price": x.product_price,
             "mrp": x.mrp, "discount": x.product_discount, "category_id": x.category_id,
             "subcategory_id": x.subcategory_id, "visible": x.view, "highlight": x.highlight}
            for x in rows
        ]})


class CustomerListView(APIView):
    required_resource = "customers"
    permission_classes = [AdminRolePermission]

    def get(self, request):
        qs = LegacyUser.objects.order_by("-id")
        search = request.query_params.get("search", "").strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(username__icontains=search) | Q(fullname__icontains=search) | Q(email__icontains=search) | Q(shop_name__icontains=search))
        page = max(1, int(request.query_params.get("page", 1) or 1))
        size = min(100, max(1, int(request.query_params.get("page_size", 20) or 20)))
        total = qs.count()
        rows = qs[(page - 1) * size:page * size]
        return Response({"count": total, "page": page, "page_size": size, "results": [
            {"id": x.id, "username": x.username, "full_name": x.fullname, "email": x.email,
             "phone": x.phone, "shop_name": x.shop_name, "status": x.status, "city": x.city}
            for x in rows
        ]})


class OrderListView(APIView):
    required_resource = "orders"
    permission_classes = [AdminRolePermission]

    def get(self, request):
        qs = Checkout.objects.order_by("-order_date")
        search = request.query_params.get("search", "").strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(full_name__icontains=search) | Q(email__icontains=search) | Q(status__icontains=search) | Q(phone__icontains=search))
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        page = max(1, int(request.query_params.get("page", 1) or 1))
        size = min(100, max(1, int(request.query_params.get("page_size", 20) or 20)))
        total = qs.count()
        rows = qs[(page - 1) * size:page * size]
        return Response({"count": total, "page": page, "page_size": size, "results": [
            {"id": x.order_id, "customer": x.full_name, "email": x.email, "phone": x.phone,
             "total_amount": x.total_amount, "status": x.status, "order_date": x.order_date,
             "payment_method": x.payment_method}
            for x in rows
        ]})


class AdminRefreshView(APIView):
    """POST /admin-api/auth/refresh: exchange a still-valid admin token for a fresh one.

    Tokens are stateless signed values (no server-side revocation list), so there is no server-side
    logout: the React app discards the token. Account existence and role are re-checked on every
    request by AdminTokenAuthentication, so removing an account or role takes effect immediately.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.principal_type == 'ADMIN':
            payload = {'admin_id': user.pk}
        else:
            payload = {'principal_type': user.principal_type, 'principal_id': user.pk}
        return Response({'success': True, 'token': signing.dumps(payload, salt='stokit.admin-token')})
