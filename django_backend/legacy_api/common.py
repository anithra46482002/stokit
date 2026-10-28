"""Helpers that keep the Flutter-facing views byte-compatible with the PHP originals."""
import functools
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import Error as DatabaseLayerError
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from accounts import services

# Exact body the PHP token.php returns (HTTP 401) for a missing/unknown/revoked/expired token.
SESSION_EXPIRED = {"status": "session_expired", "message": "Session expired"}
# Sanitised body for a database failure: never echoes driver text, SQL, hosts, credentials or tracebacks.
SERVER_ERROR = {"status": "error", "message": "Internal server error"}

logger = logging.getLogger("legacy_api")


class LegacyEncoder(DjangoJSONEncoder):
    """Decimal -> number, datetime -> 'YYYY-MM-DD HH:MM:SS' (what PHP/mysqli printed)."""

    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, datetime):
            return o.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(o, date):
            return o.strftime("%Y-%m-%d")
        return super().default(o)


def jr(data, status=200):
    return JsonResponse(
        data, status=status, safe=False, encoder=LegacyEncoder,
        json_dumps_params={"ensure_ascii": False},
        content_type="application/json; charset=UTF-8",
    )


def json_body(request):
    """json_decode(php://input, true): parsed value, or None when empty/invalid."""
    try:
        return json.loads(request.body.decode("utf-8")) if request.body else None
    except (ValueError, UnicodeDecodeError):
        return None


def as_dict(v):
    return v if isinstance(v, dict) else {}


def php_int(v, default=0):
    """PHP (int) cast: leading integer of a string, 0 otherwise."""
    if v is None:
        return default
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float, Decimal)):
        return int(v)
    m = re.match(r"\s*[+-]?\d+", str(v))
    return int(m.group()) if m else 0


def php_float(v, default=0.0):
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        m = re.match(r"\s*[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?", str(v))
        return float(m.group()) if m else 0.0


def php_round(x, nd=2):
    """PHP round(): half away from zero (Python's round() is banker's rounding)."""
    d = Decimal(repr(float(x)))
    q = Decimal(1).scaleb(-nd)
    return float(d.quantize(q, rounding="ROUND_HALF_UP" if d >= 0 else "ROUND_HALF_DOWN"))


def get_int(request, name, default):
    return php_int(request.GET[name]) if name in request.GET else default


def base_url():
    return settings.LEGACY_BASE_URL


def legacy_image_url(path, request=None, fallback=""):
    """Absolute image URL for a stored image path, shared by every Flutter-facing endpoint.

    Local uploads (MEDIA_ROOT/uploads, when SERVE_LOCAL_UPLOADS is on) are served by this backend over the
    request's scheme/host; absolute URLs are kept as is (never prefixed again); anything not stored locally keeps
    the legacy LEGACY_BASE_URL + path contract. An empty/NULL path returns `fallback` (each endpoint keeps the
    empty value Flutter already receives from it).
    """
    value = str(path or "").strip()
    if not value:
        return fallback
    from adminapi.image_urls import image_url as _resolve, legacy_url
    return _resolve(value, request) or legacy_url(value) or fallback


# ---- raw SQL (PostgreSQL dialect; legacy MySQL-only syntax and implicit string/number coercion were converted explicitly) ----
def fetchall(sql, params=()):
    with connection.cursor() as c:
        c.execute(sql, params)
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, r)) for r in c.fetchall()]


def fetchone(sql, params=()):
    rows = fetchall(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    with connection.cursor() as c:
        c.execute(sql, params)
        return c.rowcount


def lock_user_cart(username):
    """Serialise cart writes of one user for the rest of the current transaction.

    a_cart has no uniqueness constraint on (username, product_id, variant_id) and the schema must not change,
    so two simultaneous Add taps (or an Add racing a quantity change) could otherwise both see "no line yet"
    and insert duplicates, which later makes quantity/remove act on the wrong rows. Must be called inside
    transaction.atomic(); the lock is released automatically on commit/rollback.
    """
    fetchone("SELECT pg_advisory_xact_lock(hashtext(%s)) AS locked", ["a_cart:" + str(username)])


def legacy_view(auth=True):
    """csrf-exempt + legacy bearer auth. Auth runs BEFORE any method check (as in PHP)."""

    def deco(fn):
        @csrf_exempt
        @functools.wraps(fn)
        def wrapper(request, *args, **kwargs):
            try:
                if auth:
                    token = services.parse_bearer(request.META.get("HTTP_AUTHORIZATION", ""))
                    found = services.authenticate_token(token)
                    if found is None:
                        return jr(SESSION_EXPIRED, 401)
                    request.legacy_session, request.legacy_user = found
                return fn(request, *args, **kwargs)
            except DatabaseLayerError as exc:
                # Log only the exception class: driver messages can contain SQL, hosts or credentials.
                # A database outage is a 500, never a 401 (the client would discard a valid session).
                logger.error("Database error in %s: %s", fn.__name__, type(exc).__name__)
                return jr(SERVER_ERROR, 500)

        return wrapper

    return deco
