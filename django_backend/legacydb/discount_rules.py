"""Pure cart-discount eligibility rules shared by the Flutter API and the admin API.

Rule (enforced on the server; client-supplied totals are never trusted):
  * A cart (order) discount may only be applied to lines that carry NO other discount.
  * A line carries another discount when its product has any positive product-level discount
    (has_disc / discount_percent / discount_value / product_discount) or, for stored order lines,
    when the line discount is positive.
  * A customer with an active VIP discount already receives a discount on the whole order, so the
    cart discount is not applied at all for that customer (no stacking).
No database access happens here, so the rules are unit-testable without a database.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")


def _num(value):
    try:
        number = Decimal(str(value if value is not None else 0))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
    return number if number.is_finite() else Decimal("0")


def product_has_discount(has_disc=0, discount_percent=0, discount_value=0, product_discount=0):
    """True when the product carries any product-level discount.

    The legacy schema stores a discount in several columns (has_disc flag, discount_percent,
    discount_value and the catalogue column product_discount). Any positive value counts, so a
    product is never made eligible for the cart discount just because one flag is unset.
    """
    flag = str(has_disc or "").strip().upper()
    flag_active = flag in {"Y", "YES", "TRUE", "ON"} or _num(has_disc) > 0
    return flag_active or any(_num(v) > 0 for v in (discount_percent, discount_value, product_discount))


def customer_has_vip(vip_discount, vip_percentage):
    """True when the customer has an active VIP discount (flag 'Y' and a positive percentage)."""
    return str(vip_discount or "").strip().upper() == "Y" and _num(vip_percentage) > 0


def cart_discount_amount(eligible_subtotal, percent, vip_applied=False):
    """Cart discount on the subtotal of discount-free lines; 0 when a VIP discount applies."""
    eligible, pct = _num(eligible_subtotal), _num(percent)
    if vip_applied or eligible <= 0 or pct <= 0:
        return Decimal("0.00")
    return (eligible * pct / 100).quantize(CENT, rounding=ROUND_HALF_UP)
