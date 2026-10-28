"""Per-order-item GST snapshot: GST is frozen when an order is created and never recomputed afterwards.

Deployment ordering (see docs/STOKIT_GST_SNAPSHOT_MIGRATION_PROPOSAL.md):
  * Until the reviewed migration adds the five snapshot columns to zg_order_items, `snapshot_available()` is False.
    New orders are written exactly as before and order displays keep their previous (pre-snapshot) behaviour, so this
    code can be deployed before the migration without changing any total.
  * Once the columns exist, every new order stores its GST breakdown (computed by the central gst_rules service),
    and every display reads the stored snapshot. Current product/variant settings are never consulted again.

Legacy policy for orders created before the snapshot (columns NULL): their original GST cannot be established from
the historical records, so it is NOT invented and NOT recomputed from today's settings. The line contributes 0 to the
displayed GST total and the response reports gst_source = "legacy_unrecorded" so the gap is explicit, not silent.
"""
from decimal import Decimal, InvalidOperation

from django.db import connection

from .gst_rules import CENT, ZERO, calculate_gst_amount, effective_gst_settings

SNAPSHOT_COLUMNS = ("gst_applicable", "gst_percentage", "gst_unit_amount", "gst_amount", "gst_snapshot_at")

SOURCE_SNAPSHOT = "snapshot"
SOURCE_LEGACY = "legacy_unrecorded"
SOURCE_PARTIAL = "partial_snapshot"
SOURCE_PRE_MIGRATION = "current_settings_pre_snapshot"

_available = False


def snapshot_available():
    """True once all snapshot columns exist on zg_order_items. A positive answer is cached; failures are not."""
    global _available
    if _available:
        return True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = current_schema() "
                "AND table_name = 'zg_order_items' AND column_name = ANY(%s)", [list(SNAPSHOT_COLUMNS)])
            present = int(cursor.fetchone()[0]) == len(SNAPSHOT_COLUMNS)
    except Exception:
        return False
    if present:
        _available = True
    return present


def line_snapshot(*, quantity, product_gst_applicable, variant_gst="N", is_variant=False,
                  customer_gst_percentage=None, configured_amount=None):
    """The GST breakdown to store for one order line, from the central rule service (never from the client).

    gst_percentage = the customer's saved percentage used at order time, gst_unit_amount = the configured per-unit
    GST amount used, gst_amount = the calculated line GST (configured amount x quantity x percentage / 100).
    """
    settings = effective_gst_settings(
        product_gst_applicable=product_gst_applicable, configured_amount=configured_amount,
        variant_gst=variant_gst, is_variant=is_variant, customer_gst_percentage=customer_gst_percentage)
    amount = calculate_gst_amount(
        quantity=quantity, product_gst_applicable=product_gst_applicable,
        variant_gst=variant_gst, is_variant=is_variant, configured_amount=configured_amount,
        customer_gst_percentage=customer_gst_percentage)
    return {"gst_applicable": settings["applicable"], "gst_percentage": settings["percentage"],
            "gst_unit_amount": settings["amount"], "gst_amount": amount}


def insert_clause(snapshot):
    """(extra column list SQL, extra placeholders SQL, extra params) for the zg_order_items INSERT."""
    return (",gst_applicable,gst_percentage,gst_unit_amount,gst_amount,gst_snapshot_at", ",%s,%s,%s,%s,CURRENT_TIMESTAMP",
            [snapshot["gst_applicable"], snapshot["gst_percentage"], snapshot["gst_unit_amount"], snapshot["gst_amount"]])


def select_fragment(alias="oi"):
    """SELECT-list fragment exposing the stored line GST as snap_gst_amount (NULL when unrecorded/unavailable)."""
    if snapshot_available():
        return f"{alias}.gst_amount AS snap_gst_amount"
    return "NULL AS snap_gst_amount"


def _money(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def order_gst(rows, recalc_pre_snapshot):
    """(total GST Decimal, gst_source) for one order's item rows.

    `rows` carry snap_gst_amount (see select_fragment). `recalc_pre_snapshot(row)` is used ONLY while the snapshot
    columns do not exist yet (before the approved migration); it is never used for a snapshot-era order.
    """
    rows = list(rows)
    if not snapshot_available():
        return sum((recalc_pre_snapshot(r) for r in rows), ZERO), SOURCE_PRE_MIGRATION
    total, missing = ZERO, 0
    for row in rows:
        stored = _money(row.get("snap_gst_amount"))
        if stored is None:
            missing += 1
        else:
            total += stored
    source = SOURCE_SNAPSHOT if missing == 0 else (SOURCE_LEGACY if missing == len(rows) else SOURCE_PARTIAL)
    return total.quantize(CENT), source
