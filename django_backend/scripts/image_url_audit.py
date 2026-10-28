"""Read-only image URL audit.

Collects every stored image value (distinct, per table/column) through the ORM, builds the public URL with the
SAME shared helper the APIs use, then performs one safe GET per URL and verifies the response is really an image.

    python scripts/image_url_audit.py --base-url http://127.0.0.1:8000 [--limit 500] [--timeout 10] [--json out.json]

Nothing is written to the database or to MEDIA_ROOT. Exit code 1 when any URL fails. Results only describe the
environment/host the script could reach: a clean run against local dev data is NOT a production verification.
"""
import argparse
import json
import os
import socket
import ssl
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF", b"<svg", b"<?xml")  # RIFF = WEBP container
SOURCES = [("LegacyUser", "profile_picture"), ("Category", "category_image"), ("Subcategory", "subcategory_image"),
           ("Product", "share_image"), ("ProductImage", "image_path"), ("Slider", "image_path"),
           ("AdvancePayOffer", "image_path"), ("Target", "reward_image")]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def fetch(url, timeout):
    """GET (no HEAD) and classify. Redirects are reported, not silently followed."""
    req = urllib.request.Request(url, headers={"User-Agent": "stokit-image-audit/1", "Accept": "image/*"})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as r:
            head = r.read(16)
            ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if not ctype.startswith("image/"):
                return "not_image", f"status {r.status} content-type {ctype or 'none'}"
            if not head.startswith(MAGIC):
                return "not_image", f"image content-type {ctype} but bytes are not an image signature"
            return "ok", ctype
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:
            return "redirect", f"{e.code} -> {e.headers.get('Location')}"
        if e.code in (401, 403):
            return "authorization", str(e.code)
        if e.code in (404, 410):
            return "missing_file", str(e.code)
        return ("server_error" if e.code >= 500 else "http_error"), str(e.code)
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, ssl.SSLError):
            return "network_tls", str(reason)
        if isinstance(reason, socket.gaierror):
            return "network_dns", str(reason)
        return "network", str(reason)
    except (socket.timeout, TimeoutError):
        return "network", "timeout"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000", help="origin used for locally served uploads")
    ap.add_argument("--limit", type=int, default=0, help="max distinct values per column (0 = all)")
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--json", help="write full results to this file")
    args = ap.parse_args()

    import django
    django.setup()
    from django.conf import settings
    from adminapi.image_urls import image_url, legacy_url
    from legacydb import models

    request = SimpleNamespace(build_absolute_uri=lambda p: args.base_url.rstrip("/") + p)
    results, seen = [], set()
    for model_name, field in SOURCES:
        model = getattr(models, model_name)
        values = model.objects.exclude(**{f"{field}__isnull": True}).values_list(field, flat=True).distinct()
        if args.limit:
            values = values[: args.limit]
        for value in values:
            if not str(value).strip():
                results.append(dict(source=f"{model_name}.{field}", stored=value, url=None, status="empty", detail=""))
                continue
            url = image_url(value, request) or legacy_url(value)
            if url is None:
                results.append(dict(source=f"{model_name}.{field}", stored=value, url=None,
                                    status="url_format", detail="no safe URL could be built"))
            elif (url, ) in seen:
                continue
            else:
                seen.add((url, ))
                status, detail = fetch(url, args.timeout)
                results.append(dict(source=f"{model_name}.{field}", stored=value, url=url, status=status, detail=detail))

    checked = [r for r in results if r["status"] not in ("empty",)]
    counts = Counter(r["status"] for r in results)
    print(f"MEDIA_ROOT={settings.MEDIA_ROOT}  LEGACY_BASE_URL={settings.LEGACY_BASE_URL}  base={args.base_url}")
    print(f"values={len(results)} checked={len(checked)} ok={counts['ok']} failed={len(checked) - counts['ok']} "
          f"empty(skipped)={counts['empty']}")
    for status, n in sorted(counts.items()):
        print(f"  {status}: {n}")
    for r in checked:
        if r["status"] != "ok":
            print(f"FAIL [{r['status']}] {r['source']} stored={r['stored']!r} url={r['url']} ({r['detail']})")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return 1 if len(checked) - counts["ok"] else 0


if __name__ == "__main__":
    sys.exit(main())
