"""Order management endpoints for the React admin, reproducing the legacy PHP pages
(admin/manage/order.php and admin/manage/order_details.php) against the existing tables.

Legacy business rules are kept in ONE place (`FIN`) so they are visible and testable.
No schema changes are made; optional columns (e.g. zg_checkout.grand_total) are only written when present.
"""
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.db import connection, transaction
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .image_urls import image_url as _resolve_image_url
from .permissions import ROLE_RESOURCES, require_object_body

from .finance import build_order_summary_query
from .bonus_credit import preview_customer_bonus, release_and_deduct_for_confirmed_order
from legacydb.discount_rules import customer_has_vip
from legacydb.gst_rules import calculate_gst_amount
from legacydb import order_gst_snapshot as _gst_snapshot
from legacydb.monthly_credit import ORDER_REFERENCE_TYPE
from legacydb.order_gst_snapshot import order_gst

D = Decimal
CENT = D("0.01")

# The cart promotion is a FIXED amount chosen by the saved Cart Discount Settings at the moment the order was placed.
# It is never re-derived here from a percentage: order display and order edits read what checkout persisted
# (zg_checkout.total_amount, see stored_cart_discount). GST and VIP rates come from saved product/customer configuration.
FIN = {
    "credit_release": D("0"),          # customer bonus is computed from the active allocation
}

# How the cart discount of an order was established (response key items.cart_discount_source).
DISCOUNT_STORED = "stored_difference"        # items total minus the persisted post-discount total
DISCOUNT_NONE = "none"                       # persisted total equals the items total: no cart discount
DISCOUNT_NO_TOTAL = "no_recorded_total"      # legacy row without a usable total_amount: nothing to infer from
DISCOUNT_ABOVE_ITEMS = "stored_above_items"  # persisted total exceeds the items total (edited/legacy): preserved
DISCOUNT_UNRELIABLE = "unreliable_preserved" # difference larger than any eligible line could carry: preserved

# Status values offered by the legacy status dropdown (stored lower-case, exactly as the PHP form posted them).
STATUS_OPTIONS = [
    ("Placed", "Placed"), ("processing", "Processing"), ("await_pickup", "Awaiting Pickup"), ("picked_up", "Picked Up"),
    ("shipped", "Shipped"), ("delivered", "Delivered"), ("failed", "Delivery Failed"),
    ("cancelled", "Cancelled"), ("pending", "Pending"),
]
ALL_STATUS_VALUES = {value for value, _ in STATUS_OPTIONS}
# Legacy PHP had no per-role limits. Admin/Super Admin may set any status; other roles are limited to
# the statuses that match their job (same intent as the existing /orders PATCH role matrix).
ROLE_STATUS_LIMITS = {
    "SALESMAN": {"processing"},
    "WAREHOUSE_STAFF": {"processing", "await_pickup", "picked_up", "shipped"},
    "DELIVERY_BOY": {"delivered", "failed"},
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def money(value):
    return str(D(value).quantize(CENT, rounding=ROUND_HALF_UP))


def to_dec(value, default="0"):
    try:
        return D(str(value)) if value not in (None, "") else D(default)
    except (InvalidOperation, ValueError):
        return D(default)


def _rows(cursor):
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _has_column(table, column):
    with connection.cursor() as cursor:
        return any(col.name == column for col in connection.introspection.get_table_description(cursor, table))


class OrderActionPermission(BasePermission):
    """GET: any role that may see orders. Writes: roles listed in the view's `write_roles` (default admins)."""
    message = "Your role cannot perform this order operation."

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return False
        role = getattr(user, "role", None)
        if role not in ROLE_RESOURCES:
            return False
        allowed = ROLE_RESOURCES[role]
        if "orders" not in allowed and "*" not in allowed:
            return False
        if request.method in SAFE_METHODS:
            return True
        if role not in getattr(view, "write_roles", {"SUPER_ADMIN", "ADMIN"}):
            return False
        require_object_body(request)
        return True


def _filters(params, *, default_today):
    """Build the WHERE clause shared by the list and the statistics (same filters as order.php)."""
    where, args = [], []
    from_date, to_date = params.get("from_date", "").strip(), params.get("to_date", "").strip()
    for label, value in (("from_date", from_date), ("to_date", to_date)):
        if value:
            try:
                datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                raise ValueError(f'{label} must be a real date in YYYY-MM-DD format')
    explicit_date_range = bool(from_date or to_date)
    if from_date:
        where.append("c.order_date >= %s"); args.append(from_date + " 00:00:00")
    elif default_today and not explicit_date_range:
        where.append("c.order_date >= CURRENT_DATE")
    if to_date:
        where.append('c.order_date < %s'); args.append((datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d 00:00:00'))
    elif default_today and not explicit_date_range:
        where.append('c.order_date < CURRENT_DATE + INTERVAL ' + chr(39) + '1 day' + chr(39))
    status = params.get("status", "all").strip()
    if status and status.lower() != "all":
        where.append("c.status = %s"); args.append(status)
    color = params.get("color_code", "").strip()
    if color:
        where.append("u.color_code = %s"); args.append(color)
    warehouse = params.get("warehouse_id", "").strip()
    if warehouse:
        if not warehouse.isdigit() or int(warehouse) <= 0:
            raise ValueError("warehouse_id must be a positive integer")
        where.append("u.warehouse_id = %s"); args.append(int(warehouse))
    delivery_boy = params.get("delivery_boy_id", "").strip()
    if delivery_boy:
        if not delivery_boy.isdigit() or int(delivery_boy) <= 0:
            raise ValueError("delivery_boy_id must be a positive integer")
        where.append("c.delivery_boy_id = %s"); args.append(int(delivery_boy))
    return (" WHERE " + " AND ".join(where)) if where else "", args


class OrderManageView(APIView):
    """GET /admin-api/orders/manage - the order.php page: filtered list + statistics + dropdown data."""
    permission_classes = [OrderActionPermission]

    def get(self, request):
        try:
            list_where, list_args = _filters(request.query_params, default_today=False)
            stat_where, stat_args = _filters(request.query_params, default_today=True)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        ranged = bool(request.query_params.get("from_date") or request.query_params.get("to_date"))
        base = "FROM zg_checkout c LEFT JOIN users u ON c.email = u.email"
        with connection.cursor() as cursor:
            # DISTINCT keeps one row per order even if several user rows share an e-mail address.
            cursor.execute(
                "SELECT DISTINCT c.order_id, c.full_name, c.email, c.order_date, c.total_amount, c.payment_method, c.status, "
                "c.delivery_boy_id, (SELECT COUNT(*) FROM zg_order_items i WHERE i.order_id = c.order_id) AS item_count "
                + base + list_where + " ORDER BY c.order_date DESC, c.order_id DESC", list_args)
            orders = _rows(cursor)
            payables = _list_payables(cursor, orders)
            summary_sql, summary_status_args = build_order_summary_query(base, stat_where)
            cursor.execute(summary_sql, [*summary_status_args, *stat_args])
            stats = _rows(cursor)[0]
            cursor.execute('SELECT id, fullname FROM delivery_boys ORDER BY fullname')
            boys = _rows(cursor)
            cursor.execute('SELECT DISTINCT color_code FROM users WHERE color_code IS NOT NULL AND LENGTH(color_code) > 0 ORDER BY color_code')
            colors = [r[0] for r in cursor.fetchall()]
            cursor.execute('SELECT DISTINCT warehouse_id FROM users WHERE warehouse_id IS NOT NULL ORDER BY warehouse_id')
            warehouses = [r[0] for r in cursor.fetchall()]
            cursor.execute('SELECT DISTINCT status FROM zg_checkout WHERE status IS NOT NULL AND LENGTH(status) > 0 ORDER BY status')
            statuses = [r[0] for r in cursor.fetchall()]
        boy_names = {b["id"]: b["fullname"] for b in boys}
        return Response({
            "count": len(orders),
            "ranged": ranged,
            "stats": {"total_orders": int(stats["total_orders"] or 0), "revenue": money(stats["revenue"] or 0),
                      "pending_orders": int(stats["pending_orders"] or 0)},
            "filters": {"color_codes": colors, "warehouses": warehouses, "statuses": statuses},
            "delivery_boys": boys,
            "orders": [{
                "id": o["order_id"], "order_date": o["order_date"], "customer": o["full_name"],
                "items": o["item_count"] or 1, "total_amount": money(o["total_amount"] or 0),
                # total_amount stays the stored subtotal after cart discount (same key, same meaning). The final payable
                # amount is exposed additively, from persisted rows, by the same shared summary Order Details uses.
                "subtotal_after_discount": money(o["total_amount"] or 0),
                "payable_amount": payables.get(int(o["order_id"]), {}).get("payable_amount"),
                "credit_recorded": payables.get(int(o["order_id"]), {}).get("credit_recorded", False),
                "payment_method": o["payment_method"], "status": o["status"],
                "delivery_boy_id": o["delivery_boy_id"], "delivery_boy_name": boy_names.get(o["delivery_boy_id"]),
            } for o in orders],
        })


class OrderBulkAssignView(APIView):
    """POST /admin-api/orders/bulk-assign {order_ids:[...], delivery_boy_id} (order.php bulk action)."""
    permission_classes = [OrderActionPermission]

    def post(self, request):
        ids = request.data.get("order_ids")
        try:
            boy_id = int(request.data.get("delivery_boy_id"))
            order_ids = sorted({int(i) for i in ids}) if isinstance(ids, list) else []
        except (TypeError, ValueError):
            return Response({"detail": "Please select at least one order and a delivery boy."}, status=400)
        if not order_ids or boy_id <= 0:
            return Response({"detail": "Please select at least one order and a delivery boy."}, status=400)
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM delivery_boys WHERE id = %s", [boy_id])
            if cursor.fetchone() is None:
                return Response({"detail": "Selected delivery boy does not exist."}, status=400)
            marks = ",".join(["%s"] * len(order_ids))
            cursor.execute(f"UPDATE zg_checkout SET delivery_boy_id = %s WHERE order_id IN ({marks})", [boy_id, *order_ids])
        return Response({"assigned": len(order_ids),
                         "message": f"Delivery boy assigned to {len(order_ids)} order(s) successfully."})


def _image_url(path, request=None):
    # Shared resolver: serves local uploads from this backend, falls back to the legacy host.
    return _resolve_image_url(path, request) or ""



def _split_items(items):
    """(discounted subtotal, plain subtotal, product-discount total) from stored order lines.

    A line with a positive stored discount is a product-level discount line. total_price is the line total AFTER
    that product discount and BEFORE any cart discount (order_post stores it that way).
    """
    disc_sub = plain_sub = product_discount = D("0")
    for item in items:
        total = to_dec(item.get("total_price"))
        discount = to_dec(item.get("discount"))
        if discount > 0:
            disc_sub += total
            product_discount += discount
        else:
            plain_sub += total
    return disc_sub, plain_sub, product_discount


def stored_cart_discount(items, stored_total):
    """(cart discount, subtotal after cart discount, source) for ONE persisted order. Pure; never writes.

    stored_total is zg_checkout.total_amount, which order_post writes as items total minus the fixed cart discount
    (before GST, delivery, VIP and credit). The cart discount is the difference, and it is inferred only when that is
    reliable: the difference must be positive and no larger than the lines that carry no product discount (the only
    lines the promotion may apply to). In every other case the stored total is kept as the subtotal and NO discount is
    invented. Today's Cart Discount Settings are deliberately not consulted: they describe today's promotion, not the
    one this order was placed under.
    """
    disc_sub, plain_sub, _ = _split_items(items)
    gross = disc_sub + plain_sub
    total = None if stored_total in (None, "") else to_dec(stored_total, "0")
    if total is None or (total <= 0 and gross > 0):
        return D("0.00"), gross.quantize(CENT, rounding=ROUND_HALF_UP), DISCOUNT_NO_TOTAL
    total = total.quantize(CENT, rounding=ROUND_HALF_UP)
    diff = (gross - total).quantize(CENT, rounding=ROUND_HALF_UP)
    if gross <= 0 or diff == 0:
        return D("0.00"), total, DISCOUNT_NONE
    if diff < 0:
        return D("0.00"), total, DISCOUNT_ABOVE_ITEMS
    if diff > plain_sub:
        return D("0.00"), total, DISCOUNT_UNRELIABLE
    return diff, total, DISCOUNT_STORED


def recorded_total_after_edit(old_items, old_total, new_items):
    """New zg_checkout.total_amount after an admin line edit, or None to leave the stored amount untouched.

    The fixed promotion amount the order was placed with is preserved (never recomputed from a percentage or from
    today's settings). It is capped at the lines that can carry it. When the original discount cannot be established
    reliably the stored amount is preserved: None is returned and nothing is invented.
    """
    discount, _subtotal, source = stored_cart_discount(old_items, old_total)
    if source not in (DISCOUNT_STORED, DISCOUNT_NONE):
        return None
    disc_sub, plain_sub, _ = _split_items(new_items)
    kept = min(discount, plain_sub)
    return max(D("0"), disc_sub + plain_sub - kept).quantize(CENT, rounding=ROUND_HALF_UP)


def order_financial_summary(items, stored_total, gst_amount, delivery, vip_pct, preview_bonus):
    """Every figure of the Order Details financial summary, from PERSISTED values. Pure apart from preview_bonus.

    * subtotal after cart discount = the persisted order total (same figure the All Orders list shows);
    * cart discount = fixed amount inferred by stored_cart_discount, counted once;
    * checkout never stacks the cart promotion with a VIP discount (calculate_cart_discount), so when the order
      carries a cart discount no VIP discount is shown for it;
    * GST is the stored/snapshot amount passed in, delivery is counted once, credit comes from preview_bonus
      (the ledger when the order already has a recorded deduction).
    """
    disc_sub, plain_sub, product_discount = _split_items(items)
    cart_disc, subtotal, source = stored_cart_discount(items, stored_total)
    vip_pct = D("0") if cart_disc > 0 else D(vip_pct)
    vip = (subtotal * vip_pct / 100).quantize(CENT, rounding=ROUND_HALF_UP)  # same rounding as order_post
    amount_before_bonus = max(D("0"), subtotal + gst_amount + delivery - vip)
    bonus = preview_bonus(amount_before_bonus)
    return {"disc_sub": disc_sub, "plain_sub": plain_sub, "product_discount": product_discount,
            "gross": disc_sub + plain_sub, "original_items_subtotal": disc_sub + plain_sub + product_discount,
            "cart_discount": cart_disc, "cart_discount_source": source, "subtotal": subtotal,
            "vip_pct": vip_pct, "vip": vip, "amount_before_bonus": amount_before_bonus, "bonus": bonus,
            "bonus_is_recorded": bonus.get("credit_status") == "already_applied"}


# GST sources from which a final payable amount may be derived: the order-time snapshot, or (only while the database has no
# snapshot columns at all) the shared GST rule, which is what checkout used. legacy_unrecorded / partial_snapshot mean GST is
# genuinely missing for a snapshot-era order: never reliable, and never counted as zero.
PAYABLE_GST_BASIS = {_gst_snapshot.SOURCE_SNAPSHOT: "gst_snapshot", _gst_snapshot.SOURCE_PRE_MIGRATION: "gst_current_settings"}


def payable_inputs_reliable(gst_source, discount_source):
    """True when GST and the cart discount are both established from recorded data (credit is checked by the caller)."""
    return gst_source in PAYABLE_GST_BASIS and discount_source in (DISCOUNT_STORED, DISCOUNT_NONE)


def _pre_snapshot_line_gst(item, gst_config, customer_gst_percentage):
    """GST of one order line by the shared GST rule, for databases that have no per-order GST snapshot yet.

    Same call Order Details makes for the pre-snapshot case; the list reuses it so both views derive one figure."""
    return calculate_gst_amount(
        quantity=item.get("quantity"),
        product_gst_applicable=gst_config.get("product_gst_applicable"),
        variant_gst=gst_config.get("variant_gst"),
        is_variant=int(item.get("variant_id") or 0) != 0,
        configured_amount=gst_config.get("configured_amount"),
        customer_gst_percentage=customer_gst_percentage,
    )


def _list_payables(cursor, orders):
    """{order_id: {"payable_amount", "credit_recorded"}} for the All Orders rows. Read-only; never writes.

    zg_checkout.total_amount is the subtotal after cart discount, so the list cannot show the final payable amount from
    that column. It is derived from persisted rows (GST, customer delivery/VIP settings and the recorded credit ledger
    row) through order_financial_summary, the SAME shared calculation Order Details uses, so one order shows one figure in
    both places. The GST comes from the stored snapshot when the database has the snapshot columns, otherwise from the
    shared GST rule (the established pre-snapshot behaviour). Orders whose GST or cart discount cannot be established
    reliably are omitted: the caller then keeps the stored subtotal and never gets an invented amount.
    credit_recorded is False when no ledger deduction exists yet (the amount is then before monthly credit).
    """
    if not orders:
        return {}
    snapshot = _gst_snapshot.snapshot_available()
    ids = [int(o["order_id"]) for o in orders]
    lines = {}
    if snapshot:
        cursor.execute("SELECT order_id, discount, total_price, gst_amount FROM zg_order_items WHERE order_id = ANY(%s)", [ids])
        for oid, discount, total_price, gst_amount in cursor.fetchall():
            lines.setdefault(int(oid), []).append({"discount": discount, "total_price": total_price, "snap_gst_amount": gst_amount})
    else:
        cursor.execute("SELECT order_id, discount, total_price, product_id, variant_id, quantity FROM zg_order_items WHERE order_id = ANY(%s)", [ids])
        for oid, discount, total_price, product_id, variant_id, quantity in cursor.fetchall():
            lines.setdefault(int(oid), []).append({"discount": discount, "total_price": total_price, "snap_gst_amount": None,
                                                   "product_id": product_id, "variant_id": variant_id, "quantity": quantity})
    products, variants = {}, {}
    if not snapshot:
        product_ids = sorted({int(l["product_id"]) for ls in lines.values() for l in ls if l.get("product_id") is not None})
        variant_ids = sorted({int(l["variant_id"]) for ls in lines.values() for l in ls if int(l.get("variant_id") or 0) != 0})
        if product_ids:
            cursor.execute("SELECT product_id, gst_applicable, gst_price FROM zg_product WHERE product_id = ANY(%s)", [product_ids])
            products = {int(r[0]): (r[1], r[2]) for r in cursor.fetchall()}
        if variant_ids:
            cursor.execute("SELECT variant_id, product_id, gst, gst_price FROM zg_variant WHERE variant_id = ANY(%s)", [variant_ids])
            variants = {(int(r[0]), int(r[1])): (r[2], r[3]) for r in cursor.fetchall()}
    cursor.execute(
        "SELECT reference_id, SUM(amount) FROM advance_pay_transactions WHERE reference_type = %s "
        "AND UPPER(transaction_type) = 'CREDIT_USED' AND reference_id IS NOT NULL AND reference_id::text = ANY(%s) "
        "GROUP BY reference_id", [ORDER_REFERENCE_TYPE, [str(i) for i in ids]])
    credit = {int(r[0]): to_dec(r[1]) for r in cursor.fetchall()}
    emails = sorted({o["email"] for o in orders if o.get("email")})
    users = {}
    if emails:
        cursor.execute("SELECT email, delivery_charges, vip_discount, vip_percentage, gst_percentage FROM users WHERE email = ANY(%s) ORDER BY id", [emails])
        for email, delivery_charges, vip_discount, vip_percentage, gst_percentage in cursor.fetchall():
            users.setdefault(email, (delivery_charges, vip_discount, vip_percentage, gst_percentage))
    out = {}
    for o in orders:
        oid = int(o["order_id"])
        delivery_charges, vip_discount, vip_percentage, gst_percentage = users.get(o.get("email"), (None, None, None, None))
        vip_pct = to_dec(vip_percentage) if customer_has_vip(vip_discount, vip_percentage) else D("0")

        def line_gst(row, customer_pct=gst_percentage):
            product_id, variant_id = int(row["product_id"]), int(row.get("variant_id") or 0)
            product_gst, product_amount = products.get(product_id, (None, None))
            variant_gst, variant_amount = variants.get((variant_id, product_id), (None, None)) if variant_id else (None, None)
            config = {"product_gst_applicable": product_gst, "variant_gst": variant_gst if variant_gst is not None else "N",
                      "configured_amount": (product_amount if variant_id == 0 else variant_amount) or 0}
            return _pre_snapshot_line_gst(row, config, customer_pct)

        gst_amount, gst_source = order_gst(lines.get(oid, []), line_gst)
        applied = credit.get(oid)

        def recorded_credit(amount, applied=applied):
            deducted = min(applied, amount) if applied is not None else D("0")
            return {"amount_payable": max(D("0"), amount - deducted), "credit_status": "already_applied" if applied is not None else "not_recorded"}

        summary = order_financial_summary(lines.get(oid, []), o.get("total_amount"), gst_amount, to_dec(delivery_charges), vip_pct, recorded_credit)
        # Same reliability rule as Order Details (payable_is_reliable): otherwise no payable is reported for the order.
        if not payable_inputs_reliable(gst_source, summary["cart_discount_source"]):
            continue
        out[oid] = {"payable_amount": money(summary["bonus"]["amount_payable"]), "credit_recorded": applied is not None}
    return out


def _build_detail(order_id, request=None):

    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM zg_checkout WHERE order_id = %s", [order_id])
        found = _rows(cursor)
        if not found:
            return None
        order = found[0]
        cursor.execute("SELECT username, warehouse_id, city, gst_percentage, delivery_charges, latitude, longitude, vip_discount, vip_percentage "
                       "FROM users WHERE email = %s LIMIT 1", [order["email"]])
        u = (_rows(cursor) or [{}])[0]
        warehouse = None
        if u.get("warehouse_id"):
            cursor.execute("SELECT * FROM zg_warehouse WHERE warehouse_id = %s", [u["warehouse_id"]])
            warehouse = (_rows(cursor) or [None])[0]
        if not warehouse and u.get("city"):
            cursor.execute("SELECT * FROM zg_warehouse WHERE place = %s LIMIT 1", [u["city"]])
            warehouse = (_rows(cursor) or [None])[0]
        cursor.execute("SELECT * FROM zg_order_items WHERE order_id = %s ORDER BY item_id", [order_id])
        raw_items = _rows(cursor)
        def _recalc_pre_snapshot(item):
            # Used ONLY before the snapshot columns exist (pre-migration); never for a snapshot-era order.
            cursor.execute(
                "SELECT p.gst_applicable AS product_gst_applicable, "
                "CASE WHEN %s = 0 THEN COALESCE(p.gst_price, 0) ELSE COALESCE(v.gst_price, 0) END AS configured_amount, "
                "COALESCE(v.gst, 'N') AS variant_gst FROM zg_product p "
                "LEFT JOIN zg_variant v ON v.variant_id = %s AND v.product_id = p.product_id "
                "WHERE p.product_id = %s LIMIT 1",
                [int(item.get("variant_id") or 0), int(item.get("variant_id") or 0), item["product_id"]],
            )
            gst_config = (_rows(cursor) or [{}])[0]
            return calculate_gst_amount(
                quantity=item.get("quantity"),
                product_gst_applicable=gst_config.get("product_gst_applicable"),
                variant_gst=gst_config.get("variant_gst"),
                is_variant=int(item.get("variant_id") or 0) != 0,
                configured_amount=gst_config.get("configured_amount"),
                customer_gst_percentage=u.get("gst_percentage"),
            )

        for item in raw_items:
            cursor.execute("SELECT image_path FROM zg_product_images WHERE product_id = %s AND main = '1' LIMIT 1",
                           [str(item["product_id"])])
            img = cursor.fetchone()
            item["image_path"] = img[0] if img else ""
            item["snap_gst_amount"] = item.get("gst_amount")  # stored order-time GST (SELECT * includes it once migrated)
        gst_amount, gst_source = order_gst(raw_items, _recalc_pre_snapshot)
        cursor.execute("SELECT status, changed_at, message FROM zg_order_status_history WHERE order_id = %s "
                       "ORDER BY changed_at DESC, id DESC", [order_id])
        history = _rows(cursor)
        cursor.execute("SELECT id, fullname FROM delivery_boys ORDER BY fullname")
        boys = _rows(cursor)

    discounted = [i for i in raw_items if to_dec(i["discount"]) > 0]
    plain = [i for i in raw_items if to_dec(i["discount"]) <= 0]
    billed_pct = to_dec(u.get("gst_percentage"))
    delivery = to_dec(u.get("delivery_charges"))
    current_vip_pct = to_dec(u.get("vip_percentage")) if customer_has_vip(u.get("vip_discount"), u.get("vip_percentage")) else D("0")
    # Persisted values only: the recorded order total is the subtotal after the (fixed) cart discount.
    summary = order_financial_summary(
        raw_items, order.get("total_amount"), gst_amount, delivery, current_vip_pct,
        lambda amount: preview_customer_bonus(order.get("email"), amount, order_id=order_id))
    disc_sub, plain_sub = summary["disc_sub"], summary["plain_sub"]
    cart_disc, subtotal, vip_pct, vip = summary["cart_discount"], summary["subtotal"], summary["vip_pct"], summary["vip"]
    amount_before_bonus, bonus = summary["amount_before_bonus"], summary["bonus"]
    gst_pct = (gst_amount / subtotal * 100) if subtotal > 0 else D("0")  # derived ratio of GST to subtotal, not a rate
    grand = bonus["amount_payable"]
    # The final payable amount is shown as the recorded order amount ONLY when every input is recorded data: a GST snapshot on
    # every line, a cart discount established from the stored total, and no credit that is still just a preview.
    # Otherwise nothing is invented: the stored subtotal is kept and the page says the payable cannot be reconstructed.
    payable_reliable = (payable_inputs_reliable(gst_source, summary["cart_discount_source"])
                        and (to_dec(bonus.get("bonus_applied")) == 0 or summary["bonus_is_recorded"]))
    stored_subtotal = to_dec(order["total_amount"] or 0)
    recorded_amount = grand if payable_reliable else stored_subtotal
    if payable_reliable:
        fallback_reason = ""
    elif gst_source not in PAYABLE_GST_BASIS:
        fallback_reason = "GST was not recorded for every line of this order."
    elif summary["cart_discount_source"] not in (DISCOUNT_STORED, DISCOUNT_NONE):
        fallback_reason = "The cart discount cannot be established from the stored total of this order."
    else:
        fallback_reason = "The monthly credit for this order is not recorded yet."

    def item_out(i):
        return {"id": i["item_id"], "product_id": i["product_id"], "product_name": i["product_name"],
                "variant_name": i["variant_name"], "image_url": _image_url(i["image_path"], request),
                "price": money(i["price"]), "quantity": i["quantity"], "discount": money(i["discount"]),
                "total_price": money(i["total_price"])}

    boy_name = next((b["fullname"] for b in boys if b["id"] == order["delivery_boy_id"]), None)
    wh = warehouse or {}
    order_out = {k: order[k] for k in ("order_id", "full_name", "email", "phone", "address", "city", "state",
                                       "postal_code", "country", "order_date", "status", "payment_method")}
    order_out.update({"delivery_boy_id": order["delivery_boy_id"], "delivery_boy_name": boy_name,
                      "total_amount": money(order["total_amount"] or 0)})
    return {
        "order": order_out,
        "customer": {"username": u.get("username") or "", "billed_percentage": str(billed_pct.normalize() if billed_pct else 0)},
        "warehouse": {"name": wh.get("warehouse_name") or "", "address": wh.get("address") or "", "pincode": wh.get("pincode") or "",
                      "state": wh.get("state") or "", "place": wh.get("place") or "",
                      "latitude": str(wh["latitude"]) if wh.get("latitude") is not None else "",
                      "longitude": str(wh["longitude"]) if wh.get("longitude") is not None else ""},
        "customer_location": {"latitude": u.get("latitude") or "", "longitude": u.get("longitude") or ""},
        "financials": {"subtotal": money(subtotal), "gst_percentage": money(gst_pct), "gst_amount": money(gst_amount), "gst_source": gst_source,
                       "total_with_gst": money(subtotal + gst_amount), "delivery_charges": money(delivery),
                       "amount_before_bonus": money(amount_before_bonus), "credit_release": money(bonus["bonus_applied"]),
                       "monthly_bonus": money(bonus["monthly_bonus"]), "carried_forward_bonus": money(bonus["carried_forward"]),
                       "available_bonus": money(bonus["available_bonus"]), "remaining_bonus": money(bonus["remaining_bonus"]),
                       "bonus_credit_status": bonus["credit_status"], "amount_payable": money(bonus["amount_payable"]),
                       "vip_discount_percent": money(vip_pct), "vip_discount": money(vip),
                       "vip_not_applied_reason": "cart_discount_applied" if cart_disc > 0 and current_vip_pct > 0 else "",
                       "grand_total": money(grand),
                       # Additive keys: original items total, product discount, the fixed cart discount amount and the
                       # persisted order amount, so the page can show each figure once without recomputing anything.
                       "original_items_subtotal": money(summary["original_items_subtotal"]),
                       "product_discount": money(summary["product_discount"]),
                       "items_subtotal_before_cart_discount": money(summary["gross"]),
                       "cart_discount": money(cart_disc), "cart_discount_type": "fixed" if cart_disc > 0 else "none",
                       "cart_discount_source": summary["cart_discount_source"],
                       "recorded_order_amount": money(recorded_amount),
                       "stored_subtotal_after_discount": money(stored_subtotal),
                       "payable_reliably_derived": payable_reliable,
                       "payable_gst_basis": PAYABLE_GST_BASIS.get(gst_source, "gst_not_recorded"),
                       "payable_fallback_reason": fallback_reason,
                       # zg_checkout.total_amount is the subtotal after cart discount (order_post), NOT the payable amount.
                       "recorded_order_amount_meaning": "derived_payable_amount" if payable_reliable else "subtotal_after_cart_discount",
                       "final_payable_amount": money(grand),
                       "bonus_is_recorded": summary["bonus_is_recorded"]},
        "items": {"discounted": [item_out(i) for i in discounted], "discounted_subtotal": money(disc_sub),
                  "non_discounted": [item_out(i) for i in plain], "non_discounted_subtotal": money(plain_sub),
                  # cart_discount_percent is kept (always 0.00) so the response shape stays stable: the promotion is a
                  # fixed amount, never a percentage.
                  "cart_discount_percent": money(0), "cart_discount": money(cart_disc),
                  "cart_discount_type": "fixed" if cart_disc > 0 else "none",
                  "cart_discount_source": summary["cart_discount_source"],
                  "non_discounted_after_discount": money(plain_sub - cart_disc)},
        "history": [{"status": h["status"], "changed_at": h["changed_at"], "message": h["message"] or ""} for h in history],
        "delivery_boys": boys,
        "status_options": [{"value": v, "label": label} for v, label in STATUS_OPTIONS]
        + ([{"value": order["status"], "label": str(order["status"])}]
           if order["status"] and order["status"] not in ALL_STATUS_VALUES else []),
    }


class OrderDetailView(APIView):
    """GET / PATCH (edit order) / DELETE for one order (order_details.php)."""
    permission_classes = [OrderActionPermission]

    def get(self, request, order_id):
        data = _build_detail(order_id, request)
        if data is None:
            return Response({"detail": "Order not found."}, status=404)
        return Response(data)

    def patch(self, request, order_id):
        body = request.data
        limits = {"full_name": 255, "email": 255, "phone": 20, "address": 255, "city": 100, "state": 100,
                  "postal_code": 20, "country": 100}
        values = {}
        for field, max_len in limits.items():
            value = str(body.get(field, "")).strip()
            if len(value) > max_len:
                return Response({field: f"Must be at most {max_len} characters."}, status=400)
            values[field] = value
        if not values["full_name"]:
            return Response({"full_name": "Required."}, status=400)
        if values["email"] and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", values["email"]):
            return Response({"email": "Enter a valid e-mail address."}, status=400)
        items = body.get("items", [])
        if not isinstance(items, list):
            return Response({"items": "Must be a list."}, status=400)
        parsed = []
        for entry in items:
            try:
                item_id = int(entry["item_id"]); qty = D(str(entry["quantity"]))
                price = D(str(entry["price"])); discount = D(str(entry.get("discount", 0)))
            except (KeyError, TypeError, ValueError, InvalidOperation):
                return Response({"items": "Each item needs item_id, quantity, price and discount."}, status=400)
            if qty < 0 or qty != qty.to_integral_value() or price < 0 or discount < 0:
                return Response({"items": "Quantity must be a whole number; price and discount cannot be negative."}, status=400)
            total = price * qty - discount
            if total < 0:
                return Response({"items": f"Discount for item {item_id} exceeds its line total."}, status=400)
            parsed.append((item_id, int(qty), price, discount, total))
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM zg_checkout WHERE order_id = %s FOR UPDATE", [order_id])
            if cursor.fetchone() is None:
                return Response({"detail": "Order not found."}, status=404)
            # The row is locked above. Read the amount and lines as they were BEFORE this edit: the promotion the order
            # was placed with is established from them (never from a percentage or from today's settings).
            cursor.execute("SELECT total_amount FROM zg_checkout WHERE order_id = %s", [order_id])
            old_total = cursor.fetchone()[0]
            cursor.execute("SELECT item_id, discount, total_price FROM zg_order_items WHERE order_id = %s", [order_id])
            old_rows = cursor.fetchall()
            owned = {r[0] for r in old_rows}
            old_lines = [{"discount": r[1], "total_price": r[2]} for r in old_rows]
            if any(p[0] not in owned for p in parsed):
                return Response({"items": "An item does not belong to this order."}, status=400)
            cursor.execute(
                "UPDATE zg_checkout SET full_name=%s, email=%s, phone=%s, address=%s, city=%s, state=%s, postal_code=%s, country=%s "
                "WHERE order_id=%s", [*[values[k] for k in limits], order_id])
            for item_id, qty, price, discount, total in parsed:
                cursor.execute("UPDATE zg_order_items SET quantity=%s, price=%s, discount=%s, total_price=%s "
                               "WHERE item_id=%s AND order_id=%s", [qty, price, discount, total, item_id, order_id])
            total_preserved = False
            if parsed:
                cursor.execute("SELECT discount, total_price FROM zg_order_items WHERE order_id = %s", [order_id])
                new_lines = [{"discount": d, "total_price": t} for d, t in cursor.fetchall()]
                new_total = recorded_total_after_edit(old_lines, old_total, new_lines)
                if new_total is None:
                    # The original cart discount cannot be established reliably: keep the stored amount as it is.
                    total_preserved = True
                elif to_dec(old_total) != new_total:
                    cursor.execute("UPDATE zg_checkout SET total_amount=%s WHERE order_id=%s", [new_total, order_id])
        # The legacy PHP also stored grand_total, but only when that column exists in the schema.
        if parsed and _has_column("zg_checkout", "grand_total"):
            detail = _build_detail(order_id)
            with connection.cursor() as cursor:
                cursor.execute("UPDATE zg_checkout SET grand_total=%s WHERE order_id=%s", [detail["financials"]["grand_total"], order_id])
        data = _build_detail(order_id, request)
        if total_preserved:
            data["recorded_total_notice"] = ("The recorded order amount was kept as stored: the original cart discount "
                                             "of this order cannot be established reliably from its saved records.")
        return Response(data)

    def delete(self, request, order_id):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM zg_checkout WHERE order_id = %s FOR UPDATE", [order_id])
            if cursor.fetchone() is None:
                return Response({"detail": "Order not found."}, status=404)
            cursor.execute("DELETE FROM zg_order_status_history WHERE order_id = %s", [order_id])
            cursor.execute("DELETE FROM zg_order_items WHERE order_id = %s", [order_id])
            cursor.execute("DELETE FROM zg_checkout WHERE order_id = %s", [order_id])
        return Response(status=204)


class OrderStatusView(APIView):
    """POST /admin-api/orders/<id>/status {status, status_message, delivery_boy_id} (order_details.php update_status)."""
    permission_classes = [OrderActionPermission]
    write_roles = {"SUPER_ADMIN", "ADMIN", "SALESMAN", "WAREHOUSE_STAFF", "DELIVERY_BOY"}

    def post(self, request, order_id):
        role = getattr(request.user, "role", None)
        new_status = str(request.data.get("status", "")).strip()
        # Flutter writes capitalised values ("Placed", "Cancelled"); compare case-insensitively, store as sent.
        if new_status.lower() not in {v.lower() for v in ALL_STATUS_VALUES}:
            return Response({"status": "Choose one of: " + ", ".join(sorted(ALL_STATUS_VALUES))}, status=400)
        if role in ROLE_STATUS_LIMITS and new_status.lower() not in ROLE_STATUS_LIMITS[role]:
            return Response({"status": "This role cannot set the requested order status."}, status=403)
        message = str(request.data.get("status_message", "") or "")[:2000]
        boy_supplied = "delivery_boy_id" in request.data
        raw_boy = request.data.get("delivery_boy_id")
        boy_id = None
        if raw_boy not in (None, "", 0, "0"):
            try:
                boy_id = int(raw_boy)
            except (TypeError, ValueError):
                return Response({"delivery_boy_id": "Invalid delivery boy."}, status=400)
        can_assign = role in {"SUPER_ADMIN", "ADMIN"} and boy_supplied
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT delivery_boy_id, status, email FROM zg_checkout WHERE order_id = %s FOR UPDATE", [order_id])
            current_order = cursor.fetchone()
            if current_order is None:
                return Response({"detail": "Order not found."}, status=404)
            previous_status, order_email = str(current_order[1] or "").strip().lower(), current_order[2]
            if boy_id is not None:
                cursor.execute("SELECT 1 FROM delivery_boys WHERE id = %s", [boy_id])
                if cursor.fetchone() is None:
                    return Response({"delivery_boy_id": "Selected delivery boy does not exist."}, status=400)
            if can_assign:
                cursor.execute("UPDATE zg_checkout SET status=%s, delivery_boy_id=%s WHERE order_id=%s", [new_status, boy_id, order_id])
            else:  # non-admin roles change the status only; they never reassign or clear the delivery boy
                cursor.execute("UPDATE zg_checkout SET status=%s WHERE order_id=%s", [new_status, order_id])

            # Credit is normally deducted when the customer places the order (legacy_api.views_orders). Here the
            # shared service finds that ledger row and returns it unchanged, so confirmation never deducts a
            # second time; it only deducts for older unconfirmed orders that were placed before that change.
            bonus_result = None
            if role in {"SUPER_ADMIN", "ADMIN"} and new_status.lower() == "processing" and previous_status != "processing":
                detail_before = _build_detail(order_id)
                amount_before_bonus = to_dec((detail_before or {}).get("financials", {}).get("amount_before_bonus"))
                cursor.execute("SELECT 1 FROM zg_order_status_history WHERE order_id = %s AND LOWER(TRIM(status)) = 'processing' LIMIT 1", [order_id])
                first_confirmation = cursor.fetchone() is None
                bonus_result = release_and_deduct_for_confirmed_order(cursor, order_id, order_email, amount_before_bonus, allow_new=first_confirmation)
                if bonus_result is not None:
                    payable = money(bonus_result["amount_payable"])
                    if _has_column("zg_checkout", "grand_total"):
                        cursor.execute("UPDATE zg_checkout SET grand_total=%s WHERE order_id=%s", [payable, order_id])
                    message = (message + " | " if message else "") + (
                        f"Bonus applied: ₹{money(bonus_result['bonus_applied'])}; payable: ₹{payable}; "
                        f"remaining bonus: ₹{money(bonus_result['remaining_bonus'])}"
                    )
            cursor.execute("INSERT INTO zg_order_status_history (order_id, status, changed_at, message) VALUES (%s, %s, NOW(), %s)",
                           [order_id, new_status, message])
        response = _build_detail(order_id, request)
        if bonus_result is not None:
            response["credit_release"] = {key: money(value) if isinstance(value, Decimal) else value
                                          for key, value in bonus_result.items()}
            response["credit_release"]["message"] = (
                f"Bonus credit applied: ₹{money(bonus_result['bonus_applied'])}. "
                f"Amount payable: ₹{money(bonus_result['amount_payable'])}. "
                f"Remaining bonus balance: ₹{money(bonus_result['remaining_bonus'])}."
            )
        return Response(response)
