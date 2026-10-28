# STOKIT Complete API Audit

**Audit date:** 2026-10-16  
**Status: PARTIAL.** Static source audit only; no route is certified E2E PASS. PHP and Flutter source are read-only. No live database writes, migrations, DDL, imports, restores, account creation, package installation, or destructive database cleanup occurred. Secrets were not read or printed.

## Scope and project structure

Reviewed the React/Vite admin frontend, Django backend and PostgreSQL-only settings, Django route/view/test source, Flutter route constants and API repositories, and available PHP reference snapshot. Root workspace `C:\Users\.MSI\Downloads\StokIt Backend` contains `admin_frontend/` and `django_backend/`; separate read-only workspaces are `stokit_flutter` and `phpref`. Root has no `.git` directory, so Git status and tracked/untracked-file provenance cannot be established.

Source route totals: **26 Django admin URL patterns** under `/admin-api/`, **33 Flutter-facing legacy URL patterns** under `/api/`, **59 registered patterns total**. Flutter defines 31 API path constants. Static route matching is not proof of runtime success. All 59 patterns remain NOT VERIFIED for authenticated isolated E2E.

## React admin → Django route matrix

React uses Axios from `admin_frontend/src/api.js`; base URL is `VITE_API_BASE_URL` or loopback `http://127.0.0.1:8000/admin-api/`; bearer token is read from session storage. Protected calls use `AdminTokenAuthentication` and role/resource permissions. Methods below reflect source, not full role/method integration evidence.

| # | Route pattern | Handler / workflow | Methods observed | Status |
|---:|---|---|---|---|
| 1 | `/admin-api/auth/login` | `AdminLoginView`; login page | POST | BLOCKED — unit tests only; browser login not run |
| 2 | `/admin-api/auth/refresh` | `AdminRefreshView` | POST | NOT VERIFIED — refresh flow not E2E tested |
| 3 | `/admin-api/uploads` | `ImageUploadView`; shared `uploadImage()` | POST multipart `file` | NOT VERIFIED — real file storage/serving not E2E tested |
| 4 | `/admin-api/dashboard` | `DashboardView` | GET | NOT VERIFIED — no authenticated live request |
| 5 | `/admin-api/reports` | `ReportsAdminView` | GET | NOT VERIFIED — report data parity not tested |
| 6 | `/admin-api/categories` | `CategoryCRUDView` | GET, POST, PATCH, DELETE | NOT VERIFIED — static/unit evidence only |
| 7 | `/admin-api/subcategories` | `SubcategoryCRUDView` | GET, POST, PATCH, DELETE | NOT VERIFIED — isolated parent relation not tested |
| 8 | `/admin-api/products` | `ProductCRUDView` | GET, POST, PATCH, DELETE | NOT VERIFIED — validation regressions exist; authenticated CRUD blocked |
| 9 | `/admin-api/product-variants` | `VariantCRUDView` | GET, POST, PATCH, DELETE | NOT VERIFIED — stock/transaction parity not E2E tested |
| 10 | `/admin-api/product-images` | `ProductImageCRUDView` | GET, POST, DELETE | NOT VERIFIED — image persistence and main-image effects not E2E tested |
| 11 | `/admin-api/customers` | `CustomerCRUDView` | GET, POST, PATCH, DELETE | NOT VERIFIED — role restrictions/deactivation need isolated tests |
| 12 | `/admin-api/orders` | `OrderAdminCRUDView` | GET, POST, PATCH | NOT VERIFIED — no DB-backed create/readback; no idempotency key |
| 13 | `/admin-api/orders/manage` | `OrderManageView` | GET | CODE-LEVEL FIXED — removed GET write side effect; mocked read-only regression passes. Authenticated isolated E2E remains unverified |
| 14 | `/admin-api/orders/bulk-assign` | `OrderBulkAssignView` | POST | NOT VERIFIED — no DB-backed assignment test |
| 15 | `/admin-api/orders/{order_id}/detail` | `OrderDetailView` | GET, PATCH, DELETE | NOT VERIFIED — delete policy and transaction effects need isolated test/owner decision |
| 16 | `/admin-api/orders/{order_id}/status` | `OrderStatusView` | POST | NOT VERIFIED — role/status graph and credit effects need policy tests |
| 17 | `/admin-api/banners` | `BannerAdminView` | GET, POST, PATCH, DELETE | NOT VERIFIED — upload/save/refresh/serve not E2E tested |
| 18 | `/admin-api/notifications` | `NotificationAdminView` | GET, POST, DELETE | NOT VERIFIED — push delivery not configured |
| 19 | `/admin-api/warehouses` | `WarehouseAdminView` | GET, POST, PATCH, DELETE | NOT VERIFIED — map/place selection and save/reload not E2E tested |
| 20 | `/admin-api/inventory` | `InventoryAdminView` | GET, PATCH | NOT VERIFIED — stock adjustment/log atomicity not tested in isolated DB |
| 21 | `/admin-api/cart-discount-settings` | `CartDiscountSettingsView` | GET, PUT | NOT VERIFIED — no DB write test; legacy cart formula differs |
| 22 | `/admin-api/staff` | `StaffAdminView` | GET, POST, PATCH, DELETE | NOT VERIFIED — principal creation/role behavior not integration-tested |
| 23 | `/admin-api/advance-payments` | `AdvancePaymentOffersView` | GET, POST, PATCH, DELETE | NOT VERIFIED — image/allocation effects not E2E tested |
| 24 | `/admin-api/advance-allocations` | `AdvanceAllocationAdminView` | GET, POST, PATCH, DELETE | NOT VERIFIED — ledger/concurrency not tested |
| 25 | `/admin-api/locations` | `LocationAdminView` | GET, POST, PATCH, DELETE | BLOCKED — city collation parity unresolved |
| 26 | `/admin-api/targets` | `TargetAdminView` | GET, POST, PATCH, DELETE | NOT VERIFIED — category/image/progress persistence not E2E tested |

## Flutter → Django legacy route matrix

Flutter base URL in `lib/core/constants/api_constants.dart` is `https://app.stokitb2b.com/api`; Django mounts matching suffixes under `/api/`. Calls usually use `ApiService.dio` with Bearer token; secure storage is used for token. PHP snapshot is not proven to be active deployment source, so payload parity remains unverified.

| # | Route | Flutter call / request shape | Django handler | Status / contract note |
|---:|---|---|---|---|
| 1 | `/api/login` | AuthRepository POST username/password | `views_auth.login` | NOT VERIFIED — credential flow not run |
| 2 | `/api/logout` | No API call found; `AuthService.logout` clears local secure storage | `views_auth.logout` | NOT VERIFIED — mobile logout appears local-only |
| 3 | `/api/profile` | ProfileRepository POST, no body | `views_auth.profile` | NOT VERIFIED |
| 4 | `/api/geocode` | ProfileRepository POST latitude/longitude | `views_auth.geocode` | NOT VERIFIED — persistence not tested |
| 5 | `/api/banner` | HomeRemoteDataSource GET | `views_catalog.banner` | NOT VERIFIED — image serving/model parse not tested |
| 6 | `/api/category` | Home/category repository | `views_catalog.category` | NOT VERIFIED — exact call method/model parse needs runtime evidence |
| 7 | `/api/sub_categories` | Subcategory repository; category/subcategory ID | `views_catalog.sub_categories` | NOT VERIFIED — POST body or query supported; payload parity untested |
| 8 | `/api/getCategory` | POST `category_id` (actually subcategory ID) | `views_catalog.get_category` | NOT VERIFIED — legacy field naming is misleading |
| 9 | `/api/search` | SearchRepository.search() sends POST JSON `{min_price,max_price,sort_by,skip,limit}` | `views_catalog.search` now accepts POST JSON filters and retains the PHP-compatible GET query contract | CODE-LEVEL FIX TESTED; E2E NOT VERIFIED — four database-free runtime tests cover POST filters, invalid ranges, unsupported methods and legacy GET search; no live request or DB readback |
| 10 | `/api/highlights` | Home repository GET | `views_catalog.highlights` | NOT VERIFIED |
| 11 | `/api/recommended` | Home repository GET | `views_catalog.recommended` | NOT VERIFIED — depends on `category_view` and warehouse behavior |
| 12 | `/api/product-api` | ProductRepository POST `product_id` | `views_catalog.product_api` | NOT VERIFIED — view writes `category_view` as side effect |
| 13 | `/api/fav` | FavRepository POST `product_id` | `views_favorites.fav` | NOT VERIFIED — toggle/persistence not tested |
| 14 | `/api/favpage` | FavRepository GET | `views_favorites.favpage` | NOT VERIFIED |
| 15 | `/api/cart_action` | POST `product_id`, `variant_id`, `action` | `views_cart.cart_action` | NOT VERIFIED — mutation keys off `variant_id`; PHP source does likewise |
| 16 | `/api/product-api-cart` | POST `product_id`, `variants:[{variant_id,qty}]` | `views_commerce.product_api_cart` | NOT VERIFIED — DB effects not tested |
| 17 | `/api/cart_api_test` | Cart repository GET | `views_commerce.cart_api_test` | NOT VERIFIED — legacy ₹14,000/10% promo differs from admin fixed amount setting |
| 18 | `/api/checkout` | CheckoutRepository GET | `views_commerce.checkout` | NOT VERIFIED — response model not E2E tested |
| 19 | `/api/saveCheck` | POST `{success,checkout_data:{profile,cart_items,cart_summary}}` | `views_remaining.save_check` | NOT VERIFIED — stores payload; returns legacy key `oder_id`; no readback test |
| 20 | `/api/notify` | Notification token service POST device-token header | `views_commerce.notify` | NOT VERIFIED — token persistence not tested |
| 21 | `/api/noti_list` | NotificationRepository GET; no mark-read call found | `views_commerce.noti_list` GET and PUT `?action=mark_read` | NOT VERIFIED — mark-read workflow absent from inspected repository |
| 22 | `/api/notification_action` | POST `message_id` | `views_commerce.notification_action` | NOT VERIFIED |
| 23 | `/api/order_post` | CartApiRepository POST, no body | `views_orders.order_post` | NOT VERIFIED — creates order/items and clears cart; transaction not isolated-tested |
| 24 | `/api/orders` | OrderRepository GET with pagination defaults | `views_orders.orders` GET/POST | NOT VERIFIED — ownership/pagination not E2E tested |
| 25 | `/api/order_details` | POST `order_id` | `views_orders.order_details` | NOT VERIFIED — pricing formula/ownership not E2E tested |
| 26 | `/api/order_cancel` | POST `order_id` | `views_orders.order_cancel` | NOT VERIFIED — ownership/status transition not E2E tested |
| 27 | `/api/acc/` | `ApiConstants.forgotPassword` reset request | `views_reset.request_reset` | NOT VERIFIED — OTP delivery/reset flow not tested |
| 28 | `/api/acc/reset` | No dedicated constant found; may be composed by reset flow | `views_reset.reset_password` | NOT VERIFIED — complete reset/rate-limit flow not tested |
| 29 | `/api/targets` | TargetRepository GET | `views_remaining.targets` | NOT VERIFIED — assignment/progress not E2E tested |
| 30 | `/api/coabout` | AboutRepository GET | `views_remaining.coabout` | CONFIRMED PLACEHOLDER — returns `example.com` links; owner must provide canonical URLs |
| 31 | `/api/advancePay-api` | POST `{status}` | `views_finance.advance_pay` | NOT VERIFIED — eligibility/response model not tested |
| 32 | `/api/crd_rel` | CreditReleaseRepository GET | `views_finance.credit_release` | NOT VERIFIED — ledger/response parity not tested |
| 33 | `/api/contactus` | Constant exists; active call site not confirmed | `views_finance.contactus` | NOT VERIFIED — method/payload/delivery unknown |

## Confirmed defects and risks

| ID | Severity | Finding | Evidence | Status |
|---|---|---|---|---|
| STK-API-001 | HIGH | Flutter search sends POST JSON with price/sort/page filters; original Django handler read only GET query parameters; PHP snapshot declares GET only. | Flutter `SearchRepository.search`, Django `views_catalog.search`, PHP `api/search.php` | FIXED IN DJANGO ONLY — added POST JSON support for min/max price, allowlisted sorting and pagination while retaining GET behavior; 3 regression tests pass. Flutter/PHP unchanged; E2E remains NOT VERIFIED |
| STK-API-002 | MEDIUM | `/api/coabout` returns placeholder `example.com` links. | `views_remaining.coabout` | CONFIRMED; canonical URLs required from owner |
| STK-API-003 | HIGH | `GET /admin-api/orders/manage` writes `zg_checkout.view='y'` when orders exist. | `OrderManageView.get` | CONFIRMED; never call against live target |
| STK-API-004 | HIGH | Legacy cart has fixed ₹14,000 threshold/10% promotion while admin setting stores a separate fixed amount. | `views_commerce._build_cart_response`, cart discount docs | CONFIRMED policy divergence; owner decision required |
| STK-API-005 | MEDIUM | Flutter logout appears local-only; server logout route exists but no client call was found. | `AuthService.logout`, route constants | CONFIRMED source observation |
| STK-API-006 | MEDIUM | Flutter notification repository lacks a mark-read call despite backend support for PUT mark-read. | `NotificationRepository`, `views_commerce.noti_list` | CONFIRMED source observation |
| STK-API-007 | MEDIUM | `CustomersPage.txt` and `NotificationsPage.txt` duplicate-looking text copies beside JSX source; they are not imported but may be intentional backups. | Static tree/import inspection | REVIEW REQUIRED; preserved |
| STK-API-008 | MEDIUM | No Git repository metadata at workspace root; tracked/untracked changes cannot be proven. | Root scan and failed `git status` | CONFIRMED |

## Security/config/dependency review

- Django requires `DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`; PostgreSQL is the only configured DB engine. Default env file is `.env.postgres` unless `DJANGO_ENV_FILE` is selected. Only env-file names/metadata were read; values were not read or printed. Preserve `.env`, `.env.bak_stokit_dev`, `.env.postgres`, `.env.test`, and examples.
- React defaults to loopback API; deployment needs `VITE_API_BASE_URL`. Google Maps key was not found in inspected source/config; map fallback exists, but Google Places is not verified.
- PHP reference has config/token/log/dump files and remains read-only; never print sensitive contents. Active deployed PHP revision is unknown.
- Flutter dependencies include Dio, secure storage, Firebase Messaging, Geolocator and generated Freezed/JSON files. `pubspec.yaml` declares Dart SDK `^3.11.0`; README is generic template. No dependency install/upgrade performed. Preserve platform build files, Firebase configuration, `local.properties`, generated source, assets and lockfile.

## Cleanup classification — audit performed before cleanup

| Candidate | Classification | Reason / action |
|---|---|---|
| Python `__pycache__` and `.pyc` in Django app source directories, excluding `.venv` | SAFE | Generated bytecode only; regenerates from source. Only these may be removed and logged. |
| `admin_frontend/node_modules/.vite`, `.vite-temp` | REVIEW REQUIRED | Generated cache but existing dev server may use it; preserve. |
| `admin_frontend/dist` | REVIEW REQUIRED | Generated build output may be served by local preview; preserve. |
| `node_modules`, `django_backend/.venv` | KEEP | Installed dependency environments; no package installs. |
| `CustomersPage.txt`, `NotificationsPage.txt` | REVIEW REQUIRED | Possibly backup snapshots; do not delete without approval. |
| `.env*`, SQL dumps, backups, uploads/media, migrations, docs, audit scripts | KEEP | Sensitive config, user/business data, rollback/provenance/schema evidence. |
| PHP and Flutter workspaces | KEEP | Explicitly read-only; no changes/cleanup. |
| Databases, DB backups, external temp evidence, processes/services | KEEP / APPROVAL REQUIRED | Not eligible for source cache cleanup. |

## Verification status summary

| Layer | Route patterns | Static review | Authenticated E2E |
|---|---:|---|---|
| React admin → Django | 26 | Reviewed | BLOCKED / NOT RUN |
| Flutter → Django | 33 | Reviewed; 31 API constants | BLOCKED / NOT RUN |
| Total | 59 | Static audit only | **0 certified E2E PASS** |

Each route still needs success/error, request/response type, auth/role, upload, persistence/readback and transaction tests against an approved isolated environment. Do not call `/admin-api/orders/manage` against the live target.

## Phase log

- Phase 1 audit: project trees, entry points, dependencies, settings, route declarations, handler source, tests/docs, env names/metadata, Flutter repositories and PHP reference inspected; no deletion during audit.
- Phase 2 cleanup: initial audit pass removed 10 generated Python `__pycache__` directories / 74 `.pyc` files; tests regenerated caches, then a final post-test pass removed 9 directories / 63 `.pyc` files. Final scan: 0 source-tree `__pycache__` directories outside `.venv`. Full log: `STOKIT_TEMPORARY_RESOURCE_CLEANUP_REVIEW.md`. No node_modules, dist, uploads, env, SQL, backups, migrations, PHP or Flutter files were deleted.
- Phase 3 API inventory: this document is the canonical 59-route matrix. Static registration is not reported as proof of API success.
- Phase 4 completed for the safe local scope: frontend tests/lint/build, Django check/migrate consistency, 80 selected database-independent tests, and search compatibility fix/regressions. Authenticated CRUD/browser and live DB write tests remain BLOCKED pending explicit isolated-environment approval.

**Overall status: PARTIAL.** Search request mismatch is fixed in Django with database-free regressions; placeholder company links, order-list side effect, cart policy divergence, and missing E2E evidence remain open.


## Phase 4 update — safe tests and search contract fix (2026-10-16)

### Confirmed code fix

`STK-API-001` was fixed in `legacy_api/views_catalog.py` without changing Flutter or PHP source. The endpoint now retains the legacy GET query contract and additionally accepts Flutter POST JSON fields `min_price`, `max_price`, `sort_by`, `skip`, and `limit`. Price values must be finite and non-negative, min cannot exceed max, sort keys are allowlisted (`price_asc`, `price_desc`, `discount`), and POST page size is capped at 100. SQL filter values remain parameterized; sort SQL comes only from the fixed allowlist. Response keys remain `search`, `total`, `skip`, `limit`.

Added four database-free runtime regressions: POST filter/sort/pagination SQL shape, legacy GET search remains supported, inverted price bounds return 400 without SQL calls, and unsupported methods return 405 without SQL calls. Targeted `legacy_api.tests_runtime_contract`: **7/7 PASS**. These are mocked SQL helper tests, not live DB evidence.

### Checks actually executed

| Check | Actual result | Evidence limits |
|---|---|---|
| React unit tests | PASS — 27/27 | Unit tests only; no browser/API E2E |
| React lint | PASS — 0 warnings, 0 errors; 23 files | Static lint only |
| React production build | PASS — Vite transformed 1,988 modules | Build is not API runtime evidence |
| Django system check | PASS — no issues | No business-flow proof |
| Django migration consistency `migrate --check` | PASS — exit 0 | No migration was applied |
| Selected database-independent Django suite | PASS — 80/80 | No test database setup observed; mocked/unit contracts only |
| Flutter `analyze --no-pub` | BLOCKED — Flutter CLI not recognized | No package install attempted |
| Flutter `test --no-pub` | BLOCKED — Flutter CLI not recognized | No package install attempted |
| Authenticated browser CRUD, upload, order, inventory, cart-discount, location E2E | BLOCKED / NOT RUN | Requires approved isolated DB, authorized existing test identities and fixtures |

No PHP/Flutter source changes, package installation, database writes, DDL, migrations, imports, restores or account creation occurred. Overall status remains PARTIAL.

## Local service smoke checks — 2026-10-16

These probes were made against the local listeners only; response data values were not printed and no write/mutation endpoints were called.

| Probe | Actual result | What it proves / does not prove |
|---|---|---|
| React `/login` at `127.0.0.1:5173` | HTTP 200, HTML | Vite server serves the login route; does not prove login/authenticated UI workflows |
| Django `GET /api/banner` | HTTP 200, JSON | Local banner endpoint responds; does not prove all records, images, mobile parsing or production deployment compatibility |
| Django `GET /api/category` without a token | HTTP 401 | Authentication gate rejects the unauthenticated request; successful authenticated category flow remains unverified |
| Django `GET /admin-api/dashboard` without a token | HTTP 401 | Admin authentication gate rejects the unauthenticated request; successful admin dashboard flow remains unverified |
| Flutter/Dart tool availability | Both commands unavailable | Flutter analyzer and test suite could not run; no package installation attempted |

The React frontend and Django backend have local listeners, but Flutter's configured API base is `https://app.stokitb2b.com/api`, not the local `127.0.0.1:8000/api` development server. No production URL probe was performed. No login credentials were used, no account was created, and no database write was performed. These are smoke checks only; they do not change the 59-route E2E status.

## Order creation, financial summary, and banner update continuation (2026-10-16)

### Confirmed source fixes and regressions

- Order creation now supports `variant_id` from the React form. The form displays available variants and prices, resets the variant when product changes, and blocks duplicate product/variant combinations. Backend validates the product and variant relationship, requires a variant when a product has variant rows, and uses the database variant price for the line total. The existing atomic order + items + status-history write remains in place.
- Dashboard and reports normalize status case/whitespace and calculate revenue only from delivered/fulfilled orders. Order Management financial SQL recognizes completed statuses for revenue, known open statuses for pending count, and excludes cancelled/failed orders. The SQL counts distinct order IDs to avoid duplicate totals from joined user rows.
- Order Management GET was changed to be read-only: the former `UPDATE zg_checkout SET view='y'` side effect has been removed. Date filtering now validates calendar dates and uses an exclusive next-day upper bound.
- Backend validation arrays/nested error values are now rendered by the React error formatter.
- Banner upload still stores a new file under `MEDIA_ROOT/uploads`, returns `image_path`, and leaves the old image file untouched when PATCH replaces the reference. Existing mocked path persistence and temporary upload tests passed. Browser reload and actual persisted banner retrieval remain unverified.

### Latest checks

- React unit tests: **31/31 PASS**.
- React lint: **PASS**, 0 warnings/errors, 24 files.
- React production build: **PASS**, Vite transformed 1,988 modules.
- Selected database-independent Django/API contract suite: **105/105 PASS**.
- Django system check: **PASS**.
- Django `migrate --check`: **PASS**, no migration applied.

These are source/unit/contract checks only. No authenticated order creation/readback, aggregate comparison against real PostgreSQL order rows, or banner upload/PATCH/reload/image-serving browser E2E was executed. No PostgreSQL write, schema change, migration, import, restore, account creation, package install, or destructive cleanup occurred. PHP and Flutter remain unchanged. **Overall status: PARTIAL.**

Banner serving component evidence: the temporary-media upload test now invokes Django's `serve` view and checks returned bytes (**5/5 upload tests pass**). This is not an authenticated browser test of the configured URL route or a banner-row persistence/reload cycle. The development route is registered only with `DEBUG=True`; production media hosting remains unverified.

## Static Flutter + web API audit continuation (2026-10-16)

### Dedicated Flutter workspace and SDK evidence

- Audited the exact `stokit_mobile` workspace at `C:\Users\.MSI\Downloads\stokit (2) (2)\stokit`; inventory confirms **112 Dart files under `lib/`** plus `test/widget_test.dart`. No files from `stokit_flutter` or the older `flutter` workspace were used.
- Flutter 3.47.6 / Dart 3.13.5 exists at `C:\src\flutter`; neither command is on PATH. Running the SDK by absolute path is possible, but `flutter analyze --no-pub` fails with 6,545 issues and `flutter test --no-pub` fails at compilation because `.dart_tool/package_config.json` points at missing `C:\flutter\packages\flutter_test` and `C:\Users\OMEN\AppData\Local\Pub\Cache` roots. No `pub get`, package installation, or cache repair was performed.
- `dart format --output=none` parsed the 112 library Dart files plus the widget test without writing source. It reported 84 files would be reformatted; no Flutter source was modified.

### Route inventory and web/mobile boundary

- The 31 active `ApiConstants` paths map to registered Django `/api/` suffixes. The commented `/products` constant has no registered route and no active call site. Django also registers `/api/logout` and `/api/acc/reset` without active matching constants/call sites found in the mobile source.
- React continues to use `/admin-api/` through Axios and Flutter uses `/api/` through Dio. Static source review did not identify an unmatched active React endpoint in the existing 26-pattern admin route matrix. This confirms source routing only, not authenticated runtime behavior.
- Updated the stale Order Management row: `GET /admin-api/orders/manage` is code-level read-only after the UPDATE removal; its mocked regression passes. Authenticated isolated E2E remains unverified.

### Confirmed source findings

| ID | Severity | Endpoint / affected file and line | Finding | Recommended fix | Evidence status |
|---|---|---|---|---|---|
| STK-MOB-001 | HIGH | All authenticated `/api/*`; `lib/core/constants/api_service.dart:41-49` | Shared interceptor logs the bearer token in debug output. | Remove token/header values from logs and redact credentials. | Confirmed source defect |
| STK-MOB-002 | MEDIUM | `/api/logout`; `lib/features/auth/data/services/auth_service.dart:29-32` | Logout only clears local storage although Django exposes a session-revoking logout endpoint. | Call server logout while token is available, then clear local storage regardless of network result. | Confirmed source defect; server-side behavior not E2E tested |
| STK-MOB-003 | HIGH | `/api/getCategory`; `lib/features/home/data/repositories/category_products_repository.dart:6-22`; `lib/features/home/presentation/pages/widgets/category/category_products_page.dart:74-88,103-122` | UI sends skip/limit and appends pages, but Django `views_catalog.py:76-95` and PHP `api/getCategory.php:69-80,98-132` ignore pagination and return the full list. | Implement server pagination and page metadata; regression-test repeated pages and terminal/empty page. | Confirmed source contract defect; no live records read |
| STK-MOB-004 | MEDIUM | `/api/search`; `lib/features/search/data/repositories/search_repository.dart:6-28`; `lib/features/search/presentation/search_page.dart:73-79,97,123-182` | Search filters only loaded products locally; query text is not sent to the API. | Send query and filters to server and reset pagination on changes. | Confirmed source limitation |
| STK-MOB-005 | MEDIUM | `/api/cart_api_test`; `lib/features/cart/data/models/cart_model.dart:103-115` | Model expects `original_totol_Price` and `total_discount_amout`; backend/PHP response uses `original_total_price`, `product_discount_amount`, and `cart_discount_amount`. | Correct key mapping and define explicit total-discount semantics. | Confirmed model mismatch; these two properties are not currently read by `CartPage` |
| STK-MOB-006 | MEDIUM | `/api/noti_list`; `lib/features/notification/models/noti_list_response.dart:14-19`; `lib/features/notification/notification_page.dart:71-85`; `lib/features/notification/services/notification_storage.dart:8-24` | `is_read` is not parsed, read actions only update local state/storage, and local read IDs are not loaded. Backend supports PUT mark-read. | Parse read state and call the registered PUT mark-read contract. | Confirmed source defect |
| STK-MOB-007 | MEDIUM | `/api/product-api`; `lib/features/product/data/models/product_model.dart:135-136` | `set_contains` is cast to `List<String>` although both Django and PHP accept JSON object/dictionary values as well as lists. | Normalize list/map/null shapes or standardize server output. | Confirmed data-dependent parsing risk; DB values not inspected |
| STK-MOB-008 | MEDIUM | `/api/profile`; `lib/features/profile/data/models/profile_model.dart:33-41` | Strict non-null string casts conflict with nullable backend profile columns. | Use nullable-safe defaults and null fixture tests. | Confirmed data-dependent parsing risk; user rows not inspected |
| STK-MOB-009 | LOW | `/api/notify`; `lib/features/notification/services/notification_token_service.dart:10-23` | FCM device token is printed in clear text. | Remove or redact token logging. | Confirmed source risk |
| STK-MOB-010 | LOW | Inactive `/api/products`; `lib/core/constants/api_constants.dart:10` | Commented constant has no matching Django route. | Do not re-enable without adding a deliberate contract. | Confirmed inactive code only |
| STK-MOB-011 | LOW | `/api/contactus` and `/api/saveCheck`; `lib/core/constants/api_constants.dart:13,28`; `lib/features/cart/data/repositories/checkout_repository.dart:16-64` | No active UI caller found; saveCheck stores a checkout payload and does not create the actual order. | Confirm intended use; actual order placement remains `/api/order_post`. | Source observation; user impact unverified |

### Fresh verification results

- React tests **31/31 PASS**; lint **0 warnings/errors across 24 files**; production build **PASS (1,988 modules transformed)**.
- Selected database-independent Django/API contract tests **105/105 PASS**; `manage.py check` **PASS**; `migrate --check` **PASS**, no migration applied.
- Flutter `analyze --no-pub` **FAILED** due to stale package roots; Flutter `test --no-pub` **FAILED** during test compilation. These are failures, not passes.
- No live API or production endpoint was called. No database writes/schema changes, package installs, PHP edits, or Flutter edits occurred.

**Overall status remains PARTIAL until authenticated web and mobile workflows pass end-to-end.**


## Order creation and banner image re-verification — 2026-10-16

Status remains PARTIAL; neither user-reported workflow is marked fixed because authenticated end-to-end acceptance was not available. The Order form's sentence about server-side pricing and delivery coordinates is a styled informational paragraph in `admin_frontend/src/OrdersPage.jsx`, not an API error. The current form sends `address`, `city`, `state`, `postal_code`, and `country`; the backend re-reads Product/Variant prices, calculates totals with Decimal, rejects duplicate product/variant lines, and writes Checkout, OrderItem, and OrderStatusHistory inside `transaction.atomic()`. The database-free tests exercise server pricing, duplicate lines, variant validation, and transaction usage. A real authenticated create/list/financial-summary flow was not run because no approved isolated database-backed test environment was supplied; no live records were written.

Banner source trace: `BannersPage.jsx` uploads multipart field `file` to `/admin-api/uploads`, then PATCHes `/admin-api/banners` with `{id, image_path}` and reloads the list. Upload validation/storage and patch replacement/preserve-existing behavior pass the current database-free tests. A targeted mocked GET reproduced a non-debug URL mismatch: with an existing local file at `MEDIA_ROOT/uploads/replacement.png`, `DEBUG=False` still serializes `https://legacy.example/admin/manage/uploads/replacement.png` from `LEGACY_BASE_URL`, not a URL proven to serve the Django-local file. The current configuration only registers `/admin/manage/uploads/...` serving while `DEBUG=True`. Local settings currently have `DEBUG=True`, so the non-debug deployment risk is not evidence that the user's local failure has been reproduced. Production media serving/base URL configuration remains a blocker. No application source was changed and no database/schema operations were performed.

Verification: React tests 31/31 PASS; lint PASS (0 warnings/errors); Vite production build PASS; selected database-independent Django/API suite 105/105 PASS; Django system check PASS during tests. These are regression/unit checks only, not authenticated E2E acceptance.
