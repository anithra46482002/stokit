# STOKIT Full Schema and Application Execution Report

Workspace: C:/Users/.MSI/Downloads/StokIt Backend (Cody workspace stokit)
Target: PostgreSQL 18.6 at 127.0.0.1:5432, database stokit_postgres_dev, schema public
Last updated: 2026-10-15 22:35 local

## Final status

**Schema provisioning: PASS for the approved 43-table inventory. Application validation: PARTIAL.** All 43 expected tables are present. Browser-driven end-to-end testing and some legacy behavior-equivalence decisions remain incomplete.

| Stage | Status | Evidence |
|---|---|---|
| 1. Inspect/resume | PASS | Existing artifacts and live target inspected. |
| 2. Generate schema | PASS | 28 legacy tables generated; existing admins preserved; Django tables handled by migrations. |
| 3. Isolated validation | PASS | 43-table validation DB; catalog validator 1,383 checks, 0 failures; 12 functional assertions passed. |
| 4. Target implementation | PASS | 28 legacy tables created; 19 pending migrations applied normally; target has 43 tables and 20 migration records. |
| 5. Backend | PASS | Django check/migration check passed; 86 tests passed; server at http://127.0.0.1:8000/. |
| 6. Frontend | PASS | 15 tests passed; production build passed; lint 0 warnings/errors; Vite at http://127.0.0.1:5173/ returns HTTP 200. |
| 7. End to end | PARTIAL | API/CORS HTTP smoke checks passed. Browser automation unavailable; successful admin CRUD not tested because no account may be created. |

## Backup and preservation

Fresh backup: django_backend/backups/stokit_postgres_dev_pre_full_schema_20261015.dump

Restored to isolated database stokit_backup_restore_verify_20261015. Table names, row counts, and migration records matched the pre-change target baseline: 3 tables, admins=0, admin_cart_discount_settings=0, django_migrations=1.

After implementation, admins and admin_cart_discount_settings column definitions, defaults, constraints, indexes, and row counts match the restored baseline. Both still have 0 rows. The original adminapi.0001_cart_discount_settings migration record remains present.

## Final inventory

Exactly 43 public tables are present: 28 newly created legacy tables, preserved admins, 12 Django-managed tables (5 accounts, 6 auth, django_content_type), and the 2 existing tables admin_cart_discount_settings and django_migrations.

All 16 historical exclusions remain absent. The 28 legacy tables contain no business rows. No historical business records were imported and no admin/Super Admin account was created.

## Validation evidence

- Offline converter generates 28 legacy table definitions, 283 columns, 6 foreign keys, 29 secondary indexes, 12 unique constraints, and 8 triggers.
- Catalog validation against isolated DB stokit_schema_validation_20261015_2: 1,383 checks, 0 failures. Validator checks column types/order, nullability, identity/default presence, primary keys, uniqueness, foreign keys, index names, check counts, triggers, and data-free status.
- Functional SQL was corrected: removed stray EOF_X and added assertions that raise on failure. All 12 assertions passed, including enum rejection, identity, unique email, timestamp behavior, FK rejection/cascade, boolean default, JSON validation, and checkout target-progress trigger.
- Fixed six-digit checkout ID allocation to retry actual PostgreSQL primary-key collisions in a savepoint; added regression test.
- Backend suite: 86 tests passed in the isolated validation DB. Django check and migrate --check pass.
- Frontend npm test: 15 passed, 0 failed. Vite build passed. Oxlint: 0 warnings/errors.
- Live smoke tests: nonexistent login -> expected HTTP 401; protected cart-discount API without credentials -> expected HTTP 401; frontend root -> HTTP 200; CORS preflight -> HTTP 200 with allowed origin http://127.0.0.1:5173.
- Backend and frontend development servers are running at http://127.0.0.1:8000/ and http://127.0.0.1:5173/. Backend uses stokit_postgres_dev.

## Remaining blockers

1. Active deployed PHP source is unconfirmed. Eight excluded tables have literal references in the available PHP backup; exclusions remain unchanged pending active-source/dependency confirmation.
2. Source collation for zg_location.city_name is utf8mb4_uca1400_ai_ci. Exact PostgreSQL case/accent/trailing-space equivalence is not yet proven.
3. Django checkout inserts now retry primary-key collisions, but an active external PHP writer would not share that retry logic; active PHP runtime is unverified.
4. Browser-level Playwright testing is blocked because playwright-cli is unavailable. No dependency was installed without approval.
5. Successful authenticated admin CRUD was not tested because creating an account is prohibited.

## Safety outcome

No historical business records imported. admins was not altered; no admin account created. PHP and Flutter source files were not modified. Schema provisioning is complete for the approved 43-table inventory; remaining work concerns compatibility and browser-level verification.


## Final continuation audit (2026-10-15)

### Phase 1 — current-state preflight
- Cody workspace `stokit` resolves to `C:\Users\.MSI\Downloads\StokIt Backend`; the repository and the expected reports exist.
- Read-only Django connection confirmed PostgreSQL 18.6, database `stokit_postgres_dev`, role `postgres`, schema `public`. Exactly 43 public base tables were returned. None of the 16 excluded historical table names is present.
- `admins` rows=0, `admin_cart_discount_settings` rows=0, `django_migrations` rows=20. No database writes were made during this continuation audit.
- Listener checks confirmed processes on 127.0.0.1:8000 and 127.0.0.1:5173. Existing managed processes were left running.

### Workstream 1 — `zg_location.city_name` collation: BLOCKED
- Read-only catalog inspection found only the built-in ICU collation `und-x-icu` among the inspected ICU candidates; the proposed `und-u-ks-level1` collation is not present in the target database.
- PostgreSQL default equality test returned false for `Kochi`/`kochi`, `café`/`cafe`, and `Kochi`/`Kochi `; this does not establish source parity. The candidate `und-u-ks-level1` query could not run because that collation does not exist in the target.
- No target collation, index, constraint, or application normalization was changed. Exact source equality, trailing-space and unique-collision semantics remain unproven. Next action: compare source MariaDB behavior against candidate implementations in an isolated database, then document/approve a strategy before any target change.

### Workstream 2 — PHP provenance and excluded-table dependency audit: PARTIAL / BLOCKED
- The available PHP root is `C:\Users\.MSI\Downloads\StokIt_PHP_Backup_20261012\Host`, a 153-file backup snapshot. Sample file timestamps are 2026-10-09; directory metadata is dated 2026-10-12. No Git metadata was found at that root. These facts do not establish the active deployed revision.
- Literal PHP backup references remain confirmed for eight excluded tables: `zg_brands`, `zg_cod`, `zg_headings_new`, `zg_reels`, `zg_social_media`, `zg_testy`, `zg_vari_product_images`, `zg_vari_variant`. No literal reference was found in that snapshot for `users1`, `zg_api_keys`, `zg_banner`, `zg_headings`, `zg_logo`, `zg_product_warehouse`, `zg_target_activity_log`, `zg_vari_product`; absence of literal matches is not proof of no indirect/runtime dependency.
- All 16 exclusions remain absent and unchanged. Active-source provenance and route/include/cron/indirect dependency verification require an authoritative deployment source and remain unresolved.

### Workstream 3 — browser E2E: BLOCKED BY TOOLING
- Cody's browser command reported `playwright-cli not found on PATH`. No dependency or browser binary was installed. A browser session, console, and browser network panel therefore could not be inspected; this is not reported as a browser test.
- Fresh HTTP checks: frontend `/` returned 200; protected `/admin-api/cart-discount-settings` without credentials returned 401; CORS OPTIONS preflight returned 200 and `Access-Control-Allow-Origin: http://127.0.0.1:5173`. Backend `/` returned 404 (no root route observed), not an authenticated workflow test.
- Next action: obtain approval for an existing browser automation tool or use a supported browser session; then test the UI using only an already-authorized account.

### Workstream 4 — authenticated admin workflows: BLOCKED / PARTIAL SECURITY CHECKS
- No account was created and no authentication/permission bypass was introduced. Unauthenticated protected endpoint rejection (401) was verified. Existing report evidence records an invalid/nonexistent login rejection (401) and auth unit tests.
- Authenticated navigation, role-based UI behavior and CRUD were not verified because no authorized existing test account was available in the evidence reviewed. Next action: obtain approved credentials for an existing test account; otherwise keep authenticated CRUD blocked.

### Continuation outcome
- Schema remains at the approved 43-table state; exclusions and protected existing table row counts remain unchanged. No historical data import, migration, DDL/DML, account creation, PHP/Flutter edit, package installation, or destructive cleanup was performed in this audit.
- Overall status remains **PARTIAL**. Exact collation parity, active PHP provenance/dependency confirmation, browser E2E, and authenticated admin CRUD are not complete. Do not mark the project fully complete until these items have evidence-backed resolution.


### Fresh regression checks during continuation
- `python manage.py check`: PASS, no issues (no database writes).
- `admin_frontend` `npm test`: PASS, 15/15 tests.
- `admin_frontend` `npm run build`: PASS (Vite production build).
- `admin_frontend` `npm run lint`: PASS, 0 warnings and 0 errors.
- Backend full test suite is not rerun in this continuation; the previously recorded 86-test isolated-database run remains the latest backend-suite evidence.


### Excluded-table PHP backup scan refinement
A fresh line-level scan of all 153 PHP files in the available backup refined the literal-reference evidence below. Operation labels are based on SQL keywords on matching lines; multiline queries/comments and runtime reachability require manual review. This remains backup-only evidence, not proof of active deployment behavior.

| Excluded table | Backup evidence | Operations visible in matching lines | Assessment |
|---|---|---|---|
| `zg_brands` | `admin/manage/brands.php` | SELECT, INSERT, DELETE | Direct SQL read/write references found. |
| `zg_cod` | `admin/manage/cod.php` | SELECT, UPDATE, INSERT | Direct SQL read/write references found. |
| `zg_headings_new` | `admin/manage/editProduct.php`, `admin/manage/product.php` | SELECT | Direct read references found; source lines also contain comments. |
| `zg_reels` | `admin/manage/reels.php` | SELECT, INSERT, UPDATE, DELETE | Direct SQL read/write references found. |
| `zg_social_media` | `admin/manage/navbar.php` | SELECT | Direct read reference found. |
| `zg_testy` | `admin/manage/testmo.php` | SELECT, INSERT, UPDATE, DELETE | Direct SQL read/write references found. |
| `zg_vari_product_images` | `admin/manage/col.php` | SELECT | Direct read reference found. |
| `zg_vari_variant` | `admin/manage/edit_col.php` | No SQL operation confirmed by the matching line; the match is a comment about deleting variants. | Comment-only literal match; not evidence of a live SQL dependency by itself. |
| `users1`, `zg_api_keys`, `zg_banner`, `zg_headings`, `zg_logo`, `zg_product_warehouse`, `zg_target_activity_log`, `zg_vari_product` | No literal match in scanned PHP backup | None detected | Indirect/runtime use is not ruled out. |

Do not add or restore any of these tables based on this scan. Active PHP provenance, include/route/cron analysis, and owner scope approval remain required before revisiting the 16 exclusions.

## Master completion pass (2026-10-16)

Overall: **PARTIAL**. Schema provisioning and regression suites pass; collation parity, PHP provenance, runtime dependency of excluded tables, interactive browser E2E and authenticated CRUD remain BLOCKED/PARTIAL for the external reasons below. Where this section conflicts with the earlier 'Excluded-table PHP backup scan refinement' above, this section is correct.

### Final status matrix

| Workstream | Status | Evidence | Next action / who / authorization |
|---|---|---|---|
| Target identity and 43-table schema | PASS | Read-only: stokit_postgres_dev, PostgreSQL 18.6, schema public, 43 base tables, 0 of 16 excluded present (final_target_verify_readonly.py). | none |
| Existing-object and migration-history preservation | PASS | admins=0, admin_cart_discount_settings=0, django_migrations=20 (first record adminapi.0001_cart_discount_settings); `migrate --check` exit 0; only auth_permission(128), django_content_type(32), django_migrations(20) are non-empty (framework seed rows); no business rows. Column-level preservation diff is from the earlier stage, not repeated today. | none |
| Collation equality and uniqueness compatibility | BLOCKED | See collation section. Source semantics measured on a disposable MariaDB 13.0.2 (source dump was 11.8.9). Best candidate (ks-level1 + rtrim expression unique index) leaves 1 of 23 cases unmatched (trailing NBSP); the current candidate (deterministic default) mismatches 17 of 23. | Owner approval of a collation/expression-index strategy and the NBSP/legacy-data policy; ideally a run on the original MariaDB 11.8.9. Needs authorization for any target schema change. |
| Active PHP deployment provenance | BLOCKED | Backup has no VCS or deploy manifest; all 153 files share mtimes within 10 seconds (2026-10-09 10:03:59-10:04:09), i.e. extraction/copy time, not edit history. | Owner supplies the deployed commit/tag, host file listing with hashes, or a hosting-panel export. |
| Dependency matrix for all 16 excluded tables | PARTIAL | Complete static matrix for all 16 (below). 14 of 16 are referenced by the backup's admin/manage PHP once the $qt prefix is resolved; users1 and zg_target_activity_log have no reference anywhere. Runtime reachability is not established. | Provenance (above) plus owner scope decision per table; no change made. |
| Browser-level E2E | BLOCKED | Real Chrome 155 (existing install, headless, no automation library) loaded the Vite page for /, /login, /orders, /no-such-page: all rendered the login screen with a password field, 0 load failures, console had only 3 INFO messages (Vite connect, React DevTools hint), 0 errors/warnings, backend log 0 5xx. This is page-load evidence only. Interactive login-form validation, login success/failure through the UI, session persistence, logout and CRUD were not exercised. | Approval to use browser automation (Playwright or driving Chrome over DevTools protocol) AND an authorized existing test account. |
| Authentication and permission security checks | PARTIAL | PASS (HTTP, real servers): 24 admin-api endpoints return 401 without credentials; garbage/empty/Basic/none-alg tokens return 401; unauthenticated POST/PUT/DELETE on 4 resources return 401; POST auth/login with empty body returns 400. CORS: allowed origin gets ACAO; http://evil.example gets no ACAO header. Code review: signed token with max_age, fail-closed role lookup, 5 roles identical in backend ROLE_RESOURCES and frontend VALID_ROLES. Not exercised: valid-token role matrix (needs a real account). | Authorized existing account per role, or approved test fixtures in an isolated DB. |
| Authenticated admin CRUD | BLOCKED | admins has 0 rows; no account may be created; no credentials provided. | Authorized existing test credentials, or approved isolated-DB fixture. |
| Backend regression suite | PASS | `manage.py test --noinput` against isolated DB: 93 tests, OK (expected failures=1). 86 earlier + 7 new city-name collation tests. check: no issues; makemigrations --check --dry-run: no changes. | none |
| Frontend tests, build, and lint | PASS | npm test 15/15; npm run build OK; npm run lint 0 warnings/0 errors. | none |
| Final read-only database verification | PASS | See first two rows; 8 user triggers, 111 indexes; no ci_ai/ci_as collations and no citext/unaccent in target. | none |

### zg_location.city_name collation (Workstream A)
Verified facts: source dump (MariaDB 11.8.9) declares the table with `DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci` and `UNIQUE KEY city_name (city_name)`; the PostgreSQL candidate is `varchar(100)` with the database default collation and `UNIQUE (city_name)`; the app searches with `ILIKE` (case-insensitive, accent-sensitive) in adminapi/operations.py and duplicate detection relies on the unique index.

Executable evidence: `scripts/schema_conversion/collation_eval.py` ran 23 value pairs on a disposable MariaDB 13.0.2 (temp datadir, port 3399, stopped afterwards; the original 11.8.9 server was not available) and on disposable PostgreSQL 18.6 databases (stokit_collation_eval_20261015c). Raw results: docs/STOKIT_CITY_NAME_COLLATION_EVAL.json.
- Source behavior measured (equal AND unique-collision): Kochi/kochi, cafe-acute/cafe, NFC/NFD, trailing space(s), trailing NBSP, sharp s/ss, ae ligature/ae, Istanbul dotted I, fullwidth, ligature fi, ZWJ, Kelvin sign, o-stroke, l-stroke, Malayalam vowel forms, and empty/space are all equal. Different: leading space, trailing tab, inner space, dotless i/i, hyphen, Kochi/Kochin. Equality and unique collision agreed for all 23 pairs.
- PostgreSQL candidates vs source (mismatching cases of 23): deterministic default 17; und-x-icu deterministic 17; nondeterministic ICU und-u-ks-level1 4 (trailing space, two trailing spaces, trailing NBSP, empty vs space); ks-level2 10; ks-level1 plus unique index on rtrim(city_name, ' ') 1 (trailing NBSP only).
- Query behavior: plain equality uses the unique index for all but the rtrim expression index, which is used only when the query repeats the same expression. `ILIKE` fails on nondeterministic collations (FeatureNotSupported), so the search would need `LIKE` (not recorded in the JSON) or normalization. ICU collations ci_ai/ci_as do not exist in the target; creating them is a schema change that was NOT made.
- Assumption vs fact: PAD SPACE behavior was measured on 13.0.2, not 11.8.9. Public MariaDB naming material lists uca1400_ai_ci and uca1400_nopad_ai_ci as separate collations, consistent with the measured padding, but one naming document is internally inconsistent, so the version-to-version claim is an inference.
- Proposed (needs approval): nondeterministic `und-u-ks-level1` collation on the column plus a unique expression index on `rtrim(city_name, ' ')`, with application queries using the same expression; decide NBSP handling and replace `ILIKE`. Trade-offs: nondeterministic collations are slower, cannot use LIKE-prefix index scans, and cannot back some features; the expression index changes how queries must be written.
- Regression tests added: adminapi/tests_city_name_collation.py (7 tests, DB-free): pins the measured source behavior, asserts the DDL candidate declares no collation, and carries one expectedFailure documenting that parity is not met. Status: BLOCKED (parity unproven; not changed).

### PHP provenance and excluded-table dependencies (Workstream B)
Verified facts: backup root `C:\Users\.MSI\Downloads\StokIt_PHP_Backup_20261012\Host`; 153 PHP files; no `.git`, no manifest/checksum/deploy files (only .htaccess); all file mtimes are within 10 seconds on 2026-10-09 (extraction time). No `.git` at the workspace roots or C:\Project\stokit. The `stokit_php` workspace path resolves to an empty location. Provenance of the active deployment: BLOCKED.

CORRECTION to earlier text in these reports: the previous literal-name scan found only 8 referenced tables because the PHP code builds names as `{$qt}_table` with `$qt = 'zg'` (admin/manage/config.php). After resolving that prefix (scripts/read_only_audits/excluded_table_dependency_audit_readonly.py, output docs/STOKIT_EXCLUDED_TABLE_DEPENDENCY_MATRIX.json) 14 of 16 excluded tables have SQL references in the backup; only users1 and zg_target_activity_log have none. Operation labels are keyword-heuristic (nearest SQL keyword before the name); comment-only lines are labeled separately. All hits are under admin/manage/; none are in the backup's api/ files. No excluded table is referenced by Django runtime code, tests aside, or by React. 350 dynamic-name candidate lines exist (interpolated variables); only the `$qt`/`$table_prefix` pattern was resolved, so other dynamically built names are not ruled out. A static backup scan is not proof that any table is unused or used in production.

| Table | PHP backup references (operation counts) | Source path : function | Inferred business purpose | Dump rows (approx) / FKs / triggers | Django runtime / React refs | Risk of continued exclusion |
|---|---|---|---|---|---|---|
| `users1` | none (hits 0, 0 via $qt prefix) | - | Unknown (no code reference found); name suggests a legacy user copy [inference] | ~2 / none / 0 | 0 / 0 | Low |
| `zg_api_keys` | DELETE x1, INSERT x2, SELECT/read x2, UPDATE x3 (hits 8, 8 via $qt prefix) | admin/manage/keys.php:getAllKeys<br>admin/manage/keys.php:getGroupedKeys<br>admin/manage/keys.php:getKeyById | Admin management of service/payment API keys (key_type, service_name, key_value, merchant_id, salt_key) [inferred from SQL columns] | ~0 / none / 0 | 0 / 0 | High if the PHP admin is live: payment-key management has no Django equivalent |
| `zg_banner` | DELETE x1, INSERT x1, SELECT/read x10, UPDATE x3 (hits 15, 15 via $qt prefix) | admin/manage/ban_timer.php:getAvailableSlot<br>admin/manage/ban_timer.php:hasActiveBanner<br>admin/manage/ban_timer.php:updatePreviewTimer<br>admin/manage/login.php:(top-level script) | Admin-login-page banner and countdown (ban_timer.php, login.php) [inferred]; distinct from the Django banner model (zg_slider) | ~1 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_brands` | DELETE x1, INSERT x1, SELECT/read x3 (hits 5, 0 via $qt prefix) | admin/manage/brands.php:(top-level script) | Brand list management (brands.php) [inferred] | ~3 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_cod` | INSERT x1, SELECT/read x2, UPDATE x1 (hits 4, 0 via $qt prefix) | admin/manage/cod.php:(top-level script) | Cash-on-delivery settings (cod.php) [inferred] | ~1 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_headings` | SELECT/read x1, UPDATE x1 (hits 2, 2 via $qt prefix) | admin/manage/heading4.php:(top-level script) | Storefront/app heading text (heading4.php) [inferred] | ~1 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_headings_new` | INSERT x1, SELECT/read x6, UPDATE x3, comment-only x2 (hits 12, 8 via $qt prefix) | admin/manage/editProduct.php:(top-level script)<br>admin/manage/headings.php:(top-level script)<br>admin/manage/product.php:(top-level script) | Product-page headings (headings.php, product.php, editProduct.php) [inferred] | ~7 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_logo` | DELETE x2, INSERT x1, SELECT/read x5, UPDATE x1 (hits 9, 9 via $qt prefix) | admin/manage/logo.php:(top-level script) | Site logo and favicon files (logo.php) [inferred] | ~2 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_product_warehouse` | DELETE x2, INSERT x1, SELECT/read x4, comment-only x1 (hits 8, 8 via $qt prefix) | admin/manage/editProduct.php:(top-level script)<br>admin/manage/editProduct.php:handleBannerUpload<br>admin/manage/product.php:(top-level script)<br>admin/manage/warehouse_details.php:(top-level script) | Product-to-warehouse assignment; FKs to zg_product and zg_warehouse; INNER JOIN in the PHP product list [inferred] | ~9 / `product_id` -> zg_product; `warehouse_id` -> zg_warehouse / 0 | 0 / 0 | High if used: FK-linked assignment data; PHP product list joins it; no Django equivalent |
| `zg_reels` | DELETE x1, INSERT x1, SELECT/read x2, UPDATE x1 (hits 5, 0 via $qt prefix) | admin/manage/reels.php:getInstagramEmbedCode | Reels/video content management (reels.php) [inferred] | ~1 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_social_media` | SELECT/read x2, UPDATE x1 (hits 3, 2 via $qt prefix) | admin/manage/navbar.php:(top-level script)<br>admin/manage/social.php:(top-level script) | Social links (social.php, navbar.php) [inferred] | ~1 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_target_activity_log` | none (hits 0, 0 via $qt prefix) | - | Unknown (no code reference found); name suggests a target activity audit log [inference] | ~0 / none / 0 | 0 / 0 | Low |
| `zg_testy` | DELETE x1, INSERT x2, SELECT/read x4, UPDATE x2, comment-only x1 (hits 10, 1 via $qt prefix) | admin/manage/testmo.php:(top-level script) | Testimonials (testmo.php) [inferred] | ~4 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_vari_product` | DELETE x1, INSERT x1, SELECT/read x3, UPDATE x2 (hits 7, 7 via $qt prefix) | admin/manage/add_col.php:compressImage<br>admin/manage/col.php:(top-level script)<br>admin/manage/edit_col.php:(top-level script)<br>admin/manage/edit_col.php:compressImage<br>admin/manage/edit_col_.php:(top-level script)<br>admin/manage/edit_col_.php:compressImage | Variant-collection ('col') products (add_col.php, col.php, edit_col*.php) [inferred] | ~0 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_vari_product_images` | DELETE x3, INSERT x3, SELECT/read x6, UPDATE x4 (hits 16, 15 via $qt prefix) | admin/manage/add_col.php:compressImage<br>admin/manage/col.php:(top-level script)<br>admin/manage/edit_col.php:(top-level script)<br>admin/manage/edit_col.php:compressImage<br>admin/manage/edit_col_.php:(top-level script)<br>admin/manage/edit_col_.php:compressImage | Images for variant-collection products [inferred] | ~0 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_vari_variant` | DELETE x2, INSERT x1, SELECT/read x1, comment-only x1 (hits 5, 4 via $qt prefix) | admin/manage/col.php:(top-level script)<br>admin/manage/edit_col.php:(top-level script)<br>admin/manage/edit_col.php:compressImage | Variants of variant-collection products; only a delete comment plus SQL found [inferred] | ~0 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |

Evidence required to change any classification: authoritative deployed source or access logs showing which admin/manage pages are actually used, plus an owner scope decision. Exclusions were preserved; nothing was created, restored or populated.

### Execution detail (2026-10-16, local +05:30)
Commands/results: `python manage.py check` (no issues); `makemigrations --check --dry-run` (no changes); `manage.py test --noinput` with DB_NAME=stokit_schema_validation_20261015_2 (93 tests OK, 1 expected failure); `manage.py migrate --check` on target (exit 0, reads django_migrations only); `npm test` 15 pass; `npm run lint` 0/0; `npm run build` OK; collation_eval.py; excluded_table_dependency_audit_readonly.py; final_target_verify_readonly.py (READ ONLY transaction). Servers: Django (127.0.0.1:8000, DB stokit_postgres_dev) and Vite (127.0.0.1:5173) were started for the HTTP/browser checks and stopped afterwards; the dev servers that were listening at the start of this pass are not running now (ports 8000 and 5173 are free) and must be restarted by the owner if wanted. Backend log during checks: 94 lines, 0 5xx, 0 tracebacks.
Confirmed application defects: none found in this pass; no application code changed. Documentation defects corrected: incomplete PHP reference count, inventory JSON BOM/omission. Observation tied to S04: location search uses ILIKE (accent-sensitive) whereas the source collation is accent-insensitive.
Files added: adminapi/tests_city_name_collation.py; scripts/schema_conversion/collation_eval.py; scripts/read_only_audits/excluded_table_dependency_audit_readonly.py; scripts/read_only_audits/final_target_verify_readonly.py; scripts/read_only_audits/update_reports_20261016.py; docs/STOKIT_CITY_NAME_COLLATION_EVAL.json; docs/STOKIT_EXCLUDED_TABLE_DEPENDENCY_MATRIX.json. Files edited: the six docs listed in the task (inventory JSON re-saved without BOM with an added `master_completion_pass_20261016` key; exclusions and approved manifest unchanged). admin_frontend/dist was regenerated by the build. No PHP, Flutter, SQL dump, .env or secret file was modified.
