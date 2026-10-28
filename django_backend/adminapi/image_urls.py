"""Single source of truth for turning a stored image value into a public URL.

Every API (Flutter-facing `legacy_api` and React-facing `adminapi`) must use `image_url` so that
absolute URLs, legacy relative paths, duplicated `admin/manage/` prefixes, spaces and Windows paths
are handled in exactly one place.
"""
import re
from urllib.parse import quote, unquote

from django.conf import settings

_WINDOWS_PATH = re.compile(r"^[a-zA-Z]:[\\/]")
_STRIP_PREFIXES = ("admin/manage/", "manage/")
# Characters left untouched when re-encoding an already-absolute URL (keeps existing %XX escapes).
_URL_SAFE = "%:/?#[]@!$&'()*+,;=~-._"


def normalize_relative(value):
    """Return the media-relative path for a stored value, or None when it is not a safe relative path.

    Handles `uploads/x.jpg`, `/uploads/x.jpg`, `/admin/manage/uploads/x.jpg` and repeated prefixes
    (`admin/manage/admin/manage/...`). Windows drive paths, `file:` URIs and `..` segments return None
    so local filesystem details are never published. Percent-escapes are decoded once so a stored
    `a%20b.png` is not double-encoded later.
    """
    value = str(value or "").strip().replace("\\", "/")
    if not value or _WINDOWS_PATH.match(value) or value.lower().startswith("file:"):
        return None
    value = value.lstrip("/")
    changed = True
    while changed:
        changed = False
        for prefix in _STRIP_PREFIXES:
            if value.startswith(prefix):
                value = value[len(prefix):].lstrip("/")
                changed = True
    parts = [unquote(p) for p in value.split("/") if p]
    if not parts or any(p in (".", "..") or "/" in p or "\\" in p for p in parts):
        return None
    return "/".join(parts)


def _encode(relative):
    return "/".join(quote(part, safe="") for part in relative.split("/"))


def image_url(path, request=None):
    """Return an absolute URL for a stored image value, or None when there is nothing safe to return.

    * Absolute http(s) URLs are preserved (only spaces/unsafe characters are escaped).
    * Local uploads under MEDIA_ROOT/uploads are published only when SERVE_LOCAL_UPLOADS is enabled.
    * Everything else keeps the legacy `LEGACY_BASE_URL + path` contract Flutter relies on.
    * Empty values return None; no URL is fabricated for them.
    """
    value = str(path or "").strip()
    if not value:
        return None
    if value.startswith("//"):
        value = "https:" + value
    if value.lower().startswith(("https://", "http://")):
        return quote(value, safe=_URL_SAFE)

    relative = normalize_relative(value)
    if relative is None:
        return None
    media_root = settings.MEDIA_ROOT.resolve()
    local_file = (media_root / relative).resolve()
    try:
        local_file.relative_to(media_root)
    except ValueError:
        return None

    if local_file.is_file() and relative.startswith("uploads/"):
        if not getattr(settings, "SERVE_LOCAL_UPLOADS", False) or request is None:
            return None
        return request.build_absolute_uri("/admin/manage/" + _encode(relative))

    return legacy_url(relative)


def legacy_url(path):
    """`LEGACY_BASE_URL` + normalized path (never duplicates `admin/manage/`), or None if unsafe/unset."""
    relative = normalize_relative(path)
    base = str(getattr(settings, "LEGACY_BASE_URL", "") or "").rstrip("/")
    if relative is None or not base:
        return None
    return f"{base}/{_encode(relative)}"
