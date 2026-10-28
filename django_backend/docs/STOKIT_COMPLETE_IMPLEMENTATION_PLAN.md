# StokIt Complete PostgreSQL Implementation Plan

Status: planning only; execution is not authorized.

## Gate 0 — Preserve and verify

1. Confirm target identity and take a fresh custom-format backup with an independently verified restore destination.
2. Capture read-only catalog, row counts, constraints, indexes, and migration records for the three existing tables.
3. Do not run migrations or DDL during this gate.

## Gate 1 — Resolve scope

1. Review all 45 source tables and trace all 16 excluded tables through PHP, API, frontend, foreign keys, and trigger references.
2. Obtain an approved table manifest distinguishing existing objects from proposed objects.
3. Confirm whether Django auth/contenttypes tables are in scope.

## Gate 2 — Resolve conversion semantics

Resolve ID/uniqueness, collation, prefix indexes, enum values, boolean semantics, update timestamps, trigger behavior, checkout allocation, JSON validity, timezone, tuple-count discrepancy, and target baseline.

## Gate 3 — Generate complete candidate

Generate DDL only for approved tables, preserving existing objects. Specify keys, indexes, checks, FK actions, identity behavior, and timestamp-trigger strategy. Mark each object EXISTING, PROPOSED, BLOCKED, or NOT IN SCOPE.

## Gate 4 — Isolated validation

Verify the validation database is not stokit_postgres_dev. Validate only in an isolated disposable database or rollback-only transaction. Check dependency order, constraints, indexes, and compatibility without importing business data.

## Gate 5 — Human approval

Present exact SQL, backup/restore evidence, manifest, rollback plan, test results, and remaining risks. Wait for explicit approval.

## Gate 6 — Controlled implementation (future approval only)

After approval only, apply approved DDL in the named target, verify catalog objects, and stop on any deviation. Migration execution and account bootstrap require separate explicit approval. No historical data import is included.

## Current stop condition

Artifacts remain review-only. No DDL, migrations, account creation, or business data writes were performed.

## Phase 4 result (2026-10-15 21:45:11 +05:30)

### Completed read-only work
1. Verified Cody workspace and read all eight existing complete-schema artifacts.
2. Updated the existing inventory JSON/Markdown in place with source column/key metadata and table-by-table PHP backup, Django runtime/tooling, and React literal-reference evidence.
3. Scanned 153 PHP files in the available backup snapshot, 62 Django runtime Python files, 34 Django test/migration/audit files, and 20 React source files. Active PHP source remains unconfirmed.
4. Connected read-only to PostgreSQL 18.6 stokit_postgres_dev; verified exactly three public tables, metadata, exact row counts, constraints/indexes, and the sole migration record. The read-only transaction ended with ROLLBACK.
5. Inspected the visible trigger condition and target-progress update path; full conversion semantics remain blocked.

### Stop conditions still active
- Do not run migrations (including --fake), create accounts/roles/Super Admin, import historical data, modify PHP/Flutter, install dependencies, or execute DDL/DML against the target.
- Do not promote any source table to executable DDL yet. Active PHP source and table scope remain unresolved; all 16 excluded tables require individual evidence/owner decisions.
- Current tuple scan matches at 3,224 original and sanitized tuples under both escape modes; the earlier 3,219 count was not reproduced, but its origin remains unknown. Trigger equivalence, collation/prefix-index/ENUM/boolean/timestamp/JSON/timezone/checkout ID semantics, admins ID/uniqueness, auth/contenttypes scope, and migration-history reconciliation remain blockers.
- Candidate SQL intentionally contains comments only; manifest has zero executable operations.
- Status remains NOT READY FOR HUMAN REVIEW as an executable complete schema. Wait for explicit approval before schema changes.



## Post-execution reconciliation (2026-10-15)

The earlier sections above preserve the original planning/approval gates as historical context. Subsequent authorized execution evidence in `STOKIT_FULL_SCHEMA_AND_APPLICATION_EXECUTION_REPORT.md` records that the approved 43-table schema has been provisioned and validated. Do not treat the earlier planning-only wording as the current live target inventory.

Current verified checkpoint: PostgreSQL 18.6 `stokit_postgres_dev`, schema `public`, 43 public tables, 16 exclusions absent, `admins=0`, `admin_cart_discount_settings=0`, `django_migrations=20`. No historical business data was imported.

Remaining gates before declaring application parity: (1) prove MariaDB `utf8mb4_uca1400_ai_ci` comparison/unique behavior against a PostgreSQL strategy in isolation; (2) obtain authoritative deployed PHP provenance and complete the 16-table dependency matrix before any scope change; (3) perform browser-level E2E using approved existing tooling; (4) validate authenticated workflows with a legitimately authorized existing test account, without account creation or authentication bypass. Current status remains PARTIAL. No additional target schema changes are authorized by this reconciliation note.

## Master completion pass (2026-10-16)

Status update: the approved 43-table schema is implemented and verified; the remaining plan items are all external decisions or authorizations. (1) Provenance: owner supplies the deployed PHP revision. (2) Scope: per-table decisions for the 14 referenced excluded tables, informed by the matrix. (3) Collation: approve the ks-level1 + rtrim expression-index strategy or another one, then validate in isolation before any target change. (4) Browser/authenticated testing: approve an automation tool and provide an existing test account.

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
