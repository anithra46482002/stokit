# STOKIT Final Readiness and Next Actions

Date: 2026-10-16 | Overall status: **PARTIAL**

The project is **not** fully fixed. Status stays PARTIAL until every acceptance gate in section 9 passes with evidence. Schema provisioning for the approved 43-table inventory is the only area reported as complete.

Labels: **OBSERVED TODAY** = read-only check in this session; **HISTORICAL** = from earlier reports, not re-measured today; **BLOCKED** = cannot proceed without an owner action; **PROPOSED** = not executed. Location note: the task named `docs/`; the file sits beside its sibling reports in `django_backend/docs/`.

Related documents (same folder): `STOKIT_CITY_NAME_COLLATION_FINAL_REVIEW.md`, `STOKIT_PHP_PROVENANCE_AND_EXCLUDED_TABLES_FINAL_REVIEW.md`, `STOKIT_AUTHENTICATED_ACCEPTANCE_TEST_PLAN.md`, `STOKIT_TEMPORARY_RESOURCE_CLEANUP_REVIEW.md`, `STOKIT_FULL_SCHEMA_AND_APPLICATION_EXECUTION_REPORT.md`.

## 1. Current target

PostgreSQL 18.6 at `127.0.0.1:5432`, database `stokit_postgres_dev`, schema `public` (HISTORICAL: confirmed read-only on 2026-10-15 and again in the 2026-10-16 master pass). Today a process still listens on port 5432 (OBSERVED TODAY); no database connection was made in this task.

## 2. Inventory

- **43 public tables and 180 rows**, all framework seed data: `auth_permission` 128, `django_content_type` 32, `django_migrations` 20 (HISTORICAL).
- Evidence source: `scripts/read_only_audits/final_target_verify_readonly.py` (READ ONLY transaction), reported in the 2026-10-16 "Master completion pass" of `STOKIT_FULL_SCHEMA_AND_APPLICATION_EXECUTION_REPORT.md`. The report gives the date (2026-10-16, +05:30) but not a clock time. The earlier 2026-10-15 22:35 report recorded the same 43 tables and 20 migration records.
- Composition: 28 legacy tables (no business rows), `admins`, 12 Django-managed tables, `admin_cart_discount_settings`, `django_migrations`. All 16 historical exclusions are absent. 8 user triggers and 111 indexes were reported.
- No historical business data was imported and no account exists.

## 3. Migration history

| App | Records |
|---|---|
| accounts | 2 |
| adminapi | 1 |
| auth | 12 |
| contenttypes | 2 |
| legacydb | 3 |
| **Total** | **20** |

`manage.py migrate --check` reportedly exits 0 (HISTORICAL, 2026-10-16). `makemigrations --check --dry-run` reported no changes. Not re-run today.

## 4. Existing admin and cart-discount tables

`admins` = 0 rows; `admin_cart_discount_settings` = 0 rows. Evidence: the 2026-10-15 continuation audit and the 2026-10-16 master pass (HISTORICAL; both read-only). Consequence: no login can succeed anywhere today, so authenticated behaviour cannot be tested on this database.

## 5. Test results — current session versus history

**Current session (2026-10-16, this task): no test suites were run.** Checks actually executed are listed in section 11.

| Result | Value | Status |
|---|---|---|
| Backend suite | 93 tests OK, 1 expected failure (isolated DB `stokit_schema_validation_20261015_2`); an earlier run had 86 | HISTORICAL. The owner notes full backend tests were not run in the latest session |
| `manage.py check` | no issues | HISTORICAL |
| Frontend `npm test` | 15 of 15 passed | HISTORICAL |
| Frontend build and lint | build OK; lint 0 warnings, 0 errors | HISTORICAL |
| Catalog validation of candidate DDL | 1,383 checks, 0 failures; 12 functional assertions passed | HISTORICAL |
| HTTP smoke | 24 admin endpoints return 401 without credentials; bad tokens 401; empty login body 400; CORS allows only the configured origin | HISTORICAL |
| Browser | page-load checks only (4 URLs rendered the login screen; 0 console errors) | HISTORICAL, **not interactive testing** |

## 6. Collation mismatch and MariaDB 11.8.9

- `zg_location.city_name` in the source dump uses `utf8mb4_uca1400_ai_ci` with a unique key; the PostgreSQL candidate uses the default deterministic collation with `UNIQUE (city_name)`.
- Measured on **MariaDB 13.0.2**, the pair `Kochi` and `Kochi` + U+00A0 (trailing NBSP) is **equal and collides** under the unique key. The best evaluated PostgreSQL strategy (ICU `und-u-ks-level1` plus a unique index on `rtrim(city_name, ' ')`) leaves exactly this case unmatched (1 of 23 cases); the default collation mismatches 17 of 23. The `rtrim(..., ' ')` expression strips only U+0020, so it does not reproduce MariaDB for this input. Other trailing Unicode space characters also mismatch under that expression.
- **MariaDB 11.8.9 (the source dump's version) is unavailable**: only 13.0.2.0 is installed (OBSERVED earlier, searched to depth 3). Everything measured is for 13.0.2; 11.8.9 behaviour is an inference. Equality checks on PostgreSQL were measured; unique-index collisions for the ICU candidates were inferred from equality, not tested by inserts, and are not described as successful collision tests.
- Options, with trade-offs, are in `STOKIT_CITY_NAME_COLLATION_FINAL_REVIEW.md` (A default; B ICU + `rtrim(' ')`; B2 ICU + broader trailing-space expression; C normalized key column; D application-level normalization only). One variant the review did not measure: default collation plus an explicit normalization expression in a unique index (call it A+). **No policy is chosen and no schema change is made; the owner decides.**

## 7. PHP provenance and excluded tables

- `stokit_php` workspace path is unavailable (OBSERVED TODAY: path missing); `phpref` (153 PHP files, all present in `StokIt Backend.zip` with identical sizes) is the only reference. It is **not** declared to be the deployed production version.
- No VCS metadata or deployment manifest exists; backup timestamps reflect extraction time. Flutter's active base URL is `https://app.stokitb2b.com/api`, while backup logs cite `projects.teleber.tech` paths.
- 14 of 16 excluded tables have SQL references in the backup's `admin/manage/` pages; `users1` and `zg_target_activity_log` have none. `zg_api_keys` and `zg_product_warehouse` carry the highest risk if the PHP admin is live. Sensitive-looking `api/tokens.txt` and a 134 MB SQL dump exist (contents not opened).
- Owner scope decisions for all 16 tables are pending (checklist in the provenance review).

## 8. Open items by area

| Area | State |
|---|---|
| Authenticated CRUD | BLOCKED: no account, no disposable test database, no approval |
| Interactive browser testing | BLOCKED: no approved automation tool; page-load evidence only |
| Permission policy for `orders` | Suspected defect: `AdminRolePermission` denies POST/DELETE for `orders`, but `/admin-api/orders` has no such handlers; real order writes use `OrderActionPermission` on `/orders/<id>/detail` and related routes. Needs source-confirmed test and an owner policy decision (see the test plan, section 2). No permission was changed |
| Backup freshness and restore coverage | Both backups (5,117 bytes each) predate the schema implementation and cover a 3-table baseline. No backup of the 43-table state exists (OBSERVED TODAY). Restore coverage is baseline-only |
| Concurrency | Django retries order-ID primary-key collisions; a live PHP writer would not share that logic. Untested under real concurrency |
| Temporary resources | Running MariaDB 13.0.2 evaluation instance (port 3399, PID 4572, started 2026-10-16 09:10:59) depends on `%TEMP%\stokit_mariadb_eval_20261015\data`; four temp folders and up to eight StokIt-style databases await owner approval; `wholesale_db` and `test_wholesale_db` are not assumed to be StokIt and stay untouched. Dev servers listen on 8000 and 5173 now (OBSERVED TODAY) |
| Secrets | `.env`, `.env.bak_stokit_dev`, `.env.postgres`, `.env.test` exist in `django_backend`; not opened. `api/tokens.txt` and SQL dumps are sensitive |
| Location search | Uses `ILIKE`, which is accent-sensitive and unsupported on nondeterministic collations; tied to the collation decision |

## 9. Acceptance gates (all must pass for status to leave PARTIAL)

| # | Gate | Current |
|---|---|---|
| G1 | 43-table schema and migration history intact | PASS (historical) |
| G2 | Fresh read-only re-verification of target and migrations before sign-off | OPEN |
| G3 | Collation policy decided, approved, implemented, and verified (ideally against 11.8.9) | BLOCKED |
| G4 | PHP deployed-source provenance established | BLOCKED |
| G5 | Scope decision recorded for each of the 16 excluded tables | OPEN |
| G6 | Permission policy for orders decided and tests aligned | OPEN |
| G7 | Disposable test environment approved and fixtures created | OPEN |
| G8 | Authenticated API tests pass (all roles, all P0 rows) | OPEN |
| G9 | Interactive browser acceptance passes | OPEN |
| G10 | Flutter contract tests pass | OPEN |
| G11 | Transaction rollback and concurrency tests pass | OPEN |
| G12 | Full backend and frontend suites re-run and passing in the acceptance run | OPEN |
| G13 | Fresh backup of the accepted state, plus a restore test | OPEN |
| G14 | Temporary resources reviewed and cleaned (or retained by decision) | OPEN |

## 10. Exact remaining approvals required from the owner

1. Supply PHP provenance: deployed commit/tag, or a host file listing with hashes, or a hosting-panel export (no system access needed).
2. Scope decision for each excluded table (checklist in the provenance review), including whether the PHP admin remains in use.
3. Collation policy choice (A, A+, B, B2, C or D, or an explicit parity waiver), plus approval of any custom ICU collation, expression index, normalization column, or `ILIKE`→`LIKE` change.
4. Permission policy for order creation/deletion and the ADMIN-creates-SUPER_ADMIN question.
5. Creation of an isolated disposable PostgreSQL test database (never `stokit_postgres_dev`).
6. Creation of synthetic test fixtures and a test account per role in that database.
7. Schema provisioning and migrations in that database only.
8. Browser automation tool and the test-execution scope.
9. Permission to obtain or run MariaDB 11.8.9 for final collation parity (installation or an existing instance).
10. A fresh backup of `stokit_postgres_dev` and a restore verification.
11. Cleanup (separately for archiving evidence, stopping PID 4572, deleting the temp folders, dropping databases), per the cleanup review.
12. Any change to the target schema or code that follows from items 2–4.

## 11. Checks executed in this task

All read-only, using Cody (file reads, searches and PowerShell listings): read the existing reports, matrix JSON and relevant source (`permissions.py`, `order_pages.py`, `crud.py`, `operations.py`, `uploads.py`, `urls.py`, frontend `App.jsx` and page files); listed `phpref`, the ZIP entries (names, sizes, dates only), `%TEMP%` StokIt folders, `backups/`, and listeners on ports 3306, 5432, 3399, 5173 and 8000; checked that the `stokit_php` path is missing; grepped the Flutter base URL and the `$qt` prefix; extracted host names and timestamps from PHP backup logs. **Not run:** database queries, migrations, tests, builds, installs, network requests, any write to a database or source file. The four review documents are the only files written.

## 12. Dependency-ordered plan to reach acceptance

1. **Owner inputs, no system change:** provenance evidence (approval 1), table scope decisions (2), collation choice (3), orders permission policy (4). These unblock everything below.
2. **Resolve provenance and scope:** compare the supplied host listing with `phpref`; finalize which excluded tables stay out. Any table moved in scope needs its own schema approval and design (note `zg_product_warehouse` many-to-many, `zg_api_keys` secrets handling).
3. **Collation:** if a custom policy is chosen, implement it first in a disposable database, run the matrix in the collation review (including real unique-insert collisions), and, if approved, verify against MariaDB 11.8.9; only then propose the change to the target.
4. **Disposable test environment** (approvals 5–7): provision schema in the new database; seed role fixtures and synthetic data.
5. **Automated verification:** full backend suite, then the authentication, permission, CRUD, upload, rollback, concurrency and Flutter-contract sections of the test plan, fixing defects through separately approved changes.
6. **Browser acceptance** (approval 8) against the disposable stack.
7. **Frontend suites, build, lint** re-run and recorded.
8. **Backup and restore** of the accepted state (approval 10).
9. **Cleanup** (approval 11), keeping retained evidence.
10. **Final read-only re-verification** of the target (G2), update the execution report, and only then reconsider the overall status. If any gate remains open the status stays **PARTIAL**.

## 13. Single safest next action

Owner supplies the PHP deployment evidence (approval 1, for example a hash listing from the live host). It is read-only on the system side, changes nothing in the project, and unblocks the provenance and excluded-table decisions.
