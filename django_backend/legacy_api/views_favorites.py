"""Flutter favourites endpoints ported from Host/api/fav.php and favpage.php."""
from django.db import transaction

from .common import as_dict, base_url, legacy_image_url, execute, fetchall, fetchone, get_int, jr, json_body, legacy_view


@legacy_view()
def fav(request):
    if request.method != "POST":
        return jr({"status": "error", "message": "Only POST method allowed"}, 405)
    data = as_dict(json_body(request))
    if "product_id" not in data:
        return jr({"status": "error", "message": "product_id required"}, 400)
    try:
        product_id = int(data["product_id"])
    except (TypeError, ValueError):
        product_id = 0
    if product_id <= 0:
        return jr({"status": "error", "message": "Valid product_id required"}, 400)

    username = request.legacy_user["username"]
    with transaction.atomic():
        existing = fetchone(
            "SELECT id FROM zg_favorites WHERE user_id = %s AND product_id = %s LIMIT 1",
            [username, product_id],
        )
        if existing:
            execute("DELETE FROM zg_favorites WHERE user_id = %s AND product_id = %s", [username, product_id])
            fav_status, message = "removed", "Product removed from favourites"
        else:
            execute("INSERT INTO zg_favorites (user_id, product_id, created_at) VALUES (%s, %s, NOW())",
                    [username, product_id])
            fav_status, message = "added", "Product added to favourites"
    return jr({"status": "success", "message": message, "fav_status": fav_status, "product_id": product_id})


@legacy_view()
def favpage(request):
    skip = max(0, get_int(request, "skip", 0))
    limit = get_int(request, "limit", 30)
    if limit <= 0:
        limit = 30
    limit = min(limit, 100)
    username = request.legacy_user["username"]
    rows = fetchall(
        "SELECT p.product_id, p.product_name, p.product_price, p.discount_percent, "
        "COALESCE((SELECT image_path FROM zg_product_images WHERE product_id=p.product_id AND main='1' LIMIT 1), "
        "(SELECT image_path FROM zg_product_images WHERE product_id=p.product_id LIMIT 1)) AS image_path "
        "FROM zg_favorites f INNER JOIN zg_product p ON f.product_id=p.product_id "
        "WHERE f.user_id=%s ORDER BY f.created_at DESC LIMIT %s OFFSET %s",
        [username, limit, skip],
    )
    items = [{
        "id": int(row["product_id"]),
        "product_name": row["product_name"] or "Unknown",
        "image_url": legacy_image_url(row["image_path"], request, "https://projects.teleber.com/stokit/pro-imgs/default.jpg"),
        "price": float(row["product_price"] or 0),
        "fav": "Y",
        "discount": float(row["discount_percent"] or 0),
    } for row in rows]
    total_row = fetchone("SELECT COUNT(*) AS total FROM zg_favorites WHERE user_id=%s", [username])
    return jr({"fav": items, "total": int(total_row["total"] if total_row else 0), "skip": skip, "limit": limit})
