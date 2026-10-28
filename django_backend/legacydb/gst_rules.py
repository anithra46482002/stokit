"""Single source of truth for GST: customer percentage applied to the admin-configured GST amount.

The one formula used by the cart, the checkout preview, order placement, the order snapshot, order details,
statements and the admin order page::

    configured GST amount and customer percentage both present: unit GST amount x quantity x percentage / 100
    customer percentage blank: configured unit GST amount x quantity
    total_gst = sum(line_gst for eligible cart lines) (each line rounded half-up to cents)

Rules (documented behaviour; see also docs/STOKIT_CUSTOMER_GST_FIX.md):

* The percentage is the customer's saved ``users.gst_percentage`` (set in Customer Management). It is read from the
  database for the authenticated customer; nothing from the request is ever used.
* The amount is the admin-configured per-unit GST amount: ``zg_variant.gst_price`` for a variant line, or
  ``zg_product.gst_price`` for a product without variants (variant id 0).
* The selling price is NOT an input. ``calculate_gst_amount`` has no price parameter, so GST cannot depend on it.
  (Stored prices remain GST-exclusive list prices; GST is added once on top and never extracted from a price.)
* Eligibility: the product flag (``zg_product.gst_applicable``) must be 'Y'. A variant line also needs the variant flag
  (``zg_variant.gst``) 'Y'. A product-level 'N' always wins over a variant 'Y'. A missing/blank/other flag is 'N'.
  A configured amount alone never enables GST.
* The product-level ``zg_product.gst_percentage`` column is no longer used for any calculation.
* Blank / NULL customer percentage -> use the configured per-unit GST amount directly (100% of that amount). A saved zero is treated the same way: users.gst_percentage defaults to 0 and the schema cannot tell zero from never-configured. No statutory or hardcoded rate is invented.
* A customer percentage that is negative, non-finite (NaN/Infinity), unparseable or above 100 is treated as unusable
  and also yields zero GST (the admin screen already rejects such values; this protects against bad stored data).
* A negative configured amount disables GST for that line (fail safe).
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


def _decimal(value):
    """Decimal of `value`, or None when it is missing/blank/unparseable/non-finite."""
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount.is_finite() else None


def _flag(value):
    return str(value or "N").strip().upper() == "Y"


def customer_gst_rate(value):
    """Return a valid saved customer percentage, or zero for blank/invalid/zero values."""
    pct = _decimal(value)
    if pct is None or pct <= 0 or pct > HUNDRED:
        return ZERO
    return pct


def effective_gst_settings(*, product_gst_applicable, configured_amount=None, variant_gst='N', is_variant=False,
                           customer_gst_percentage=None):
    disabled = {'applicable': 'N', 'percentage': ZERO, 'amount': ZERO}
    # A selected variant's GST flag is authoritative; the parent product flag applies to variant_id=0 only.
    if is_variant:
        if not _flag(variant_gst):
            return disabled
    elif not _flag(product_gst_applicable):
        return disabled
    amount = _decimal(configured_amount)
    if amount is not None and amount < 0:
        return disabled
    return {'applicable': 'Y', 'percentage': customer_gst_rate(customer_gst_percentage), 'amount': amount if amount is not None else ZERO}


def calculate_gst_amount(*, quantity, product_gst_applicable, variant_gst="N", is_variant=False,
                         configured_amount=None, customer_gst_percentage=None):
    """Calculate line GST. Blank customer rate uses configured per-unit GST amount directly; explicit zero stays zero."""
    settings = effective_gst_settings(
        product_gst_applicable=product_gst_applicable, configured_amount=configured_amount,
        variant_gst=variant_gst, is_variant=is_variant, customer_gst_percentage=customer_gst_percentage)
    if settings["applicable"] != "Y":
        return ZERO
    qty_value = _decimal(quantity)
    qty = max(0, int(qty_value)) if qty_value is not None else 0
    amount = settings["amount"]
    if qty == 0 or amount <= 0:
        return ZERO
    raw_rate = _decimal(customer_gst_percentage)
    missing_rate = customer_gst_percentage is None or (isinstance(customer_gst_percentage, str) and not customer_gst_percentage.strip())
    if missing_rate or raw_rate == ZERO:
        tax = amount * qty
    elif raw_rate is None or raw_rate < 0 or raw_rate > HUNDRED:
        return ZERO
    else:
        tax = amount * qty * raw_rate / HUNDRED
    return tax.quantize(CENT, rounding=ROUND_HALF_UP)


def validate_gst_configuration(*, percentage=None, amount=None):
    """Admin-side validation of saved values. Returns an error message, or None when acceptable."""
    pct, amt = _decimal(percentage), _decimal(amount)
    if percentage not in (None, "") and pct is None:
        return "GST percentage must be a finite number."
    if amount not in (None, "") and amt is None:
        return "GST amount must be a finite number."
    if pct is not None and (pct < 0 or pct > HUNDRED):
        return "GST percentage must be between 0 and 100."
    if amt is not None and amt < 0:
        return "GST amount cannot be negative."
    return None
