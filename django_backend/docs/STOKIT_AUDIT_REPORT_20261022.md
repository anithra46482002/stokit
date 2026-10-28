# StokIt audit report, 22 Oct 2026

Status: PARTIAL (see "Not verified").

## Fixed
| # | Issue | Fix |
|---|-------|-----|
| 1 | Product save returned 500 with `discount_banners`/`set_contains` | Added missing `import json` in `adminapi/crud.py` |
| 2 | 48 admin write endpoints returned 500 for non-object JSON bodies | Central guard in `permissions.py` (runs after the role check) |
| 3 | `POST /allocations/<id>` returned 500 | Now a clean 405 |
| 4 | JSON `null` names stored as the literal "None" | `clean_text()` in `field_validation.py` |
| 5 | Banner `image_path: 5` stored as "5" | POST and PATCH now require a string; invalid PATCH leaves the existing image untouched |
| 6 | Hardcoded ngrok host in `ALLOWED_HOSTS` | Read from the env file |
| 7 | Transient `IndentationError` in `adminapi/crud.py` (line 472) made every admin API call return 500 | File was rewritten at 17:18:33 and compiles; server reloaded on the fixed file |
| 8 | Order-detail item images built from the legacy host only | `order_pages._image_url` now uses the shared `image_urls.image_url` with `request` |
| 9 | Admin thumbnails cropped and broken-image icons | New `SafeImage` component (fallback placeholder), `.sk-thumb` uses `object-fit: contain` |

## Verification
- `manage.py check`: clean.
- Backend suite: 293 tests pass on both `.venv` (Django 6.0.9) and global Python (Django 5.2.18).
- Frontend: lint 0 warnings/errors, 47/47 tests, production build OK.
- Unauthenticated admin requests return 401; path traversal and missing files return 404.

## Not verified
- Real-database sweep of fixes 4 and 5 (needs an authorized admin login and a rolled-back transaction).
- Browser/UI test and authenticated banner upload/update (no approved credentials or disposable banner).
- Flutter on a device.
- ngrok tunnel targets :8001, not Django on :8000 (not changed).

## Cleanup
Backups to delete when satisfied: `adminapi/*.bak_audit`, `admin_frontend/src/BannersPage.jsx.bak_banner_fix`.
`.env.postgres` defines `DJANGO_ALLOWED_HOSTS` twice (last wins); not edited.
