# STOKIT Project Completion Checklist

**Review date:** 2026-10-16  
**Workspace:** `C:\Users\.MSI\Downloads\StokIt Backend` (`stokit`)  
**Frontend:** React + Vite (`admin_frontend`)  
**Backend:** Django + Django REST Framework (`django_backend`)  
**Database:** PostgreSQL 18.6, `stokit_postgres_dev.public`  
**Overall status: PARTIAL — production readiness and end-to-end acceptance are not proven.**

## 1. Verified baseline

### Source baseline
- Source fingerprint recalculated after this continuation: 108 files across `admin_frontend/src` and Django `accounts`, `adminapi`, `legacy_api`, `legacydb`, and `config` source trees. Aggregate SHA-256 of sorted relative-path/file-hash entries joined with newline characters: `4437abb57baeb91dfb5747b31b0c6af3d05ecfc973f51509041a77a6d90e6631`.
- No `.git` marker was found at workspace root, `admin_frontend`, or `django_backend`; a commit/diff baseline is unavailable from those locations.
- Code-only fixes changed `admin_frontend/src/uiUtils.js`, `admin_frontend/src/uiUtils.test.js`, `django_backend/adminapi/crud.py`, and added `django_backend/adminapi/tests_crud_validation.py`. The Vite build regenerated `admin_frontend/dist`. Django source changes did not require a migration; PHP and Flutter stayed read-only.
### Database and migration baseline
- Read-only verifier identity: PostgreSQL 18.6, database `stokit_postgres_dev`, schema `public`.
- 43 public base tables, 111 indexes, 8 non-internal/user triggers, 20 migration records. The latest `showmigrations --plan` output marks all 20 migrations applied; `migrate --check` exited 0.
- Latest verifier reports 19 non-empty tables: `accounts_adminroleassignment`=1, `admins`=1, `advance_pay_allocations`=1, `advance_pay_offers`=1, `auth_permission`=128, `delivery_boys`=1, `django_content_type`=32, `django_migrations`=20, `notifications`=1, `salesmen`=1, `users`=1, `zg_category`=1, `zg_location`=1, `zg_product`=1, `zg_product_images`=1, `zg_slider`=1, `zg_subcategory`=1, `zg_variant`=1, `zg_warehouse`=1. No row values were queried.
- The six additional application tables relative to the earlier provenance list are newly observed in the latest count map; the count comparison does not establish their creation time, writer, purpose, or authorization. Preserve every existing record. See `STOKIT_DATABASE_PROVENANCE_REVIEW.md`.
- Target database access in this continuation was read-only for catalog/count checks. No DDL, DML, migration, restore, import, account creation, or cleanup was performed.

## 2. Work completed in this continuation

- [x] Read `STOKIT_COMPLETE_APPLICATION_AUDIT.md`, `STOKIT_DEFECT_REGISTER.md`, `STOKIT_DATABASE_PROVENANCE_REVIEW.md`, and relevant schema/collation/PHP provenance/acceptance documents.
- [x] Re-run frontend tests, lint, and production build.
- [x] Run Django system check and migration consistency check.
- [x] Run 74 database-independent Django tests; the runner did not set up the default database.
- [x] Re-run read-only PostgreSQL inventory and row counts; document the newer point-in-time discrepancy.
- [x] Update the three audit documents and this completion checklist.
- [x] Preserve status PARTIAL and keep PHP/Flutter read-only.
- [ ] Confirmed application code fix with regression test: **none made**; no safe code-only defect was proven by this continuation's checks. Do not interpret that as proof the application has no defects.

## 3. Tests actually executed

| Test/check | Result | Evidence limits |
|---|---|---|
| `npm test` in `admin_frontend` | PASS — 17/17 | Includes pagination regression tests; no browser E2E. |
| `npm run lint` | PASS — 0 warnings/errors | Oxlint static analysis. |
| `npm run build` | PASS | Vite compilation; not runtime/API acceptance. |
| `python manage.py check` | PASS — no issues | System checks only. |
| `python manage.py migrate --check` | PASS — exit 0 | No migration applied; does not prove business behavior or provenance. |
| `python manage.py showmigrations --plan` | PASS — 20 marked applied | Migration ledger only. |
| Selected database-independent Django tests | PASS — 74 tests, 1 expected failure | Expected failure is the documented city-collation parity gap. No default database setup. |
| `python scripts/read_only_audits/final_target_verify_readonly.py` | PASS — read-only query | Inventory/counts only; no row content, write provenance or authorization established. |
| Full Django suite | NOT RUN in this continuation | Avoided because test-database creation/deletion was not approved. Historical results must remain labeled historical. |
| Browser E2E / authenticated CRUD | BLOCKED / NOT RUN | Requires approved isolated environment, authorized existing test accounts, and approved browser tooling. |
| Full React-to-DRF endpoint contract suite | NOT COMPLETE | Current unit/route tests cover selected contracts, not every workflow or database effect. |
| Flutter/PHP behavior parity | NOT COMPLETE | No authoritative active PHP revision and no complete payload-level parity evidence. |

## 4. Acceptance criteria and status

| ID | Acceptance criterion | Status | Evidence required to close |
|---|---|---|---|
| AC-01 | Current source/schema/migration/test baseline recorded | PARTIAL | Source fingerprint recalculated for 107 files and read-only verifier rerun; authoritative VCS root/commit is unavailable, and semantic schema parity is still unverified. |
| AC-02 | Critical/high confirmed application defects fixed or owner-accepted | PARTIAL | STK-AUD-017 pagination termination, STK-AUD-018 product category/subcategory validation, STK-AUD-019 finite numeric/GST/discount validation, and STK-AUD-020 whole-number quantity validation fixed with regression tests; provenance, policy, schema and E2E blockers remain. |
| AC-03 | Every React workflow traced React → API → DRF → PostgreSQL → response → React | PARTIAL | Static resource/handler map created in `STOKIT_API_CONTRACT_MATRIX.md`; request/response/database-effect proof for every workflow still requires isolated integration tests. |
| AC-04 | Authentication and authorization verified for every role/method/resource | OPEN | Positive and negative tests for all roles and routes using authorized synthetic accounts in approved isolated environment. |
| AC-05 | Flutter API compatibility preserved and verified | BLOCKED | Authoritative PHP deployed-source hash/revision plus route-level path, method, auth, payload, type, status, error and behavior parity tests. Flutter/PHP source remains unchanged. |
| AC-06 | Database schema, keys, constraints, indexes, triggers, sequences and model/query parity verified | PARTIAL | Full catalog-to-model comparison and isolated regression evidence. No DDL/migration on main target. |
| AC-07 | Database row provenance and authorization reconciled | BLOCKED | Owner/DBA-approved evidence for existing admin/business rows, timing and origin. No claim of provenance from counts alone. |
| AC-08 | City collation/equality/uniqueness matches required legacy behavior | BLOCKED | Owner policy for case/accent/trailing spaces/NBSP; parity tests on an approved isolated environment, ideally MariaDB 11.8.9. |
| AC-09 | Excluded table scope approved, including `zg_product_warehouse` | OPEN | Authoritative source dependency trace and owner decision for every excluded table. |
| AC-10 | Authenticated browser CRUD passes | BLOCKED | Approved isolated stack, authorized existing synthetic accounts, approved browser tooling, network/console assertions and database-effect checks. |
| AC-11 | Backend, frontend, lint, build, contract and security regression suites pass | PARTIAL | Re-run full suites in approved isolated environment; resolve/document expected failure; add complete API contract, permission, validation, upload, rollback and concurrency tests. |
| AC-12 | No unexplained failures or unapproved database changes remain | BLOCKED | Provenance reconciliation and owner/DBA confirmation; maintain audit trail. |
| AC-13 | Backup and restore of accepted state verified | OPEN | Owner approval for backup/restore operation and isolated restore test. Existing historical backup report is not a fresh accepted-state restore. |
| AC-14 | Final documentation and owner sign-off complete | OPEN | Close/accept each high-severity blocker with evidence; obtain written owner sign-off. |

## 5. Open blockers, defects and approvals

| Priority | Blocker | Required decision / evidence |
|---|---|---|
| HIGH | `STK-AUD-001` / `STK-AUD-015` / `STK-AUD-016`: database state/provenance discrepancy | Owner/DBA-led read-only reconciliation of current non-empty tables against approved operation history. Preserve all rows. |
| HIGH | Active PHP deployment revision is unverified | Owner supplies deployed commit/tag, hash manifest or hosting export. Backup snapshot alone is not authoritative. |
| HIGH | Legacy excluded-table scope | Owner decides each excluded table after authoritative source trace; explicitly include/exclude `zg_product_warehouse`. |
| HIGH | Collation parity | Owner approves behavior for case, accents, trailing spaces and NBSP; then test only in isolated environment. |
| HIGH | Authenticated CRUD and browser E2E | Approval for isolated test environment, test fixtures/accounts and browser automation. Do not create them until approved. |
| HIGH | Permission/business policy | Owner decides order creation/deletion/soft-delete behavior, role escalation rules and any policy inconsistencies before code changes. |
| MEDIUM | Endpoint contract coverage | Build complete React/DRF/PHP/Flutter contract matrix and run tests against isolated fixtures. |
| MEDIUM | Full backend suite | Approval for isolated test DB lifecycle; do not point test writes at `stokit_postgres_dev`. |
| MEDIUM | Schema-level changes | Any required DDL/migration needs a separate exact SQL/migration proposal, impact analysis, backup/rollback plan, and regression tests; leave unapplied until approved. |
| MEDIUM | Existing expected failure | City-collation expected failure remains until policy and parity strategy are approved and validated. |

## 6. Non-negotiable safety gates

- [x] No PHP or Flutter source changes.
- [x] No target database writes, DDL, migrations, account creation, imports, restore, or cleanup in this continuation.
- [x] No secrets or row values exposed.
- [x] No test database setup occurred in the selected 74-test run.
- [ ] No database schema/data change until separate explicit approval.
- [ ] No test database, test account, or temporary resource creation/deletion until approval.
- [ ] No COMPLETE status while any applicable acceptance criterion remains open or blocked.

## 7. Safest next action

Keep the target unchanged and ask the project owner/DBA to reconcile the 19-table non-empty count map against authorized provisioning/application/agent history, without exposing row contents. In parallel, obtain authoritative PHP deployment provenance and written decisions on excluded-table scope and collation policy. Once approved, run the full integration and authenticated browser acceptance suite only in an isolated environment. Keep status **PARTIAL** until all applicable criteria are evidenced.

## 8. Continuation update — confirmed pagination fix (2026-10-16)

### Code change and regression test

- **Confirmed defect:** `STK-AUD-017`, `admin_frontend/src/uiUtils.js::fetchAll` returned only page 1 (up to 100 rows), even though callers use it as a full related-record loader. This could silently omit options for collections over 100 rows.
- **Fix:** `fetchAll` now loops over pages of 100, retains caller filters, and stops when backend `count` is satisfied or a short/empty page arrives.
- **Files changed:** `admin_frontend/src/uiUtils.js`, `admin_frontend/src/uiUtils.test.js`.
- **Regression tests added:** 101 rows across two pages; stop after a short page when count metadata is absent.
- **Actual result:** `npm test` PASS 17/17 after the change. `npm run lint` PASS (0 warnings/errors), `npm run build` PASS.
- No backend, PHP, Flutter, schema or database source/data was changed for this fix.

### Fresh post-fix checks

| Check | Actual result | Notes |
|---|---|---|
| React unit tests | PASS — 17/17 | Includes the new pagination regressions. |
| Oxlint | PASS — 0 warnings/errors | 23 files scanned. |
| Vite production build | PASS | Build output generated under `admin_frontend/dist`. |
| Django system check | PASS | No issues. |
| Django migration consistency | PASS — `migrate --check` exit 0 | No migration applied. |
| Selected database-independent Django tests | PASS — 74 tests, 1 expected failure | No default database setup; expected failure is the city-collation gap. |
| Read-only target verifier | PASS | 43 tables, 111 indexes, 8 user triggers, 20 migration rows; 19 non-empty tables in latest snapshot. |
| `showmigrations --plan` | PASS — all 20 marked applied | Ledger state only. |

### Current safe scope and blockers

- Created `STOKIT_API_CONTRACT_MATRIX.md` with static React-resource-to-DRF handler mapping and registered `/api/*` Flutter-facing route mapping. It explicitly does not claim payload-level legacy parity.
- `zg_product_warehouse` remains excluded and requires owner decision; available PHP backup has product/warehouse references, but active deployment provenance is unverified.
- Added a DBA reconciliation checklist and a non-applied city-collation compatibility proposal to `STOKIT_DATABASE_PROVENANCE_REVIEW.md`.
- Remaining blockers: database row provenance, authoritative PHP deployment source, full contract/role matrix, approved isolated test DB and authorized test accounts, authenticated browser E2E, city collation policy/parity, excluded-table scope, full backend integration/concurrency tests, and owner sign-off.
- No database writes, DDL, migrations, imports, restores, account creation, package installs or cleanup. PHP and Flutter stayed read-only.

**Status remains PARTIAL.** The pagination defect is fixed with passing regression tests; the project is not COMPLETE until all applicable acceptance criteria are verified.

## Continuation update — pagination and CRUD validation (2026-10-16)

### Confirmed fixes

- STK-AUD-017: pagination detects repeated full pages, enforces a 1,000-page safety limit, preserves filters and raises explicit errors if pagination ends before the reported count is reached. Frontend regression suite covers 24 cases.
- STK-AUD-018: product POST/PATCH parses subcategory IDs and enforces category/subcategory consistency.
- STK-AUD-019: variant PATCH validates GST as Y/N and discount as finite 0–100; product/variant numeric paths reject non-finite or negative amounts.
- STK-AUD-020: variant create/PATCH rejects fractional quantities rather than truncating them. Ten database-free CRUD validation tests pass.

### Actual checks from this continuation

| Check | Result |
|---|---|
| React unit tests | PASS — 24/24 |
| Oxlint | PASS — 0 warnings/errors; 23 files scanned |
| Vite production build | PASS |
|| Django tests | PASS — 116 tests, 1 expected failure (city-collation parity); no test database setup reported |
| Django system check | PASS |
| Django migrate --check | PASS; no migration applied |
| Read-only PostgreSQL verifier | PASS; same observed state: 43 tables, 111 indexes, 8 user triggers, 20 migrations, 19 non-empty tables |

### Contract documentation and blockers

STOKIT_API_CONTRACT_MATRIX.md now records source-derived request fields, response fields, validation constraints, permissions and evidence status for the React admin endpoints. It does not claim authenticated CRUD or Flutter/PHP behavioral parity.

Acceptance remains blocked on database-row provenance reconciliation; active PHP revision proof; owner decisions for excluded tables including zg_product_warehouse; collation/NBSP policy; approved isolated database and fixtures; authorized existing test accounts; authenticated browser CRUD; complete role/method and Flutter contract tests; concurrency and transaction assertions; and owner sign-off.

### Safety confirmation

No target database writes, DDL, migrations, imports, restores, account creation, package installation or cleanup. No PHP/Flutter changes. No secrets or row contents exposed. Current target remains unchanged. Overall status: PARTIAL.


## Continuation - Target Scheme, reward image, and cart discount (2026-10-16)

### Confirmed changes
- STK-AUD-021: Target Scheme loads all category pages, maps dropdown values to actual IDs, initializes category state, and validates the submitted ID before POST/PATCH.
- STK-AUD-022: Target Scheme uses an upload-only reward-image control with preview, type/size validation, upload status/errors, and persists the upload API path. Existing image paths/URLs remain supported.
- STK-AUD-023: Cart eligibility checks has_disc, discount_percent, discount_value, product_discount and stored line discounts. Active VIP discounts block the cart promotion. The Django cart endpoint derives totals from server-side records and preserves legacy response keys.

### Actual test results
| Check | Result |
|---|---|
| React unit tests | PASS - 27/27 |
| Oxlint | PASS - 0 warnings/errors |
| Vite production build | PASS |
| Targeted Django tests | PASS - 46/46 |
| Full Django suite | PASS - 126 tests, 1 expected failure (city-collation parity) |
| python manage.py check | PASS |
| python manage.py migrate --check | PASS; no migration applied |

The Django suite did not report setting up a test database. Upload tests use temporary media storage. No authenticated browser CRUD or database-backed cart request was executed.

### Remaining blockers
- /api/cart_api_test still uses the legacy hard-coded 14,000 minimum and 10% promotion. Admin settings store a separate fixed amount but are not connected. Owner must decide whether to preserve the legacy percentage rule or make the configured fixed amount authoritative.
- Browser verification of Target Scheme selection, reward upload to target save to media preview, and authenticated cart behavior remains outstanding.
- Existing database provenance, active PHP revision, collation parity, isolated integration fixtures, authorized test accounts, full Flutter/PHP parity and owner sign-off remain open.

No target database writes, schema changes, migrations, imports, restores, account creation, package installation or cleanup. PHP/Flutter unchanged. Overall status PARTIAL.


## Finalize cart policy and acceptance continuation (2026-10-16)

### Documents prepared
- [x] STOKIT_CART_DISCOUNT_POLICY_DECISION.md records the legacy ₹14,000 / 10% promotion and separate admin fixed-amount helper, including >= versus >, VIP, discounted products, mixed carts, rounding and cap.
- [x] STOKIT_CART_DISCOUNT_INTEGRATION_TEST_PLAN.md lists Target Scheme create/update, image upload/serving/persistence, and normal/VIP/already-discounted/mixed-cart acceptance cases.
- [x] Defect register updated with STK-AUD-024; overall status remains PARTIAL.
- [x] API matrix updated to preserve the existing policy distinction; no rule was switched.

### Actual checks executed in this continuation
| Check | Result | Limit |
|---|---|---|
| npm test in admin_frontend | PASS 27/27 | Unit tests only |
| npm run lint | PASS, 0 warnings/errors; 23 files | Static analysis |
| npm run build | PASS, Vite built 1,988 modules | Not runtime acceptance |
| Focused Django tests: adminapi.tests_targets adminapi.tests_uploads adminapi.tests_cart_discount legacydb.tests_discount_rules legacy_api.tests_contract | PASS 47/47 | Unit/pure helper/temporary upload tests; not authenticated DB-backed integration |
| python manage.py check | PASS | System checks only |
| python manage.py migrate --check | PASS | No migration applied |

### Acceptance matrix — current state
| Acceptance item | Status | Evidence / blocker |
|---|---|---|
| Category dropdown maps label to actual category ID | PASS — unit evidence | targetCategoryOptions and normalizeTargetCategoryId tests pass |
| Target Scheme create with persisted category ID | BLOCKED | Mocked create validation passes; no real isolated DB create/re-fetch |
| Target Scheme update with persisted category ID | BLOCKED | New database-free mocked PATCH regression passes; no isolated DB PATCH/re-fetch executed |
| Reward image file validation/storage | PASS — unit evidence | Temporary media upload tests pass |
| Reward image serving over HTTP | BLOCKED | No request to configured media-serving route executed |
| Upload -> target save -> re-fetch -> preview | BLOCKED | No authenticated browser/API end-to-end test |
| Cart helper excludes already-discounted products | PASS — unit evidence | Focused helper tests pass |
| Cart helper VIP non-stacking | PASS — unit evidence | Focused helper tests pass |
| Mixed-cart eligible subtotal and cap | PASS — unit evidence | Focused helper tests pass |
| Legacy /api/cart_api_test database-backed normal/VIP/mixed cart behavior | BLOCKED | No authenticated request against isolated fixture schema |
| Choose authoritative legacy vs admin discount policy | BLOCKED | Owner decision required; preserve both current implementations |
| Threshold equality, rounding and max-cap acceptance | BLOCKED | Business policy must be approved before expected results can be fixed |
| Authenticated browser acceptance | BLOCKED | Approved isolated environment and authorized test identity/tooling required |

### Required approvals before integration execution
1. Written business-owner decision in STOKIT_CART_DISCOUNT_POLICY_DECISION.md.
2. Explicit approval to create/drop an isolated PostgreSQL test database and apply fixture-only DDL; confirm it is not stokit_postgres_dev.
3. Approval for synthetic fixture DML and transaction/rollback strategy.
4. Approval for temporary media writes/reads/cleanup in a disposable media root.
5. Approval for an existing authorized test account or synthetic test-principal strategy; do not create accounts without approval.
6. Approval for browser automation and the isolated stack URL.

**Safety confirmation:** this continuation ran only focused unit/regression tests, frontend lint/build, Django system check and migration consistency check. No live database writes, DDL, migrations, imports, restores, account creation, package installation, or destructive cleanup. PHP and Flutter remain unchanged. **Overall status: PARTIAL.**


## Banner image, Maps and Order Management (2026-10-16)

### Source changes
- [x] Banner replacement preview, file validation, upload/save feedback and preview reset added.
- [x] Warehouse place search fallback and selected-coordinate map preview added; stale coordinates clear when the address is edited.
- [x] Admin order-create endpoint and React form added; server uses DB product/variant prices and transactionally writes checkout, items and initial status history.
- [x] Order create permission restricted to administrators.
- [x] One-sided date filters fixed; delivery-boy filter added to UI/backend.
- [x] STOKIT_BANNER_MAPS_ORDER_AUDIT.md created; defect register and API contract matrix updated.

### Actual test evidence
| Check | Result | Scope |
|---|---|---|
| Frontend npm test | PASS 27/27 | Existing utility/session regression suite |
| Frontend npm run lint | PASS; zero warnings/errors | 23 files |
| Frontend npm run build | PASS; 1,988 modules | Production bundle |
| Focused Django tests: tests_ui_workflows, tests_uploads, tests_crud_validation, tests_cart_discount | PASS 37/37 | Mocked/database-free regressions and temporary-media tests |
| Full Django suite | PASS 139 tests, 1 expected failure | No isolated/live DB integration |
| python manage.py check | PASS | System checks |
| python manage.py migrate --check | PASS | No migration applied |
| Python compilation | PASS | Modified backend modules |

### Acceptance tests still BLOCKED
- Banner: authenticated upload -> DB image_path -> GET refresh -> served-media preview.
- Places: external Google/Nominatim search, suggestion selection, persisted coordinates and reload in browser.
- Order: isolated DB creation/readback, revenue/pending totals, status transitions, delivery-boy assignment and combined filters.
- Request replay idempotency after timeout.
- Full location catalog and checkout delivery-coordinate persistence; separate schema/API proposal and approval required.

### Required configuration and approvals
1. Google Places requires owner approval for API/billing; configure VITE_GOOGLE_MAPS_API_KEY with HTTP-referrer restrictions and only required APIs. Current fallback does not need that key but depends on external OpenStreetMap service availability.
2. Approve isolated disposable PostgreSQL test DB, synthetic fixtures and test lifecycle; never use stokit_postgres_dev for writes.
3. Approve temporary media operations and authorized test identity.
4. Decide whether persisted idempotency keys and address/coordinate columns are required; approve a separate schema/API proposal before implementation.

No live DB writes, migrations, DDL, imports, restores, account creation, package installation or destructive cleanup were performed. PHP/Flutter unchanged. **Overall status: PARTIAL.**


### Additional source-level blockers (not executed against live data)
- `GET /admin-api/orders/manage` currently updates `zg_checkout.view='y'` for all orders when the returned list is non-empty. It was not called against the live DB; browser acceptance must use an isolated DB until owner approves whether to preserve this legacy read-side effect.
- Order status values are role-validated, but no explicit allowed-from/allowed-to transition graph exists. Revenue excludes pending but currently includes other statuses; cancelled/failed revenue semantics need owner approval.
- Manual order creation does not persist an idempotency key or reserve stock; repeated network replay and inventory behavior remain acceptance blockers.


## Full project audit continuation — 2026-10-16

- [x] Static audit React/Vite, Django/PostgreSQL configuration, Flutter repositories/constants, PHP reference snapshot, route handlers, tests and cleanup candidates.
- [x] Created `STOKIT_COMPLETE_API_AUDIT.md`: 26 admin + 33 legacy route patterns = 59; every route remains NOT VERIFIED for authenticated isolated E2E.
- [x] Removed generated source-tree Python bytecode caches: initial pass 10 directories/74 `.pyc`; final post-test pass 9 directories/63 `.pyc`; final scan 0 remaining outside `.venv`. Exact paths and exclusions logged in `STOKIT_TEMPORARY_RESOURCE_CLEANUP_REVIEW.md`.
- [x] Preserved env files, backups, SQL, migrations, uploads, dependency environments, generated build output, PHP and Flutter.
- [x] Fix and regression-test STK-API-001 in Django without modifying PHP/Flutter; 4 database-free search contract tests pass. E2E remains NOT VERIFIED.
- [ ] Authenticated isolated CRUD/upload/order/inventory/cart-discount/location tests and DB readback require explicit approval and isolated environment.
- [ ] Obtain canonical company links for `/api/coabout`, owner policy for cart discount and order-list side effect, authoritative PHP deployment provenance and VCS baseline.

Status remains PARTIAL. No live database writes, schema changes, migrations, account creation, imports, restores or package installation were performed.


### Phase 4 safe verification update — 2026-10-16

- [x] Fixed STK-API-001 in Django only: `/api/search` accepts Flutter POST filter fields while preserving legacy GET search; four database-free regressions pass.
- [x] React unit tests 27/27; Oxlint 0 warnings/errors; Vite build PASS (1,988 modules).
- [x] Django `check` PASS; `migrate --check` PASS with no migration applied; selected database-independent suite 80/80 PASS.
- [x] Flutter `analyze --no-pub` and `test --no-pub` attempted without installing packages; both BLOCKED because Flutter CLI is not recognized in this environment.
- [ ] All 59 route patterns still require approved isolated authenticated E2E; no route is certified E2E PASS.

No PHP/Flutter changes, package installation, database writes, DDL, migrations, imports, restores or account creation. Status remains PARTIAL.


### Local smoke check update — 2026-10-16

- [x] Local React `/login` route responds HTTP 200.
- [x] Local read-only `GET /api/banner` responds HTTP 200 JSON.
- [x] Unauthenticated `/api/category` and `/admin-api/dashboard` return HTTP 401 (auth gate observed; successful authenticated workflow not tested).
- [ ] Authenticated web/mobile workflows remain unverified; Flutter/Dart CLI unavailable and production mobile base URL was not probed.

## Order creation, financial summary, and banner continuation (2026-10-16)

### Source work completed

- [x] React order form supports variant selection, correct variant ID payloads, variant-aware estimated subtotal, and client-side duplicate/missing-variant validation.
- [x] Django order creation validates product/variant ownership, requires a variant where variant records exist, uses database-side prices, and keeps checkout/items/status-history writes in the existing atomic block.
- [x] Dashboard/reports revenue uses normalized completed statuses only (`delivered`, `fulfilled`); Order Management financial summary excludes cancelled/failed revenue and counts configured open statuses as pending.
- [x] Removed the write side effect from `GET /admin-api/orders/manage`; read-only mocked regression passes.
- [x] Calendar date validation and exclusive next-day upper bound added; backend validation array/nested errors are now displayed in the React UI.
- [x] Existing banner upload/PATCH behavior and mocked path-preservation/replacement tests rechecked; uploaded files are not deleted when the banner path changes.
- [x] Defect register, API contract matrix, complete application audit and complete API audit updated with evidence limits.

### Actual verification

| Check | Result | Notes |
|---|---|---|
| React `npm test` | PASS — 31/31 | Includes order-line/variant and validation-message regressions |
| React `npm run lint` | PASS — 0 warnings/errors across 24 files | Static analysis |
| React `npm run build` | PASS — Vite transformed 1,988 modules | Build only |
| Selected Django/API contract tests | PASS — 105/105 | Database-independent/mocked suite; no test database lifecycle |
| `python manage.py check` | PASS | No issues |
| `python manage.py migrate --check` | PASS | No migration applied |

### Acceptance criteria still BLOCKED

- [ ] Create an order with authorized credentials in an approved isolated PostgreSQL database; verify commit/rollback, items and status history, then confirm the same order appears in Order Management.
- [ ] Compare dashboard/reports/Order Management totals against the same isolated fixture orders for completed, pending, cancelled, failed and mixed statuses, with date/status filters and duplicate-join cases.
- [ ] Perform authenticated banner upload → PATCH → GET/reload → served-image browser verification in an approved isolated environment; verify the old image remains untouched while still referenced.
- [ ] Run authenticated role/permission and browser E2E acceptance with approved existing test identities and fixtures.

No PostgreSQL writes, DDL, migrations, imports, restores, account creation, package installs, or destructive cleanup were performed. PHP and Flutter source remain untouched. The selected tests did not create a test database. Overall status stays **PARTIAL** until the blocked authenticated acceptance criteria pass.

Banner evidence addendum: a temporary-MEDIA_ROOT regression verifies the uploaded PNG can be read back through Django's `serve` component; `adminapi.tests_uploads` passes 5/5. This does not close the configured URL-route, persisted banner reload, browser refresh, or production media-hosting acceptance criteria.

## Static Flutter + React/Django API audit continuation (2026-10-16)

### Completed without source/database mutation

- [x] Connected Cody to the exact `stokit_mobile` workspace path and confirmed 112 Dart files under `lib/`; older Flutter copies were not used.
- [x] Inspected Flutter API constants, Dio/auth interceptor, repositories, response models and API-dependent screens; compared the request/response contracts with Django `/api/` routes and the PHP reference.
- [x] Reviewed React Axios setup and the existing 26-route `/admin-api/` matrix against Django URL patterns; kept React `/admin-api/` separate from mobile `/api/`.
- [x] Consolidated the React + Flutter route registry in `STOKIT_API_CONTRACT_MATRIX.md` and updated `STOKIT_COMPLETE_API_AUDIT.md`, `STOKIT_DEFECT_REGISTER.md`, and this checklist.
- [x] Recorded findings STK-MOB-001 through STK-MOB-011 with severity, exact file/line, affected endpoint, source evidence, confidence, and recommended fix.
- [x] Ran `dart format --output=none` over all 112 library Dart files and `test/widget_test.dart` without modifying source; 84 files would be reformatted.
- [x] Re-ran React `npm test`: 31/31 PASS; `npm run lint`: 0 warnings/errors across 24 files; `npm run build`: PASS, 1,988 modules transformed.
- [x] Re-ran selected database-independent Django/API tests: 105/105 PASS; `python manage.py check` PASS; `python manage.py migrate --check` PASS with no migration applied.

### Flutter analysis/test blocker — exact evidence

- Flutter SDK exists at `C:\src\flutter` (Flutter 3.47.6 / Dart 3.13.5), but neither `flutter` nor `dart` is on PATH.
- `flutter analyze --no-pub`: **FAILED** (6,545 issues, including unresolved Flutter/package imports).
- `flutter test --no-pub`: **FAILED** during test compilation. The existing `.dart_tool/package_config.json` points to missing `C:\flutter\packages\flutter_test` and package cache paths under `C:\Users\OMEN\AppData\Local\Pub\Cache`, not the SDK/cache available on this machine.
- No `pub get`, package installation, dependency-cache repair, or Flutter source modification was performed because the user prohibited package installation and source changes. Do not mark Flutter analysis/tests as passing.

### Remaining blockers — status stays PARTIAL

- [ ] Correct the category-products pagination contract (`/api/getCategory`) so skip/limit are honored and load-more does not append duplicate pages; add regression coverage.
- [ ] Correct Flutter cart-summary response key mapping and null-safe parsing for product `set_contains` and profile fields.
- [ ] Implement server-backed notification mark-read and hydrate read state; add authenticated tests.
- [ ] Remove bearer/FCM token logging and add server logout behavior, with Flutter changes only after separately authorized.
- [ ] Make search query server-side so matching products outside the loaded page are included.
- [ ] Resolve stale Flutter package roots only after explicit approval to run dependency resolution/install; then rerun analyzer and tests and report their actual results.
- [ ] Run authenticated web/mobile end-to-end tests against an approved isolated PostgreSQL environment with authorized existing test identities and fixtures; verify actual order, cart, notification, profile, banner, and financial workflows.

No live API/production endpoint was called. No PostgreSQL writes, schema changes, migrations, imports, restores, account creation, package installs, PHP changes, Flutter changes, or destructive cleanup were performed.

**Overall status: PARTIAL.**


## Order and banner follow-up — 2026-10-16

- [x] Confirmed Order page sentence is informational UI copy, not an API error response.
- [x] Reviewed order payload and backend: address/locality fields are passed; server recalculates product/variant prices; duplicate lines are rejected; checkout/items/history writes are atomic in source.
- [x] Reviewed banner file selection → multipart upload (`file`) → returned `image_path` → banner PATCH (`id`, `image_path`) → list reload source path. Existing tests cover valid/invalid uploads, role denial, replacement path, and preserving image when omitted.
- [x] Ran React tests (31/31), lint (0 warnings/errors), production build, selected database-independent Django/API suite (105/105), and Django system check.
- [ ] Authenticated isolated E2E: create order, verify it in Order Management and financial summaries. Blocked: no approved isolated database-backed test environment; existing PostgreSQL data was preserved.
- [ ] Banner reload acceptance: production/non-debug media serving is unresolved. A mocked GET confirmed that DEBUG=False uses `LEGACY_BASE_URL` for a file physically stored under Django `MEDIA_ROOT`, while the current Django media route is DEBUG-only. Configure/verify the real media host or reverse-proxy mapping, then upload, PATCH, reload and fetch the served URL.
- [ ] Do not mark either issue fixed until the above E2E acceptance passes. Overall status: PARTIAL. No application source changes or database/schema mutations made in this re-verification.
