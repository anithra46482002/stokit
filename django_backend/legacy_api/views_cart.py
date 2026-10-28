"""Cart mutation endpoint ported from Host/api/cart_action.php."""
from django.db import transaction

from .common import as_dict, execute, fetchall, jr, json_body, legacy_view, lock_user_cart
from .views_commerce import MAX_CART_QTY

ACTIONS = ("increase", "decrease", "remove")
AMBIGUOUS_MESSAGE = "Cart item is ambiguous; refresh the cart and try again."


def _line_product(lines, product_hint):
    """Pick the product of the one cart line a request means.

    `lines` are the caller's a_cart rows for the requested variant_id. Variant ids of real variants are
    unique to one product, so there is normally a single product. Products without variant rows are carted
    as variant 0, which many products share; then the product_id sent by Flutter must pick the line.
    Returns (product_id, None), (None, None) when nothing matches, or (None, error_message) when several
    products match and the request cannot say which one (nothing may be touched in that case).
    """
    products = []
    for line in lines:
        pid = int(line["product_id"] or 0)
        if pid not in products:
            products.append(pid)
    if not products:
        return None, None
    if len(products) == 1:
        return products[0], None
    if product_hint in products:
        return product_hint, None
    return None, AMBIGUOUS_MESSAGE


@legacy_view()
def cart_action(request):
    if request.method != "POST":
        return jr({"status": False, "message": "Only POST method allowed"}, 405)
    username = (request.legacy_user.get("username") or "").strip()
    if not username:
        return jr({"status": False, "message": "Invalid user."})
    data = as_dict(json_body(request))
    action = str(data.get("action") or "").strip()
    # variant_id 0 is valid: products without variant rows are carted as variant 0 (see product_api_cart).
    try:
        variant_id = int(data["variant_id"]) if data.get("variant_id") is not None else -1
    except (TypeError, ValueError):
        variant_id = -1
    if not action or variant_id < 0:
        return jr({"status": False, "message": "action and variant_id are required"})
    if action not in ACTIONS:
        return jr({"status": False, "message": "Invalid action."})
    # Flutter sends the key of the cart group it rendered as product_id. It is only a hint used to tell
    # apart several products that share variant 0; the product that is changed always comes from the database.
    product_hint = 0
    if data.get("product_id") is not None:
        try:
            product_hint = int(data["product_id"])
        except (TypeError, ValueError):
            return jr({"status": False, "message": "Invalid product_id."})

    with transaction.atomic():
        lock_user_cart(username)
        lines = fetchall("SELECT product_id, qty FROM a_cart WHERE username=%s AND variant_id=%s "
                         "ORDER BY id FOR UPDATE", [username, variant_id])
        product_id, problem = _line_product(lines, product_hint)
        if problem:
            return jr({"status": False, "message": problem})
        if product_id is None:
            if action == "decrease":
                return jr({"status": False, "message": "Product not found in cart."})
            # Legacy behaviour: increase/remove of a line that is not in the cart changes nothing.
            return jr({"status": True, "affected_rows": 0, "message": "Cart updated successfully."})

        where, params = "username=%s AND variant_id=%s AND product_id=%s", [username, variant_id, product_id]
        qty = next(int(line["qty"] or 0) for line in lines if int(line["product_id"] or 0) == product_id)
        if action == "increase":
            affected = execute(f"UPDATE a_cart SET qty=LEAST(qty+1, %s) WHERE {where}", [MAX_CART_QTY] + params)
        elif action == "decrease":
            if qty <= 1:
                affected = execute(f"DELETE FROM a_cart WHERE {where}", params)
            else:
                affected = execute(f"UPDATE a_cart SET qty=qty-1 WHERE {where}", params)
        else:
            affected = execute(f"DELETE FROM a_cart WHERE {where}", params)
    return jr({"status": True, "affected_rows": affected, "message": "Cart updated successfully."})
