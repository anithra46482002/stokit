# StokIt Flutter → Django API Compatibility Matrix

**Status: PARTIAL — source-derived contract inventory, not an E2E compatibility certification.**

- Workspace: `C:\Users\.MSI\Downloads\StokIt Backend`
- Django base URL: `http://127.0.0.1:8000`; Flutter production base URL is `https://app.stokitb2b.com/api` in `stokit_flutter/lib/core/constants/api_constants.dart`. No production URL was contacted.
- Swagger: `django_backend/docs/stokit_flutter_backend_swagger.yaml`
- Flutter and PHP source were read-only. No database writes, migrations, schema changes, account creation, package installs, or credentials/tokens were used.
- Existing source audit lists 33 Django `/api/` route patterns and 31 Flutter API path constants. Route count is not equivalent to 33 verified Flutter calls: logout is local-only in inspected code, reset-confirm route has no dedicated constant, and contactus has no confirmed active call site.

## Endpoint-by-endpoint matrix

| Endpoint | Flutter request evidence | Django acceptance/processing evidence | Response evidence | Status / safe next test |
|---|---|---|---|---|
| `POST /api/login` | `AuthRepository.login`: username/password | `views_auth.login` registered; no credential flow run | Success/error schema not verified | PARTIAL; use dummy test account only in approved isolated environment |
| `POST /api/logout` | No server call found; logout appears to clear secure storage locally | `views_auth.logout` route registered | Not verified | PARTIAL; likely client/server workflow mismatch |
| `POST /api/profile` | Profile repository POST, no body | `views_auth.profile` registered | Not verified | PARTIAL; inspect actual token interceptor and model |
| `POST /api/geocode` | Latitude/longitude | `views_auth.geocode` registered | Not verified | PARTIAL; verify nullable/numeric types without persisting |
| `GET /api/banner` | Home datasource GET; parses JSON object into `HomeResponseModel` | Registered; local unauthenticated GET previously returned HTTP 200 JSON | Field names/image URLs and Flutter model parsing not verified | PARTIAL; read-only smoke test only |
| `/api/category` | Category repository; exact method/body needs source trace | Registered; local unauthenticated GET returned HTTP 401 | Not verified | PARTIAL; confirm Flutter method and auth |
| `/api/sub_categories` | Category/subcategory ID; method/body or query unclear | Handler accepts POST body or query per source audit | Not verified | PARTIAL; method/form encoding mismatch risk |
| `POST /api/getCategory` | `category_id` (handler uses it as a subcategory ID) | Registered | Not verified | PARTIAL; misleading legacy field name |
| `POST /api/search` | JSON `min_price`, `max_price`, `sort_by`, `skip`, `limit` | Django POST support added while preserving GET | Response keys `search`, `total`, `skip`, `limit` tested with mocked SQL; item schema/live DB not verified | CODE-LEVEL TESTED; E2E NOT VERIFIED; 4 database-free runtime tests cover filters, bounds, GET compatibility and unsupported method |
| `GET /api/highlights` | Home repository GET | Registered | Not verified | PARTIAL |
| `GET /api/recommended` | Home repository GET | Registered; depends on legacy category_view/warehouse behavior | Not verified | PARTIAL; database dependencies block full proof |
| `POST /api/product-api` | JSON `product_id` | Registered; handler writes `category_view` as side effect | Not verified | BLOCKED for shared DB; only isolated DB allowed |
| `POST /api/fav` | JSON `product_id` | Registered; toggle/persistence not tested | Not verified | BLOCKED for shared DB; isolated DB only |
| `GET /api/favpage` | Favorites repository GET | Registered | Not verified | PARTIAL; auth/data model not verified |
| `POST /api/cart_action` | `product_id`, `variant_id`, `action` | Registered; mutation keys off `variant_id` | Not verified | BLOCKED for shared DB; isolated DB only |
| `POST /api/product-api-cart` | `product_id`, `variants: [{variant_id, qty}]` | Registered | Not verified | PARTIAL; body types and side effects not tested |
| `GET /api/cart_api_test` | Cart repository GET | Registered; server calculates totals; response builder tests preserve `cart_items`, `final_summary`, `discount`, `mov` | Selected pure response/calculation tests exist; no authenticated DB-backed response | PARTIAL; policy currently uses legacy ₹14,000 threshold/10% promo, separate from admin fixed amount setting |
| `GET /api/checkout` | Checkout repository GET | Registered | Not verified | PARTIAL |
| `POST /api/saveCheck` | `{success, checkout_data:{profile, cart_items, cart_summary}}` | Registered; stores payload | Regression test checks legacy misspelled response key `oder_id`; full body not verified | PARTIAL; never test write on shared DB |
| `POST /api/notify` | Notification service sends device-token header | Registered | Exact header and response not verified | PARTIAL; inspect header name before sending |
| `GET /api/noti_list` | Notification repository GET; no mark-read call found | Handler supports GET and PUT `?action=mark_read` | Not verified | PARTIAL; server/client feature gap |
| `PUT /api/noti_list?action=mark_read` | No Flutter call found | Server route behavior from source audit | Not verified | SERVER-ONLY in inspected Flutter source; test only with authorized isolated identity |
| `POST /api/notification_action` | JSON `message_id` | Registered | Not verified | PARTIAL |
| `POST /api/order_post` | Cart API repository POST, no body | Creates order/items and clears cart per source | Not verified | BLOCKED for shared DB; isolated DB only |
| `GET /api/orders` | GET with pagination defaults | Handler supports GET/POST; current user's order listing | Not verified | PARTIAL; verify query names and ownership with isolated fixtures |
| `POST /api/orders` | Flutter POST call shape not established | Handler supports POST | Not verified | BLOCKED until body contract confirmed; don't send guessed body |
| `POST /api/order_details` | JSON `order_id` | Registered | Not verified | PARTIAL; ownership and pricing not E2E verified |
| `POST /api/order_cancel` | JSON `order_id` | Registered | Not verified | BLOCKED for shared DB; isolated DB only |
| `POST /api/acc/` | Reset request via `forgotPassword` constant | Registered; OTP delivery/reset flow not tested | Request/response fields not verified | PARTIAL; use dummy test contact only in isolated setup |
| `POST /api/acc/reset` | No dedicated path constant found; flow may compose route | Registered | Fields/status/rate limits not verified | PARTIAL; request contract unresolved |
| `GET /api/targets` | Target repository GET | Registered | Not verified | PARTIAL; assignment/progress not E2E verified |
| `GET /api/coabout` | About repository GET | Registered | Source review confirms placeholder `example.com` links | Placeholder confirmed; canonical URL needs owner input |
| `POST /api/advancePay-api` | JSON `{status}` | Registered | Not verified | PARTIAL; financial/eligibility behavior not tested |
| `GET /api/crd_rel` | Credit release repository GET | Registered | Not verified | PARTIAL; ledger parity not E2E verified |
| `/api/contactus` | Constant exists, active call site/method not confirmed | `views_finance.contactus` registered | Not verified | PARTIAL; do not assume method/body until handler and client call site reviewed |

## Cross-cutting request/response checks

| Check | Current evidence | Status |
|---|---|---|
| Base URL | Flutter configured for production HTTPS; Swagger targets local HTTP | MISMATCH BY ENVIRONMENT, expected for local testing; no production probe performed |
| JSON encoding | Flutter uses Dio; endpoint-specific body fields partly source-audited | PARTIAL |
| Content-Type | Exact per-call headers not yet captured for every route | PARTIAL |
| Bearer token | `ApiService` installs an auth interceptor; per-endpoint enforcement varies and must be confirmed from source/runtime | PARTIAL |
| Null values / optional fields | Not verified endpoint-by-endpoint | PARTIAL |
| IDs and numeric values | Search bounds/pagination types covered by regression tests; other ID types vary and need source validation | PARTIAL |
| Multipart image upload | No Flutter-facing upload route in the 33 legacy API patterns; admin upload is a separate `/admin-api/uploads` contract | NOT APPLICABLE to legacy Flutter route inventory unless a Flutter call is discovered |
| Response field names | `search` response keys and legacy `oder_id` key have code-level tests; most mobile response models not tested against live responses | PARTIAL |
| Error status/body | Local unauthenticated `/api/category` gave 401; search 400/405 paths covered in mocked tests; other errors not systematically tested | PARTIAL |
| Image URL accessibility | Banner endpoint responded JSON locally; actual image URLs/bytes and mobile rendering not tested | PARTIAL |
| Database effects | No authenticated isolated-DB CRUD/write tests run in this task | BLOCKED |

## Verification record

- Existing audit reports 33 Flutter-facing Django URL patterns and 31 Flutter API constants. The route list above reflects the source audit; exact per-call parity is incomplete.
- Cart PostgreSQL rollback verification (target `stokit_postgres_dev`, `.env.postgres`): **17 checks PASS, 0 failures**. Synthetic cart rows/orders were rolled back; `a_cart.id` sequence advancement is the documented residual side effect. This does not certify Flutter UI behavior.
- Fresh tests run for this task: `python manage.py test legacy_api.tests_runtime_contract legacy_api.tests_contract --verbosity 1` → **21 tests PASS**, Django system check clean. These are source/contract tests, not authenticated live parity.
- Fresh `python manage.py check` → **PASS**, no issues. Fresh safe local GET probes: `/api/banner` → **200** `application/json; charset=UTF-8` (159-byte sample read); unauthenticated `/api/category` → **401** `application/json; charset=UTF-8` (59-byte sample read). Response body values were not printed.
- OpenAPI YAML validation: **PASS** with the already-installed global Python PyYAML parser. Parsed as OpenAPI 3.0.3; 33 path items, 36 HTTP operations, 36 unique operationIds, no unresolved component schema references. `contactus` is intentionally listed without an HTTP method because the active Flutter call and method are unconfirmed. This validates YAML syntax/references, not full OpenAPI conformance or runtime compatibility.
- Swagger UI: **NOT INSTALLED/NOT CONFIGURED** in inspected Django URLs/settings/dependencies; no schema/docs URL is registered. Flutter `analyze --no-pub` and `test --no-pub` were previously BLOCKED because Flutter CLI was unavailable. No endpoint is certified end-to-end; no credentials, tokens, customer data, real orders, payments, migrations, database writes or schema changes were used.

## Remaining work

1. Finish source tracing for each Flutter repository/model and compare every serializer/parsing expectation against Django's actual response builder.
2. Validate OpenAPI syntax and schema references with tools already installed.
3. Run database-independent tests only; record fresh command output.
4. Use only read-only local GET endpoints for smoke checks, avoiding `/api/product-api` because it has a `category_view` side effect.
5. Run mutations only after approval of an isolated test database and disposable fixtures.

**Acceptance status: PARTIAL.** Swagger supports representative local requests, but unknown request/response fields are deliberately marked unverified instead of fabricated.


## Latest Cody audit — 2026-10-19

- Added a separate React admin OpenAPI specification: `django_backend/docs/stokit_admin_api_openapi.yaml` (OpenAPI 3.0.3, 26 path items, 72 operations). The existing Flutter specification now lists both local and ngrok server URLs.
- Fresh validation: `python -m compileall -q config legacy_api adminapi accounts legacydb` PASS; `python manage.py check` PASS; read-only PostgreSQL `SELECT 1` PASS.
- Fresh tests: `legacy_api.tests_runtime_contract legacy_api.tests_contract` → 21/21 PASS; `adminapi.tests_ui_workflows adminapi.tests_uploads` → 24/24 PASS.
- YAML checks with installed system Python/PyYAML: Flutter spec 33 paths / 36 operations; admin spec 26 paths / 72 operations; OpenAPI 3.x, unique operation IDs, component references resolve, both server URLs present. Formal `openapi-spec-validator`/`prance` and Swagger UI are not installed; no dependency was installed.
- Safe runtime probes: local and public `GET /api/banner` → 200 JSON; unauthenticated local `GET /api/category` and `/admin-api/dashboard` → 401 JSON; `GET /admin-api/auth/login` → 405 because login requires POST. No auth or mutation calls were made.
- Overall status remains **PARTIAL**: most authenticated response bodies are not runtime-verified against Flutter parsers; admin response schemas remain provisional in places. See `STOKIT_API_IMPLEMENTATION_AUDIT_2026-10-19.md` for exact blockers and next actions.
