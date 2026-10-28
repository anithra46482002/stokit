# StokIt Complete Application Audit

**Audit date:** 2026-10-16 (local)  
**Workspace:** `C:\Users\.MSI\Downloads\StokIt Backend` (`stokit`)  
**Scope:** React/Vite admin, Django/DRF backend, PostgreSQL target, Flutter/PHP contract references.  
**Overall status: PARTIAL — not accepted as end-to-end working.**

## 1. Executive status

Fresh checks run during this audit: frontend tests **15/15 PASS**, Vite production build **PASS**, Oxlint **0 warnings / 0 errors**, `python manage.py check` **PASS**, Django test suite **93 tests, 0 failures, 1 expected failure**. A purpose-built read-only target verifier connected to PostgreSQL 18.6 database `stokit_postgres_dev`, schema `public`, and reported **43 base tables, 111 indexes, 8 user triggers, 20 migration records**. These checks establish static/unit/build health, not complete business workflow correctness.

**Important state drift:** the current live read-only verifier reports `admins=1` and business/application rows in `accounts_adminroleassignment=1`, `notifications=1`, `users=1`, `zg_category=1`, `zg_product=1`, `zg_product_images=1`, `zg_slider=1`, `zg_subcategory=1`, and `zg_variant=1`. Earlier reports described `admins=0` and no business rows. Treat the current observation as authoritative for this audit and the earlier statements as stale; this audit did not query or expose row contents and did not write to the target. Establish the origin/authorization of those rows before any reset, migration, or cleanup.

Still blocked/unverified: browser-driven end-to-end testing; authenticated UI/CRUD using an authorized test account; exact MariaDB-to-PostgreSQL collation parity; authoritative active PHP revision and runtime dependency confirmation; and proof that every Flutter contract has behavior-equivalent responses. Do not infer these from unit tests or static route presence.

## 2. Audit method and evidence

Inspected the current workspace tree, React route/module configuration, API client, Django root/admin/legacy URL declarations, authentication and role-permission code, PostgreSQL inventory/blocker reports, and the existing read-only target verifier. Executed only checks intended not to write application data: `npm test`, `npm run build`, `npm run lint`, `python manage.py check`, `python manage.py test --verbosity 1`, and `python scripts/read_only_audits/final_target_verify_readonly.py`. The database verifier sets the PostgreSQL connection read-only and rolls back. No migration, account creation, package installation, schema change, import, PHP/Flutter edit, or application-code edit was performed.

## 3. Confirmed findings and risks

### A-DB-001 — HIGH — live database state contradicts older reports
- **Evidence:** `django_backend/scripts/read_only_audits/final_target_verify_readonly.py` current output: `admins=1`; `accounts_adminroleassignment=1`; `users=1`; `notifications=1`; `zg_category=1`; `zg_product=1`; `zg_product_images=1`; `zg_slider=1`; `zg_subcategory=1`; `zg_variant=1`; migration records 20.
- **Impact:** safety assumptions about a blank/fresh target and absence of an admin/business data are no longer safe.
- **Fix:** reconcile audit logs, approved provisioning history, and row ownership using a separately approved read-only review. Do not delete or overwrite rows.
- **Regression:** rerun the read-only inventory after owner reconciliation and compare a recorded baseline.

### A-DB-002 — HIGH — schema/business contract and migration readiness are not proven by 43-table count
- **Evidence:** `STOKIT_COMPLETE_POSTGRESQL_SCHEMA_INVENTORY.md`, `STOKIT_SCHEMA_DECISIONS_BLOCKERS.md`, and `STOKIT_FULL_SCHEMA_AND_APPLICATION_EXECUTION_REPORT.md` explicitly retain conversion decisions around collation, ENUM-like fields, prefix indexes, timestamp update behavior, triggers, ID allocation, timezone, and source table dependencies. Current verifier confirms object counts, not semantic parity.
- **Impact:** valid-looking schema may still differ from legacy PHP/Flutter behavior under edge cases and concurrent writes.
- **Fix:** resolve each documented blocker with isolated test evidence and owner approval before any schema or application change.

### A-API-001 — HIGH — authenticated CRUD is not acceptance-tested
- **Evidence:** prior execution report records protected endpoint unauthenticated response 401, but authenticated browser CRUD is blocked by lack of an approved existing test account/tooling.
- **Impact:** UI authorization, token expiry, role mapping, and real DB writes are not end-to-end validated.
- **Fix:** use an already-authorized test account and approved browser automation; do not create an account as part of this audit.

### A-COMPAT-001 — HIGH — PHP provenance and legacy-table runtime dependencies remain unresolved
- **Evidence:** `STOKIT_FULL_SCHEMA_AND_APPLICATION_EXECUTION_REPORT.md` records only a 153-file PHP backup snapshot, not verified active deployed source; its dependency matrix reports references for excluded tables.
- **Impact:** absent tables or altered behavior may affect legacy admin/API routes even if Django unit tests pass.
- **Fix:** obtain authoritative deployed revision/hash manifest and owner decisions for all excluded tables; do not add tables based only on a backup literal reference.

### A-COMPAT-002 — HIGH — collation/equality parity unresolved
- **Evidence:** existing execution report says PostgreSQL candidate matching MariaDB case/accent/trailing-space semantics leaves 1 of 23 tested cases unmatched (trailing NBSP); current target does not contain the proposed evaluation collation.
- **Impact:** location matching, uniqueness, or duplicate acceptance can differ from legacy behavior.
- **Fix:** agree source-version semantics and NBSP policy; verify in disposable databases before proposing target changes.

### A-FE-001 — MEDIUM — frontend module presence is not proof of a complete workflow
- **Evidence:** `admin_frontend/src/App.jsx` declares dashboard, categories, subcategories, products, variants, customers, orders, banners, notifications, warehouses, cart discount, staff, advance payments/allocations, locations, targets and reports. API requests are abstracted through `fetchAll(api, endpoint, ...)` and module configuration; a simple literal `api.get/post` scan does not enumerate all dynamic calls.
- **Impact:** incomplete CRUD, incorrect field mapping, or missing loading/error behavior may evade isolated utility tests.
- **Fix:** build a route-by-route browser acceptance matrix and record HTTP request, payload, response, database effect, and UI result for every supported action.

### A-SEC-001 — MEDIUM — role enforcement requires endpoint-by-endpoint proof
- **Evidence:** `django_backend/adminapi/permissions.py` has resource/method-specific role rules; `django_backend/adminapi/auth.py` derives principal identity from signed token and role assignment. Static inspection confirms policy logic exists, not that every view attaches the intended permission/resource or that every role/method combination is correct.
- **Impact:** missing or incorrect per-view permission declarations could expose actions or deny legitimate users.
- **Fix:** inventory every admin view's authentication, permission class, required resource, HTTP methods, and role matrix; add positive and negative API tests for each combination.

### A-API-002 — MEDIUM — route registration does not prove request/response contract parity
- **Evidence:** root routes expose `/api/` legacy Flutter endpoints and `/admin-api/` React endpoints in `django_backend/config/urls.py`; legacy route declarations are in `legacy_api/urls.py`, admin routes in `adminapi/urls.py`. Static route presence does not establish exact payload keys, status codes, pagination, image URL shape, or side effects.
- **Fix:** compare each route to read-only PHP/Flutter contract references and test request/response schemas plus representative data cases in an isolated environment.

### A-TEST-001 — MEDIUM — automated tests do not cover full acceptance
- **Evidence:** current unit/build checks pass, but authenticated browser CRUD, all business workflows, concurrency, upload storage, and live Flutter contract tests remain unverified. One Django test is marked expected failure.
- **Fix:** retain expected-failure label until its cause and acceptance criterion are documented; add isolated integration and browser tests after tooling/account authorization.

### A-OPS-001 — LOW — repository root is not a Git worktree
- **Evidence:** `git status --short` from workspace root returned `fatal: not a git repository`.
- **Impact:** this workspace cannot provide normal Git diff/status evidence at its root; it does not prove there is no version control elsewhere.
- **Fix:** identify the authoritative source-control root before implementation changes and record baseline commit/hash.

## 4. Frontend → backend → database endpoint matrix

This is a **static route/module crosswalk**, not proof of successful live workflows. `App.jsx` module configuration points at these admin resources; the admin URLconf registers corresponding views. Table names below are dependencies to verify in view/model implementations and live catalog, not assertions that each endpoint has passed CRUD.

| Frontend module / action | React resource path | Django endpoint | Backend handler | Database / validation status |
|---|---|---|---|---|
| Login / refresh | auth flow | `/admin-api/auth/login`, `/admin-api/auth/refresh` | `adminapi.views` | Signed token + legacy admin/staff + role assignment; authenticated UI flow blocked |
| Dashboard | `dashboard` | `/admin-api/dashboard` | `DashboardView` | Aggregated business tables; live result contract not browser-tested |
| Categories | `categories` | `/admin-api/categories` | `CategoryCRUDView` | `zg_category`; CRUD acceptance not run |
| Subcategories | `subcategories` | `/admin-api/subcategories` | `SubcategoryCRUDView` | `zg_subcategory` / parent category relationship; FK and invalid-parent cases need integration tests |
| Products | `products` | `/admin-api/products` | `ProductCRUDView` | `zg_product`; field/type/relationship parity not end-to-end verified |
| Variants | `product-variants` | `/admin-api/product-variants` | `VariantCRUDView` | `zg_variant`; product relationship and numeric constraints need integration tests |
| Product images | `product-images` | `/admin-api/product-images` | `ProductImageCRUDView` | `zg_product_images`; upload-to-record URL contract needs browser test |
| Image upload | `uploads` | `/admin-api/uploads` | `ImageUploadView` | Media filesystem + returned `image_path`/`url`; actual upload and serving not verified in this run |
| Customers | `customers` | `/admin-api/customers` | `CustomerCRUDView` | `users`; current count 1, do not inspect sensitive values |
| Orders/list/update | `orders`, detail/status/manage/bulk-assign | `/admin-api/orders`, `/orders/manage`, `/orders/{id}/detail`, `/orders/{id}/status`, `/orders/bulk-assign` | `OrderAdminCRUDView`, `OrderManageView`, `OrderDetailView`, `OrderStatusView`, `OrderBulkAssignView` | Orders/order items/staff and status-history semantics need isolated transaction and concurrency tests |
| Banners | `banners` | `/admin-api/banners` | `BannerAdminView` | Legacy banner/slider schema mapping needs contract proof |
| Notifications | `notifications` | `/admin-api/notifications` | `NotificationAdminView` | `notifications`; current count 1, no row contents read |
| Warehouses | `warehouses` | `/admin-api/warehouses` | `WarehouseAdminView` | `zg_warehouse` and staff assignment relations need integration test |
| Inventory | `inventory` | `/admin-api/inventory` | `InventoryAdminView` | stock/product/warehouse/log consistency and concurrent updates unverified |
| Cart discount | `cart-discount-settings` | `/admin-api/cart-discount-settings` | `CartDiscountSettingsView` | `admin_cart_discount_settings`; table has 0 rows per verifier; protected unauthenticated response previously 401 |
| Staff | `staff` | `/admin-api/staff` | `StaffAdminView` | `salesmen`, `delivery_boys`, role assignment; credential/token flows need acceptance tests |
| Advance payments | `advance-payments` | `/admin-api/advance-payments` | `AdvancePaymentOffersView` | offer/allocation/transaction table relationships and balance invariants need tests |
| Advance allocations | `advance-allocations` | `/admin-api/advance-allocations` | `AdvanceAllocationAdminView` | allocation/credit ledger atomicity and concurrency unverified |
| Locations | `locations` | `/admin-api/locations` | `LocationAdminView` | `zg_location`; collation/equality blocker remains |
| Targets | `targets` | `/admin-api/targets` | `TargetAdminView` | targets/assignments/achievements and trigger behavior need tests |
| Reports | `reports` | `/admin-api/reports` | `ReportsAdminView` | Aggregation correctness and empty/large datasets not acceptance-tested |

### Legacy Flutter API route inventory

`django_backend/config/urls.py` mounts `legacy_api.urls` under `/api/`. Registered paths: `/login`, `/logout`, `/profile`, `/geocode`, `/banner`, `/category`, `/sub_categories`, `/getCategory`, `/search`, `/highlights`, `/recommended`, `/product-api`, `/fav`, `/favpage`, `/cart_action`, `/product-api-cart`, `/cart_api_test`, `/checkout`, `/noti_list`, `/notification_action`, `/notify`, `/order_post`, `/orders`, `/order_details`, `/order_cancel`, `/acc/`, `/acc/reset`, `/saveCheck`, `/targets`, `/coabout`, `/advancePay-api`, `/crd_rel`, `/contactus`. Source contract compatibility is not declared PASS without payload-level tests against the read-only Flutter/PHP references.

## 5. PostgreSQL state and integrity review

Current target verifier observed 43 public base tables, 111 indexes, 8 user triggers, 20 rows in `django_migrations`, no excluded-table names present, and no target `citext`/`unaccent` extension. It reported 1 row in `admins` and the non-empty table counts listed in the executive summary. The verifier checks inventory/row counts and selected catalog properties; this audit did **not** independently compare every column, key, constraint, index definition, sequence, trigger body, or live ORM query to every application path. Use the detailed existing inventory and blocker registers for the per-object conversion backlog.

## 6. Security, configuration, operations

- `admin_frontend/src/api.js` attaches a bearer token from `sessionStorage` and redirects to login when a response has the specific invalid/expired-token detail. Review token storage/XSS threat model and ensure secrets are never placed in Vite client variables.
- `adminapi/auth.py` uses Django signing with a configured maximum age and maps admin/salesman/delivery principals. Review token revocation, role-assignment failures, account-disabled state, and login rate limiting as separate acceptance/security tests.
- `adminapi/permissions.py` implements role/resource/method policy; ensure every protected view sets correct permission classes and `required_resource`.
- `config/urls.py` serves legacy uploads through Django only when `DEBUG` is true. Verify production media hosting, path traversal protections, file type/size limits, and orphan cleanup without deleting files during this audit.
- Do not print `.env` values or credentials in logs/reports. Database read-only verification succeeded; secrets were not included in this report.

## 7. Tests actually run

| Check | Result | Scope / limitation |
|---|---|---|
| `npm test` | PASS — 15/15 | Node unit tests; not browser E2E |
| `npm run build` | PASS | Vite production compilation; not runtime acceptance |
| `npm run lint` | PASS — 0 warnings/errors | Oxlint static checks |
| `python manage.py check` | PASS | Django system checks; not DB business CRUD |
| `python manage.py test --verbosity 1` | PASS — 93 tests; 1 expected failure | Django test suite; expected failure remains a coverage gap |
| `python scripts/read_only_audits/final_target_verify_readonly.py` | PASS — read-only query completed | Live PostgreSQL catalog/table counts; current data-state drift noted above |
| Browser E2E | NOT RUN / BLOCKED | Existing reports say browser automation tooling unavailable; no new dependency installed |
| Authenticated admin CRUD | NOT RUN / BLOCKED | No approved existing test account used in this run |
| Full Flutter/PHP contract test | NOT RUN | Requires authoritative active PHP reference and isolated API fixture data |

## 8. Prioritized remediation

### Critical / immediate safety gate
1. Reconcile the current live data-state discrepancy (`admins=1` and non-empty business tables) with approved change/provisioning history. Preserve rows; no cleanup without explicit approval.

### High
1. Obtain authoritative active PHP deployment revision and complete excluded-table dependency/owner decisions.
2. Resolve collation/equality and uniqueness behavior, including trailing NBSP, in disposable DB tests.
3. Run authenticated browser acceptance with an existing authorized account and approved tooling.
4. Validate role/method permissions for every admin view with allow/deny tests.
5. Verify critical write workflows (order placement/status, inventory, checkout/cart, credit allocation, target-progress triggers) under transaction and concurrency tests in an isolated database.

### Medium
1. Generate a mechanically complete route/payload matrix from every frontend call site and compare to DRF request/response serializers and PHP/Flutter contract.
2. Add integration coverage for category/subcategory/product/variant/image relationships, upload storage, pagination, validation errors, empty data, and server errors.
3. Verify CORS, DEBUG/media behavior, token expiry/revocation, login throttling, and secret handling against deployment configuration without disclosing secrets.

### Low
1. Identify authoritative Git root/commit for future diff evidence.
2. Track and resolve the existing expected-failure test or document why it is intentionally expected.

## 9. Dependencies and approvals

- Owner approval/evidence for live data-state reconciliation; do not modify existing rows.
- Authoritative active PHP source hash/commit and table-by-table scope decision.
- Approval of collation/NBSP and uniqueness policy before any target DDL.
- Existing authorized test account and approved browser automation for authenticated UI acceptance.
- Separate approval for any implementation fix, migration, schema change, data write, package installation, or cleanup.

## 10. Safe implementation and regression plan

1. Preserve this read-only snapshot and reconcile database row-count drift using approved audit history.
2. Obtain active PHP provenance; freeze Flutter/PHP contracts as read-only baselines.
3. Finalize the per-route contract matrix, including HTTP methods, request fields/types, response fields/types, permission/resource, database dependencies, and side effects.
4. Resolve schema blockers in disposable databases; run type/key/index/constraint/sequence/trigger comparisons and edge-case collation tests.
5. After explicit approval, implement one defect at a time in a branch/worktree with narrowly scoped changes and tests.
6. Run frontend unit tests/build/lint and backend system/unit tests after each change.
7. Run integration tests only against a disposable test database, including transaction rollback, FK violations, duplicate/concurrent requests, uploads and ledger invariants.
8. Run browser tests with an existing authorized account; capture console/network outcomes and verify database effects without using production/main DB for test writes.
9. Run read-only Flutter contract regression tests and compare all legacy response schemas.
10. Re-run the read-only catalog/data-state verifier, review diffs and evidence, then update this audit. Status remains PARTIAL until every acceptance gate is evidenced.

## 11. Single safest next step

**Reconcile the newly observed live database state with the owner before any further implementation or schema action.** The current target contains an admin row and several non-empty business tables despite earlier reports describing a blank target. Keep the database unchanged while establishing provenance and approval.


## Database provenance investigation addendum (2026-10-16)

**Status remains PARTIAL.** See `STOKIT_DATABASE_PROVENANCE_REVIEW.md` for the full evidence timeline and confirmed-vs-hypothesis analysis.

The prior provenance pass recorded 43 public tables, 111 indexes, 13 foreign keys, 8 user triggers, 20 migration records, and ten non-empty application tables, alongside framework rows `auth_permission`=128, `django_content_type`=32 and `django_migrations`=20. This was an earlier point-in-time snapshot and is superseded by the newer continuation execution update in Section 11 below, which records 19 non-empty tables. No sensitive row values were read.

The older `STOKIT_POSTGRESQL_TARGET_READONLY_AUDIT.md` and `STOKIT_BACKUP_RESTORE_GATE_REPORT.md` describe an earlier 3-table/1-migration snapshot with `admins`=0. The later full execution report documents 43-table provisioning and 19 additional migrations but also claims application/business tables remained empty. That claim is inconsistent with the current point-in-time counts and must be treated as stale or unresolved. Current migration ledger: 20 records, one dated 2026-10-15 and 19 returned as 2026-10-16 04:03:28 +05:30. Historical report timestamps may be UTC-naive, so exact chronology needs timezone normalization.

PostgreSQL metadata does not provide reliable per-table creation timestamps or row-writer identity. Current `log_statement=none` and `log_min_duration_statement=-1` mean statement-level write history cannot be assumed. The inspected migration directories had no `RunPython`, `RunSQL`, `INSERT INTO`, `objects.create`, or `bulk_create` matches; this does not exclude writes from other code, triggers, manual SQL, external clients, or scripts. Provenance of the business rows and admin row is **not established**. No fix or database change was attempted. Safest next action: preserve the target and ask the owner/DBA to reconcile the provisioning window against authorized operation history; do not delete, reset, restore, or rerun migrations.


## Continuation execution update (2026-10-16)

### Fresh read-only baseline

A new execution of `python scripts/read_only_audits/final_target_verify_readonly.py` again confirmed PostgreSQL 18.6, `stokit_postgres_dev.public`, 43 public base tables, 111 indexes, 8 user triggers, and 20 migration records. The verifier now reports 19 non-empty tables: `accounts_adminroleassignment`=1, `admins`=1, `advance_pay_allocations`=1, `advance_pay_offers`=1, `auth_permission`=128, `delivery_boys`=1, `django_content_type`=32, `django_migrations`=20, `notifications`=1, `salesmen`=1, `users`=1, `zg_category`=1, `zg_location`=1, `zg_product`=1, `zg_product_images`=1, `zg_slider`=1, `zg_subcategory`=1, `zg_variant`=1, and `zg_warehouse`=1. No row values were read. This supersedes the earlier point-in-time list of ten non-empty application tables; it does not establish when, why, or by whom the additional records were written.

### Checks actually executed in this continuation

| Check | Result | Limitations |
|---|---|---|
| `npm test` in `admin_frontend` | PASS — 15/15 | Unit tests only, not browser E2E. |
| `npm run lint` in `admin_frontend` | PASS — 0 warnings/errors | Static lint only. |
| `npm run build` in `admin_frontend` | PASS — Vite production build | Generated `admin_frontend/dist` output; does not prove runtime acceptance. |
| `python manage.py check` in `django_backend` | PASS — no issues | Django system checks only. |
| `python manage.py migrate --check` | PASS — exit 0 | No migration was applied. |
| `python manage.py showmigrations --plan` | PASS — all 20 listed migrations marked applied | Does not explain arbitrary data writes or prove semantic schema parity. |
| Database-independent Django test selection | PASS — 74 tests, 1 expected failure | Test runner did not set up a database; the expected failure is the documented city-collation parity gap. |
| `python scripts/read_only_audits/final_target_verify_readonly.py` | PASS — read-only inventory/count query | Current counts reveal additional non-empty application tables; provenance remains unknown. |

A source fingerprint was recalculated after the code-only fixes for 108 source files across `admin_frontend/src` and the Django application/configuration packages. Aggregate SHA-256 of sorted relative-path/file-hash entries joined with newline characters: `4437abb57baeb91dfb5747b31b0c6af3d05ecfc973f51509041a77a6d90e6631`. No `.git` marker was found at the workspace root, `admin_frontend`, or `django_backend`, so a commit/diff baseline is unavailable in those locations.

### Code changes and remaining phase gates

During the initial audit, no application source defect was confirmed that could safely be corrected without an unresolved policy/schema/provenance/test-environment decision. The subsequent continuation identified and fixed STK-AUD-017, documented below. Other issues such as city-collation parity, order write/delete policy, active PHP provenance, excluded-table scope (`zg_product_warehouse` included), and authenticated CRUD still require evidence/approval.

Database actions: read-only inventory/catalog/count queries and `migrate --check` only; no DDL, DML, migration, account creation, import, restore, or cleanup. PHP and Flutter remain untouched.

**Overall status remains PARTIAL.** Continue with approved isolated integration/browser testing and owner-led provenance/scope decisions before claiming completion.

## Continuation: code defect and API map (2026-10-16)

### Confirmed code-only defect fixed

`STK-AUD-017` was confirmed in `admin_frontend/src/uiUtils.js`: `fetchAll` requested only page 1 with `page_size=100`, despite callers using it to populate full related-record collections. Above 100 matching records, form choices could be silently incomplete. The helper now follows successive pages, preserves caller filters, and stops when backend `count` is satisfied or a short/empty page is returned. Regression tests were added in `admin_frontend/src/uiUtils.test.js` for a 101-row, two-page response and a short page without count metadata. Actual post-fix result: `npm test` PASS 17/17. No other confirmed code-only defect was changed; unresolved business policy and schema risks were not speculatively modified.

### Static API contract coverage

Created `STOKIT_API_CONTRACT_MATRIX.md` to map current React resource calls to the DRF route handlers and enumerate registered Flutter-facing `/api/*` paths. It explicitly distinguishes static route mapping from payload-level behavioral parity. The frontend routes include auth, dashboard/reports, catalog CRUD, customers, order lifecycle, banners, notifications, warehouses/inventory, discounts, staff, advance payments/allocations, locations, targets and uploads. The legacy route map includes auth/profile/geocode, catalog/search, favorites, cart/checkout, notifications, orders, password reset, targets, about and finance endpoints.

`zg_product_warehouse` remains excluded from the live target and has no confirmed Django equivalent. The available PHP backup contains references in product/warehouse management, but it is not verified as the active deployment. The owner must approve table scope and relationship design before any schema/API implementation. City collation remains blocked: the tested candidate retains a trailing-NBSP mismatch and no target schema change was made.

### Post-fix test results

| Check | Actual result | Limits |
|---|---|---|
| React tests | PASS — 17/17 | Unit tests; no browser E2E |
| Oxlint | PASS — 0 warnings/errors | Static lint |
| Vite build | PASS | Does not prove runtime/API correctness |
| Django `check` | PASS | System checks only |
| Django `migrate --check` | PASS — exit 0 | No migration applied |
| Django selected DB-independent suite | PASS — 74 tests, 1 expected failure | No default test DB setup; expected failure is city collation |
| Read-only PostgreSQL verifier | PASS | 43 tables, 111 indexes, 8 user triggers, 20 migrations, 19 non-empty tables; no row values inspected |

No authenticated CRUD, full frontend-to-backend integration, or full Flutter/PHP payload parity test was run. No main database writes, schema changes, migrations, account creation, imports, restores, or cleanup occurred. Overall status remains **PARTIAL**.

## Continuation: confirmed fixes and acceptance evidence (2026-10-16)

### Additional code-only defects fixed

- STK-AUD-017: hardened fetchAll pagination. It preserves filters and follows count/page-size pagination, stops on empty/short pages where appropriate, rejects an early end that contradicts count metadata, detects repeated full pages with or without count metadata, and throws after 1,000 pages instead of permitting an unbounded loop.
- STK-AUD-018: ProductCRUDView POST/PATCH now parses subcategory IDs as integers and returns 400 for malformed IDs; PATCH preserves the create-time category/subcategory invariant. Category changes are rejected if the existing subcategory does not belong to the new category.
- STK-AUD-019: Variant PATCH validates GST as Y/N and discount as finite 0–100, and product/variant numeric paths reject non-finite or negative monetary values.
- STK-AUD-020: Variant create/update now requires a finite whole-number quantity instead of silently truncating fractional JSON numbers.

### Tests actually run after these changes

| Check | Result | Scope |
|---|---|---|
| admin_frontend npm test | PASS — 24/24 | Includes pagination count/filter, empty/short page, repeated page, missing metadata and 1,000-page cap regressions |
| admin_frontend npm run lint | PASS — 0 warnings/errors | Oxlint scanned 23 files |
|| Django test suite | PASS — 116 tests, 1 expected failure | Expected failure remains city-collation parity; no test database setup was reported by the runner |
| python manage.py check | PASS | No system-check issues |
| python manage.py migrate --check | PASS | No migration applied |
| scripts/read_only_audits/final_target_verify_readonly.py | PASS | Read-only query only; 43 tables, 111 indexes, 8 user triggers, 20 migration rows, 19 non-empty tables |

### API contract matrix expansion

STOKIT_API_CONTRACT_MATRIX.md now includes source-derived request/query fields, response fields, validation limits and permission classes for the main React admin endpoints, plus the current role/resource summary. It labels untested behavior explicitly. The matrix does not claim full API parity: the Flutter-facing /api/* endpoints still need payload/status/side-effect comparisons against the authoritative active PHP revision and Flutter call sites.

### Remaining open acceptance gates

- STK-AUD-001 / STK-AUD-015 / STK-AUD-016: owner/DBA reconciliation of existing populated tables and row provenance.
- Authoritative active PHP deployment revision and scope decisions for excluded tables, especially zg_product_warehouse.
- Owner-approved collation/NBSP policy and isolated parity evidence.
- Approved isolated integration database, disposable fixtures and already-authorized test accounts/roles.
- Authenticated browser CRUD, role/method allow-deny tests, API response contracts, uploads/media, concurrency and transaction assertions.
- Business-owner decisions for order deletion/status transitions, inventory warehouse scoping, credit ledger behavior and any other unresolved business rules.
- Expected-failure city-collation test resolution or owner acceptance.

No target data/schema changes, migrations, imports, restores, account creation, package installs, cleanup, PHP edits or Flutter edits were performed. Current read-only inventory matches the previous count map. Status remains PARTIAL.

## Continuation  -  Target Scheme, reward image upload, and cart discount safety (2026-10-16)

### Confirmed root causes and code fixes

- **STK-AUD-021  -  Target Scheme category ID.** The generic select could display its first option while form state lacked category_id; related categories were also limited to the first page. Target Scheme now loads all category pages, uses category IDs as option values, initializes create/edit state, and normalizes the submitted value to a positive safe integer. Category names are never submitted as IDs.
- **STK-AUD-022  -  Reward image upload.** The field was configured as text and did not invoke the reusable upload flow. It is now an image-only upload control with current/new preview, JPG/PNG/GIF/WEBP and 5 MB client checks, status/error feedback, and persistence of the returned relative image_path. Existing paths/URLs remain previewable; server signature/extension/size checks remain authoritative.
- **STK-AUD-023  -  Cart discount stacking.** product_has_discount documented but ignored has_disc; the cart query omitted product_discount and the customer VIP flag/percentage was not used to suppress stacking. The shared rule now considers the discount flag and known discount columns. The cart API derives eligibility from server-side cart/product/customer records, excludes discounted lines, disables the cart promotion for active VIP customers, calculates VIP amount from stored percentage, and preserves response keys.

The React admin cart-discount screen now states that eligibility is server-derived and promotions do not stack. PHP and Flutter were not modified.

### Tests actually executed

| Check | Result |
|---|---|
| React unit tests | PASS  -  27/27 |
| Oxlint | PASS  -  0 warnings/errors, 23 files |
| Vite production build | PASS |
| Targeted Django tests (targets, uploads, cart discount, shared rules, legacy cart contract) | PASS  -  46/46 |
| Full Django suite | PASS  -  126 tests, 1 expected failure (city-collation parity) |
| python manage.py check | PASS |
| python manage.py migrate --check | PASS; no migration applied |

Tests are unit/pure tests; upload tests use temporary media storage. No authenticated browser workflow or cart endpoint against database fixtures was executed.

### Remaining limitation

The customer cart endpoint retains legacy hard-coded promotion settings (minimum order value 14,000 and 10% cart discount). The React cart-discount-settings endpoint stores a separate fixed-amount configuration and is not wired into /api/cart_api_test. Whether that setting should replace the legacy promotion requires a business decision because percentage-vs-fixed-amount and threshold semantics differ. No schema/database changes were made. Status remains PARTIAL.

## Banner, Maps and Order Management continuation (2026-10-16)

See STOKIT_BANNER_MAPS_ORDER_AUDIT.md for file-level findings and exact blockers. Source changes cover banner image preview/validation, warehouse place search fallback/map preview, admin order creation with server-priced lines and role validation, one-sided date filters, and delivery-boy filtering. Verification: frontend 27/27, lint 0 warnings/errors, build 1,988 modules; full Django 139 tests with 1 expected failure; check, migrate --check and Python compilation passed. Authenticated DB-backed upload/place/order workflows remain BLOCKED. Google Places key/configuration is absent; OpenStreetMap fallback is used. No live database/schema changes and PHP/Flutter unchanged. Overall status PARTIAL.


## Full project and API audit continuation — 2026-10-16

- Added `STOKIT_COMPLETE_API_AUDIT.md` with a static inventory of 26 `/admin-api/` patterns and 33 `/api/` patterns (59 total), React and Flutter call-site mappings, status for every route, source-derived contract notes, security/configuration observations and cleanup classifications. All routes remain NOT VERIFIED for authenticated isolated E2E; route registration is not success evidence.
- Audited React/Vite entry points and Axios configuration, Django settings/routes/handlers/tests, Flutter `ApiConstants`, Dio/auth service and feature repositories, and available read-only PHP reference. No Git metadata was found at the workspace root. Environment values were not read or printed.
- Fixed the Flutter/Django search method/filter mismatch in Django only: POST JSON now accepts min/max price, allowlisted sort, skip and limit while legacy GET search remains supported. Four database-free regression tests pass; Flutter/PHP remain unchanged and E2E remains NOT VERIFIED.
- Confirmed `/api/coabout` emits placeholder example.com URLs, Flutter logout is local-only in inspected code, and no Flutter notification mark-read call was found. These are documented, not silently changed.
- Safe cleanup after audit: initial pass removed 10 generated Python `__pycache__` directories (74 `.pyc` files); after tests regenerated caches, final post-test cleanup removed 9 more directories (63 `.pyc` files). Final scan found 0 source-tree cache directories outside `.venv`. No source/data/config/upload/migration/backup/PHP/Flutter files or databases were deleted.
- Overall status remains PARTIAL; no authenticated CRUD/browser or live database write verification was performed.


## Local web/mobile verification continuation — 2026-10-16

- Reconnected Cody to `stokit` and reran React tests (27/27), lint (0 warnings/errors), Vite production build (1,988 modules), Django system check, `migrate --check` without applying migrations, and selected Django database-independent tests (80/80). Flutter/Dart CLI unavailable; no install attempted.
- Local smoke probes: React `/login` returned HTTP 200 HTML; local read-only `GET /api/banner` returned HTTP 200 JSON; unauthenticated `GET /api/category` and `/admin-api/dashboard` returned HTTP 401. No credentials were used, and no write endpoints were called.
- The Flutter app's configured API base is production `https://app.stokitb2b.com/api`; no production API calls were made. Local smoke tests do not prove successful authenticated mobile or web workflows. Overall status remains PARTIAL.

## Order creation, financial summary, and banner regression continuation (2026-10-16)

### Code-level changes made

- `admin_frontend/src/OrdersPage.jsx` and `orderUtils.js`: added product-variant selection, variant-aware estimated totals and payload, and pre-submit validation for missing/invalid variants and duplicate product/variant lines. Backend validation errors containing arrays or nested objects are now readable through `uiUtils.js::errorText`.
- `django_backend/adminapi/crud.py`: order creation now requires a variant when the selected product has variants, verifies the variant belongs to the selected product, and continues to calculate totals from database prices inside the existing atomic checkout/item/status-history workflow.
- `django_backend/adminapi/finance.py`, `views.py`, `operations.py`, and `order_pages.py`: centralized normalized completed/open status semantics; dashboard and report revenue now recognize only delivered/fulfilled statuses regardless of case/whitespace; Order Management revenue excludes pending, cancelled and failed orders, and its pending count covers configured open statuses. The aggregate query uses DISTINCT order IDs and parameterized status placeholders.
- `django_backend/adminapi/order_pages.py`: GET `/admin-api/orders/manage` no longer updates `zg_checkout.view`; a read request must not mutate existing order records. Date filters reject impossible calendar dates and use an exclusive next-day boundary to include fractional timestamps on the selected end date.
- Existing banner upload/PATCH code remains unchanged in this continuation; its temporary-media and mocked path-persistence regression tests were rerun. Old image files are not deleted during replacement.

### Files changed in this continuation

- `admin_frontend/src/OrdersPage.jsx`
- `admin_frontend/src/orderUtils.js`
- `admin_frontend/src/orderUtils.test.js` (new)
- `admin_frontend/src/uiUtils.js`
- `admin_frontend/src/uiUtils.test.js`
- `django_backend/adminapi/finance.py` (new)
- `django_backend/adminapi/crud.py`
- `django_backend/adminapi/views.py`
- `django_backend/adminapi/operations.py`
- `django_backend/adminapi/order_pages.py`
- `django_backend/adminapi/tests_ui_workflows.py`
- `django_backend/adminapi/tests_dashboard_categories.py`
- `django_backend/legacy_api/tests_postgres_sql.py` (test expectation updated for exclusive next-day filtering)
- `django_backend/docs/STOKIT_DEFECT_REGISTER.md`
- `django_backend/docs/STOKIT_API_CONTRACT_MATRIX.md`
- `django_backend/docs/STOKIT_COMPLETE_APPLICATION_AUDIT.md`
- `django_backend/docs/STOKIT_COMPLETE_API_AUDIT.md`
- `django_backend/docs/STOKIT_PROJECT_COMPLETION_CHECKLIST.md`

### Actual test results

| Check | Result | Evidence limit |
|---|---|---|
| `npm test` | PASS — 31/31 | Unit tests; no browser/API E2E |
| `npm run lint` | PASS — 0 warnings/errors, 24 files | Static analysis |
| `npm run build` | PASS — 1,988 modules transformed | Build is not runtime acceptance |
| Selected Django/API contract suite | PASS — 105/105 | Database-independent/mocked tests; no isolated PostgreSQL workflow |
| `python manage.py check` | PASS — no issues | System checks only |
| `python manage.py migrate --check` | PASS — no migration applied | Consistency check only |

### Acceptance still blocked

- Authenticated order creation with PostgreSQL commit/rollback and readback in Order Management.
- Financial summary comparison against the same approved isolated PostgreSQL fixtures, including mixed statuses, date ranges, duplicates and empty data.
- Banner upload → PATCH → persisted reload → browser image-serving/refresh test.
- No approved isolated PostgreSQL fixture database or authorized test identities were supplied; no target database writes were made. The test suite was selected to avoid test-database creation. No PHP/Flutter source, package installs, migrations, DDL, DML, imports, restores, accounts, or destructive cleanup were performed.

**Status remains PARTIAL.**

### Banner media-serving component follow-up

The temporary-MEDIA_ROOT upload regression now also calls Django's `serve` view and verifies the uploaded PNG bytes can be read back; focused `adminapi.tests_uploads` result: **5/5 PASS**. The app's actual `/admin/manage/uploads/...` URL route and authenticated banner-row save/reload/browser refresh remain unverified. The current local configuration reports `DEBUG=True`, under which `config.urls` registers that development media route. Production media routing remains a deployment acceptance gate.
