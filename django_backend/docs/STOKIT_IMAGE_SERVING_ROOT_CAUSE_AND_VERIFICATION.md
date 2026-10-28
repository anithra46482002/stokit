# StokIt image serving: root cause and verification

**Status: PARTIAL.** Existing banner and product image bytes are verified through local HTTP and the public ngrok URL. Authenticated product/banner API JSON and real browser-console verification remain unverified.

## Confirmed root cause
- Multiple Django `runserver` processes were listening on port 8000. A stale `--noreload` process had started before `config/urls.py` registered the local upload route, so it returned 404 even though files existed and fresh test processes returned 200.
- The route was previously conditional at URL-configuration import time. `config/urls.py` was changed so the media route is always registered and `SERVE_LOCAL_UPLOADS` is checked per request. This prevents stale import-time configuration from making the route disappear.
- The image files and existing database paths were valid. After stopping duplicate runservers, the intended process served the images successfully.

## Changes
- `django_backend/config/urls.py`: restricted local upload handler registered consistently; setting is checked per request; path traversal is rejected.
- `django_backend/adminapi/tests_image_serving.py`: tests for route registration, serving with `DEBUG=False`, disabled serving, missing files, traversal, and URL behavior.
- `django_backend/adminapi/image_urls.py` and related upload/serialization changes: normalize image paths and avoid duplicated prefixes while preserving absolute legacy URLs.
- No Flutter/PHP changes, database writes, schema changes, or migrations.

## Effective non-secret configuration
- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`
- `DEBUG=0`
- `SERVE_LOCAL_UPLOADS=1`
- `MEDIA_ROOT=django_backend/media_legacy`
- `VITE_API_BASE_URL` unset; frontend default is `http://127.0.0.1:8000/admin-api/`.
- Public image base: `https://book-fiscally-reunion.ngrok-free.dev/admin/manage/uploads/`

## Automated verification
- Django system check: passed.
- Backend tests: 17 passed across image-serving/upload and related targeted suites.
- React tests: 31 passed.
- React production build: passed.

## Real HTTP verification — local backend
The four existing images returned HTTP 200 with `Content-Type: image/png`; PNG signatures and file bytes were verified against disk in the earlier local test. The route also returns 404 for missing and traversal paths.

## Real HTTP verification — public ngrok URL
Fetched each URL using `curl.exe` and compared the downloaded file's SHA-256 with the local source file:

| Image | HTTP | Content-Type | Bytes | SHA-256 matches disk |
|---|---:|---|---:|---|
| Banner `cd8c10a8...png` | 200 | image/png | 262670 | Yes |
| Product `470c68c8...png` | 200 | image/png | 262670 | Yes |
| Product `458fd3be...png` | 200 | image/png | 262684 | Yes |
| Product `40e3858e...png` | 200 | image/png | 262684 | Yes |

## Duplicate server cleanup
- Stopped the duplicate StokIt runserver processes identified during the cleanup.
- Rechecked TCP port 8000: exactly one listener remains, PID 4912, running the intended StokIt Django process.
- No unrelated process was intentionally terminated; only Python processes identified as duplicate runservers were stopped.

## Remaining verification gaps
- Authenticated product and banner API JSON fields were not fetched live because no authenticated browser session was available. Do not provide credentials in this report.
- Browser console/network inspection remains unavailable because the Cody Playwright CLI is not installed in this environment.
- The direct image URLs are confirmed through ngrok, but the authenticated React admin's final rendered DOM has not been browser-verified.
- `order_pages._image_url` still has separate legacy-host behavior and was left unchanged because order details are outside this image task.
- No missing-image fallback was added to React.

## Final assessment
**PARTIAL.** Local and public image-byte delivery is verified, and duplicate port-8000 runservers have been cleaned up. PASS is withheld until the authenticated product/banner API response fields and actual browser rendering are verified.

## Update: banner API crash (second cause)
- `adminapi/operations.py` used `Slider` without importing it, so `GET /admin-api/banners` raised NameError (HTTP 500) and the Banners page had no image data. Fixed by adding `from legacydb.models import Slider`.
- Verified with an authenticated view call: banners 200, `image_url` = `http://127.0.0.1:8000/admin/manage/uploads/cd8c10a8...png`; products 200 with correct URLs for all three products.
- 32 backend tests pass (ui_workflows, image_serving, uploads). A single server now listens on 8000, started after the fix.
