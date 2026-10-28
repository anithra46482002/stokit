from rest_framework.exceptions import ParseError
from rest_framework.permissions import BasePermission


def require_object_body(request):
    """Reject write requests whose JSON body is not an object (e.g. `[1, 2]` or `"x"`).

    Every admin view reads `request.data` as a mapping; a list/string body used to raise AttributeError -> HTTP 500.
    Malformed JSON already raises ParseError (400) when `request.data` is first read.
    """
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    data = getattr(request, "data", None)  # real DRF requests always have .data; bare test doubles may not
    if data is not None and not hasattr(data, "get"):
        raise ParseError("Request body must be a JSON object.")

ROLE_RESOURCES = {
    'SUPER_ADMIN': {'*'},
    'ADMIN': {'dashboard','catalogue','customers','orders','banners','notifications','advance_payments','reports','targets','locations','warehouse','inventory','staff','cart_discount'},
    'SALESMAN': {'dashboard','customers','orders','reports'},
    'WAREHOUSE_STAFF': {'dashboard','catalogue','warehouse','inventory','orders'},
    'DELIVERY_BOY': {'dashboard','orders'},
}

class AdminRolePermission(BasePermission):
    message = 'An active administrator role assignment is required for this operation.'

    def has_permission(self, request, view):
        allowed = self._role_allows(request, view)
        if allowed:
            require_object_body(request)
        return allowed

    def _role_allows(self, request, view):
        user = request.user
        if not getattr(user, 'is_authenticated', False):
            return False
        role = getattr(user, 'role', None)
        resource = getattr(view, 'required_resource', 'dashboard')
        if not role or role not in ROLE_RESOURCES:
            return False
        allowed = ROLE_RESOURCES[role]
        if resource not in allowed and '*' not in allowed:
            return False
        if resource == 'cart_discount' and request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return role in {'SUPER_ADMIN', 'ADMIN'}
        if request.method == 'DELETE':
            return role in {'SUPER_ADMIN','ADMIN'} and resource in {'catalogue','customers','banners','notifications','warehouse','staff','advance_payments','targets','locations'}
        if request.method == 'POST':
            return role in {'SUPER_ADMIN','ADMIN'} and resource in {'catalogue','customers','orders','banners','notifications','warehouse','staff','advance_payments','targets','locations'}
        if request.method in ('PUT','PATCH'):
            update_roles = {
                'dashboard': {'SUPER_ADMIN'},
                'catalogue': {'SUPER_ADMIN','ADMIN'},
                'customers': {'SUPER_ADMIN','ADMIN','SALESMAN'},
                'orders': {'SUPER_ADMIN','ADMIN','SALESMAN','WAREHOUSE_STAFF','DELIVERY_BOY'},
                'banners': {'SUPER_ADMIN','ADMIN'}, 'notifications': {'SUPER_ADMIN','ADMIN'},
                'advance_payments': {'SUPER_ADMIN','ADMIN'}, 'reports': {'SUPER_ADMIN','ADMIN'},
                'targets': {'SUPER_ADMIN','ADMIN'}, 'locations': {'SUPER_ADMIN','ADMIN'}, 'warehouse': {'SUPER_ADMIN','ADMIN'},
                'inventory': {'SUPER_ADMIN','ADMIN','WAREHOUSE_STAFF'},
                'staff': {'SUPER_ADMIN','ADMIN'}, 'cart_discount': {'SUPER_ADMIN','ADMIN'},
            }
            return role in update_roles.get(resource, set())
        return True
