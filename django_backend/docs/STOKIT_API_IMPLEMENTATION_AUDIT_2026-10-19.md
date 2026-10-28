# STOKIT API IMPLEMENTATION AUDIT — 2026-10-19

**Workspace:** `stokit`  
**Backend:** `C:\Users\.MSI\Downloads\StokIt Backend\django_backend`  
**Public base URL:** `https://book-fiscally-reunion.ngrok-free.dev`  
**Overall status:** `PARTIAL` — source review, safe read-only smoke tests, database connectivity, and automated tests passed; authenticated endpoint-by-endpoint Flutter parity and write workflows remain unverified.

## Deliverables

1. `django_backend/docs/stokit_flutter_backend_swagger.yaml` — Flutter legacy `/api/` routes; OpenAPI 3.0.3; 33 path items and 36 operations. Both local and current ngrok servers are listed.
2. `django_backend/docs/stokit_admin_api_openapi.yaml` — React admin `/admin-api/` routes; OpenAPI 3.0.3; 26 path items and 72 operations. Both local and current ngrok servers are listed.
3. `django_backend/docs/STOKIT_FLUTTER_BACKEND_COMPATIBILITY.md` — existing Flutter request/response compatibility matrix, updated with the latest verification record.

The OpenAPI specifications are importable YAML documents. Swagger UI is not installed or configured in Django; no package was installed and no Django URL/settings were changed for Swagger UI.

## Source audit findings

- `config/urls.py` mounts Flutter legacy routes under `/api/` and React admin routes under `/admin-api/`.
- Flutter route handlers are registered in `legacy_api/urls.py`; React admin routes are registered in `adminapi/urls.py`.
- React admin token authentication uses `Authorization: Bearer <signed-token>`. Admin login accepts JSON `{username, password}` and returns a signed token plus user/role data on success. No real credentials were used.
- Admin image upload is multipart form data with field `file`; source code checks supported image extensions/signatures and a 5 MB size limit.
- Several write routes mutate orders, banners, categories, products, inventory, allocations, targets, or other database rows. None were executed during this audit.
- Flutter-facing schemas remain provisional where Flutter model parsing and actual authenticated responses have not been compared. Generic admin response schemas are deliberately labelled as provisional where full response fields have not yet been verified.

## Validation evidence

| Check | Result | Evidence |
|---|---|---|
| Python compilation | PASS | `.venv\Scripts\python.exe -m compileall -q config legacy_api adminapi accounts legacydb` exit 0 |
| Django system check | PASS | `manage.py check` — no issues |
| PostgreSQL connectivity | PASS | Django connection established; read-only `SELECT 1` returned `1`; vendor reported `postgresql` |
| Flutter API contract tests | PASS | `legacy_api.tests_runtime_contract legacy_api.tests_contract`: 21 tests passed |
| React admin API tests | PASS | `adminapi.tests_ui_workflows adminapi.tests_uploads`: 24 tests passed |
| Flutter OpenAPI YAML checks | PASS | YAML parse, OpenAPI 3.x, 33 paths, 36 operations, unique operation IDs, no unresolved component references, both server URLs present |
| Admin OpenAPI YAML checks | PASS | YAML parse, OpenAPI 3.x, 26 paths, 72 operations, unique operation IDs, no unresolved component references, both server URLs present |
| Local `GET /api/banner` | PASS | HTTP 200, `application/json; charset=UTF-8` |
| Local unauthenticated `GET /api/category` | Expected auth response | HTTP 401, JSON; no authenticated data access attempted |
| Local unauthenticated `GET /admin-api/dashboard` | Expected auth response | HTTP 401, JSON |
| Local `GET /admin-api/auth/login` | Expected method response | HTTP 405; login implementation accepts POST |
| Public ngrok `GET /api/banner` | PASS | HTTP 200, `application/json; charset=UTF-8` |
| Public host validation | PASS for tested request | Requests no longer produce `DisallowedHost`; root may return 404 if no root route is defined |

The YAML checks were performed using the installed system Python/PyYAML parser. `openapi-spec-validator` and `prance` were not installed; no packages were installed. These checks establish YAML parseability, server entries, operation ID uniqueness and component-reference resolution, not full formal OpenAPI conformance or endpoint compatibility.

## Endpoint verification status

- Source route inventory: verified from URL configuration.
- Methods for documented operations: derived from actual view method implementations.
- Flutter request and response compatibility: PARTIAL; most authenticated response bodies have not been exercised against approved test identities and compared with Flutter model parsers.
- React admin request/response contracts: PARTIAL; routes and common request fields were source-inspected, but most authenticated data schemas were not runtime-verified. Generic schemas must not be treated as a final contract.
- PostgreSQL: connectivity confirmed without schema/data changes.
- Authentication: login and refresh runtime success not tested because no authorized disposable test identity was supplied.
- Mutations: blocked by the requirement to avoid changing shared/production records. No orders, payments, inventory, banners, categories, products, or user records were created/updated/deleted.
- Flutter analyzer/tests: not run in this audit; Flutter CLI availability is still a separate prerequisite.
- Swagger UI: not configured. Import either YAML into an OpenAPI-compatible viewer/Postman to inspect documented routes. To expose in-project Swagger UI, approval is needed before adding a documentation dependency and URL configuration.

## Exact next actions for blocked items

1. **Authenticated runtime verification:** provide or approve an isolated PostgreSQL test database and disposable test identity/fixtures. Then test one endpoint at a time and record status, headers, and response keys; do not use shared production-like data.
2. **Flutter parsing parity:** make the Flutter CLI available, run analyzer/tests without modifying the Flutter source, then compare the actual API model parsing and request construction against the source-derived OpenAPI contract.
3. **Write workflows:** only after the isolated database and disposable fixtures are approved, test create/update/delete endpoints there; verify rollback/cleanup and response contracts.
4. **Formal OpenAPI validation / Swagger UI:** approve adding a compatible validator/UI dependency, or validate the YAML in an external Swagger/OpenAPI editor without changing the repository.
5. **Full contract schemas:** continue reading each endpoint's Flutter model and Django response builder, replacing provisional `GenericObject` schemas only when backed by source and test evidence.

## Safety confirmation

No migrations, SQL dumps, database schema changes, database record writes, account creation, real orders/payments, Flutter source edits, PHP source edits, or package installs were performed. No credentials, tokens, or customer data were included in these reports.
