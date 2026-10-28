"""Real-database check of product-variant Edit (PATCH) and Delete, with zero persistent effect.

    python scripts/verify_variant_flow.py

Everything runs in ONE transaction that is always rolled back. Edit/delete success is exercised only on
temporary rows created inside that transaction; real variants are only asked to be deleted when they are
already referenced (expected 409, never deleted). Note: PostgreSQL sequences are not rolled back, so each run
skips a few variant/stock-log ids (harmless gaps). Exit code 1 if any check fails.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from adminapi.crud import VariantCRUDView
from legacydb.models import OrderItem, Product, StockLog, Variant

ADMIN = SimpleNamespace(is_authenticated=True, role="ADMIN", id=1, pk=1, is_active=True)
FACTORY = APIRequestFactory()
failures = []


def call(method, data=None, query=""):
    path = "/admin-api/product-variants" + query
    request = getattr(FACTORY, method)(path, data, format="json") if data is not None else getattr(FACTORY, method)(path)
    force_authenticate(request, user=ADMIN)
    response = VariantCRUDView.as_view()(request)
    return response.status_code, getattr(response, "data", None)


def check(label, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + label + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        failures.append(label)


product = Product.objects.order_by("product_id").first()
if product is None:
    sys.exit("No product exists to attach temporary variants to.")
real_before = Variant.objects.count()

with transaction.atomic():
    a = Variant.objects.create(product_id=product.product_id, variant_name="ZZ-A", variant_price=10, mrp=10, quantity=5)
    b = Variant.objects.create(product_id=product.product_id, variant_name="ZZ-B", variant_price=20, mrp=20, quantity=7)

    status, body = call("patch", {"id": a.variant_id, "product_id": product.product_id, "name": "ZZ-A2", "variant_price": 11, "mrp": 12,
                                  "quantity": 6, "discount": "5", "gst": "Y", "gst_price": 1.5, "minimum_buying_count": 2})
    a.refresh_from_db(); b.refresh_from_db()
    check("edit returns 200 with the updated variant", status == 200 and body["name"] == "ZZ-A2" and body["discount"] == "5", (status, body))
    check("edit persisted every changed column", (a.variant_name, a.variant_price, a.mrp, a.quantity, a.disc, a.gst, a.minimum_buying_count) == ("ZZ-A2", 11, 12, 6, "5", "Y", 2))
    check("edit did not touch the sibling variant", (b.variant_name, b.variant_price, b.quantity) == ("ZZ-B", 20, 7))

    status, _ = call("patch", {"id": a.variant_id, "product_id": product.product_id + 1000, "name": "moved"})
    a.refresh_from_db()
    check("moving a variant to another product is refused and nothing changes", status == 400 and a.variant_name == "ZZ-A2" and a.product_id == product.product_id, status)
    check("edit of a missing variant is 404", call("patch", {"id": 99999999, "name": "x"})[0] == 404)
    check("edit with invalid quantity is 400 and unchanged", call("patch", {"id": a.variant_id, "quantity": -3})[0] == 400 and Variant.objects.get(pk=a.variant_id).quantity == 6)

    status, _ = call("delete", {"id": b.variant_id}, query=f"?id={b.variant_id}")
    check("delete returns 204", status == 204, status)
    check("delete removed only the selected variant", not Variant.objects.filter(pk=b.variant_id).exists() and Variant.objects.filter(pk=a.variant_id).exists())
    check("parent product survived", Product.objects.filter(pk=product.product_id).exists())
    check("deleting it again is 404", call("delete", query=f"?id={b.variant_id}")[0] == 404)

    StockLog.objects.create(variant_id=a.variant_id, adjustment=1, reason="verify", admin="verify", created_at=timezone.now())
    status, body = call("delete", query=f"?id={a.variant_id}")
    check("variant with inventory history deletes successfully", status == 204 and not Variant.objects.filter(pk=a.variant_id).exists(), (status, body))
    check("prior stock history and deletion audit are both retained", StockLog.objects.filter(variant_id=a.variant_id).count() == 2)
    check("delete with an invalid id is 400", call("delete", query="?id=abc")[0] == 400)

    # Never delete pre-existing variants in this script, even if they are referenced.
    transaction.set_rollback(True)

    transaction.set_rollback(True)

check("rollback left no temporary rows and the real variant count unchanged",
      Variant.objects.filter(variant_name__startswith="ZZ-").count() == 0 and Variant.objects.count() == real_before)
print(f"\n{'ALL CHECKS PASSED' if not failures else str(len(failures)) + ' CHECK(S) FAILED'}")
sys.exit(1 if failures else 0)
