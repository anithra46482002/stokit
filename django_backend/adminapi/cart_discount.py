from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError, InterfaceError
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import CartDiscountSettings
from .db_errors import log_db_error
from legacydb.discount_rules import product_has_discount
from .permissions import AdminRolePermission


CENT = Decimal("0.01")
def money(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Enter a valid monetary amount.")
    if not amount.is_finite() or amount < 0:
        raise ValueError("Amount must be finite and non-negative.")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)

def load_cart_discount_config():
    """Current persisted Cart Discount Settings (the single source of truth for the customer cart and checkout).

    Read on every call - never cached - so a change saved in the admin page applies to the next cart or order
    without a restart. There is NO hardcoded fallback: a missing row means the promotion is not configured
    (disabled, zero amounts - the same view the admin page shows), and a storage failure is logged (sanitized)
    and re-raised so the Flutter endpoints answer with their existing sanitized database-error response instead
    of applying an unconfigured discount. This never creates a row and never touches the schema.
    """
    try:
        config = CartDiscountSettings.objects.filter(pk=1).first()
    except (DatabaseError, InterfaceError) as exc:
        log_db_error("Cart Discount settings read (customer cart)", exc)
        raise
    if config is None:
        return {"enabled": False, "minimum_subtotal": Decimal("0.00"), "fixed_discount_amount": Decimal("0.00"), "configured": False}
    return {"enabled": bool(config.enabled), "minimum_subtotal": money(config.minimum_subtotal),
            "fixed_discount_amount": money(config.fixed_discount_amount), "configured": True}


def allocate_discount(amounts, discount):
    """Split `discount` over `amounts` in proportion, exact to the cent (largest remainder), never above a line."""
    amounts = [money(a) for a in amounts]
    discount, total = money(discount), sum(amounts, Decimal("0.00"))
    if discount <= 0 or total <= 0:
        return [Decimal("0.00")] * len(amounts)
    discount = min(discount, total)
    raw = [a * discount / total for a in amounts]
    shares = [r.quantize(CENT, rounding=ROUND_DOWN) for r in raw]
    leftover = int(((discount - sum(shares, Decimal("0.00"))) / CENT).to_integral_value())
    for index in sorted(range(len(amounts)), key=lambda i: raw[i] - shares[i], reverse=True)[:leftover]:
        shares[index] += CENT
    return shares


def calculate_cart_discount(lines, enabled, minimum_subtotal, fixed_discount_amount, vip_applied=False):
    """Calculate from server-derived line data; never accept client totals as authoritative.

    Lines with a product/line discount are excluded. An active customer VIP discount disables
    this cart-level promotion entirely so the two promotions cannot stack. The promotion applies only when the
    eligible subtotal is STRICTLY greater than the minimum; `line_discounts` (aligned with `lines`) splits the
    applied amount over the eligible lines so the line figures add up to the applied discount exactly once.
    """
    threshold, configured = money(minimum_subtotal), money(fixed_discount_amount)
    eligible = Decimal("0.00")
    amounts, line_ok = [], []
    for line in lines:
        amount = money(line.get("amount", 0))
        line_discount = money(line.get("line_discount", 0))
        already_discounted = bool(line.get("product_discounted", False)) or line_discount > 0 or product_has_discount(
            has_disc=line.get("has_disc", 0),
            discount_percent=line.get("discount_percent", 0),
            discount_value=line.get("discount_value", 0),
            product_discount=line.get("product_discount", 0),
        )
        amounts.append(amount)
        line_ok.append(not already_discounted)
        if not already_discounted:
            eligible += amount
    eligible = eligible.quantize(CENT, rounding=ROUND_HALF_UP)
    qualifies = bool(enabled) and not vip_applied and eligible > threshold
    applied = min(configured, eligible) if qualifies else Decimal("0.00")
    applied = applied.quantize(CENT, rounding=ROUND_HALF_UP)
    shares = allocate_discount([a if ok else Decimal("0.00") for a, ok in zip(amounts, line_ok)], applied)
    return {"eligible_subtotal": eligible, "eligible": qualifies, "configured_discount": configured,
            "applied_discount": applied, "line_discounts": shares}

def serialize(config):
    return {"enabled": config.enabled, "minimum_subtotal": str(config.minimum_subtotal), "fixed_discount_amount": str(config.fixed_discount_amount), "updated_at": config.updated_at.isoformat() if config.updated_at else None}

STORAGE_MESSAGES = {
    "table_missing": "Cart Discount settings storage is not initialized: the admin_cart_discount_settings table does not exist in the connected PostgreSQL database. An authorized developer must review and apply the approved migration to the intended development database.",
    "permission_denied": "Cart Discount settings cannot be accessed: the database role does not have permission on the admin_cart_discount_settings table. Check the database privileges.",
    "database_missing": "The configured PostgreSQL database does not exist. Check the database name in the environment configuration.",
    "authentication_failed": "The database rejected the configured credentials. Check the database user and password in the environment configuration.",
    "database_unavailable": "The database is unavailable. Check that PostgreSQL is running and that the host and port in the environment configuration are correct.",
    "database_error": "Cart Discount settings could not be processed because of an unexpected database error. See the Django server log for the error code.",
}


def storage_error_response(action, exc):
    """Log the real (sanitized) backend error and return a specific 503; same `detail` key as before."""
    category, _state = log_db_error("Cart Discount settings " + action, exc)
    detail = STORAGE_MESSAGES[category]
    if action == "save":
        detail += " No settings were confirmed saved."
    return Response({"detail": detail, "code": category}, status=503)

class CartDiscountSettingsView(APIView):
    permission_classes = [AdminRolePermission]
    required_resource = "cart_discount"

    def get(self, request):
        try:
            config = CartDiscountSettings.objects.filter(pk=1).first()
        except (DatabaseError, InterfaceError) as exc:
            return storage_error_response("read", exc)
        if config is None:
            return Response({"enabled": False, "minimum_subtotal": "0.00", "fixed_discount_amount": "0.00", "updated_at": None})
        return Response(serialize(config))

    def put(self, request):
        errors = {}
        enabled = request.data.get("enabled")
        if not isinstance(enabled, bool):
            errors["enabled"] = "Provide true or false."
        values = {}
        for field in ("minimum_subtotal", "fixed_discount_amount"):
            try: values[field] = money(request.data.get(field))
            except ValueError as exc: errors[field] = str(exc)
        if errors:
            return Response({"detail": "Invalid cart discount settings.", "errors": errors}, status=400)
        try:
            with transaction.atomic():
                config = CartDiscountSettings.objects.select_for_update().filter(pk=1).first()
                if config is None: config = CartDiscountSettings(pk=1)
                config.enabled = enabled
                config.minimum_subtotal = values["minimum_subtotal"]
                config.fixed_discount_amount = values["fixed_discount_amount"]
                config.save()
        except (DatabaseError, InterfaceError) as exc:
            return storage_error_response("save", exc)
        return Response(serialize(config))
