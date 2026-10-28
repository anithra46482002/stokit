# StokIt ? Safe Fresh PostgreSQL Implementation Plan

Generated: 2026-10-15T20:44:15+05:30

## Objective

Prepare the fresh PostgreSQL development database for the Django backend and React admin while preserving the existing target tables, avoiding historical business-row imports, and leaving PHP/Flutter sources unchanged.

## Non-negotiable safety rules

- Target only `stokit_postgres_dev`, local PostgreSQL `127.0.0.1:5432`, schema `public`.
- Preserve the existing `admins`, `admin_cart_discount_settings`, and `django_migrations` tables and their current contents/definitions. Never drop, truncate, or recreate them.
- Do not import `INSERT` data from either legacy SQL dump. Source SQL is used only for schema analysis.
- Do not run Django migrations, execute generated DDL, create a Django superuser, or create a React/legacy Super Admin until the DDL and change manifest pass review and the change/backup gates are approved.
- Do not modify PHP or Flutter source files. Do not print credentials or password values.
- Keep the project root limited to `django_backend/` and `admin_frontend/`. Regenerated documentation lives in `django_backend/docs/`.

## Current verified target state

- Database: `stokit_postgres_dev`; role: `postgres`; schema: `public`; endpoint: `127.0.0.1:5432`.
- Tables present: `admins` (11 columns, 0 rows), `admin_cart_discount_settings` (5 columns, 0 rows), `django_migrations` (4 columns, 1 row).
- Existing migration record: `adminapi.0001_cart_discount_settings` only.
- `py scripts/check_postgres_target.py`: passed.
- `py manage.py check`: passed.
- `py manage.py showmigrations --plan`: 19 migrations are pending; the existing cart-discount migration is marked applied. No migrations were run during this audit.
- React unit tests: 15/15 passed; production build passed.
- The database remains unchanged by this planning/audit work.

See `STOKIT_POSTGRESQL_TARGET_READONLY_AUDIT.md` and `.json` for live metadata.

## Source dump structural review

- Original dump: 134,426,410 bytes. Sanitized dump: 208,686 bytes. Their SHA-256 hashes are recorded in `STOKIT_SOURCE_SCHEMA_INVENTORY.json`.
- Both dumps contain 45 `CREATE TABLE` definitions, 92 `ALTER TABLE` statements, 39 `INSERT` statements, and one `CREATE TRIGGER` statement.
- The 45 table names match. Ordered, whitespace-normalized `CREATE TABLE` definitions and `ALTER TABLE` statements have matching SHA-256 fingerprints across original and sanitized dumps.
- The sanitized dump's current tuple scanner reports 3,224 tuples under both backslash-escape modes. The original dump's standard-escape scan also reports 3,224 tuples; the original no-backslash scan timed out. A previously noted 3,219-versus-3,224 discrepancy is therefore not reproduced by the completed scans but is not independently resolved. Do not use this as authorization to import data.
- These are structural checks, not a PostgreSQL grammar validation or a semantic conversion sign-off.

## Scope policy

The source dump has 45 tables. The 16 tables below remain excluded from phase one pending explicit owner review because prior dependency review identified possible application/PHP references. They must not be added automatically:

`users1`, `zg_api_keys`, `zg_banner`, `zg_brands`, `zg_cod`, `zg_headings`, `zg_headings_new`, `zg_logo`, `zg_product_warehouse`, `zg_reels`, `zg_social_media`, `zg_target_activity_log`, `zg_testy`, `zg_vari_product`, `zg_vari_product_images`, `zg_vari_variant`.

The remaining 29 source tables are *candidates for review*, not yet approved for creation. Verify endpoint and UI requirements against Flutter contracts and PHP dependency evidence before freezing the table manifest.

## Required implementation sequence

1. **Freeze schema decisions.** Resolve all items in `STOKIT_SCHEMA_DECISIONS_BLOCKERS.md`; explicitly decide table scope, constraints, conversions, trigger semantics, and time policy.
2. **Regenerate PostgreSQL candidate DDL.** Produce a review-only SQL file from approved scope and conversion rules. It must not contain `CREATE TABLE admins`, `CREATE TABLE admin_cart_discount_settings`, or any operation that alters/recreates existing target tables. Include only approved new tables, indexes, constraints, and triggers. Do not include data INSERTs.
3. **Validate offline.** Use a real PostgreSQL grammar parser against the entire candidate SQL; review parse errors, table/index/constraint counts, duplicate object names, FK dependencies, reserved words, mixed-case identifiers, and unsupported MariaDB features. Current environment has `sqlparse` only; it is not a PostgreSQL grammar parser. `pglast`/`sqlglot` are not installed.
4. **Review the change manifest.** Compare candidate DDL to the live target inventory and list every create/alter/index/constraint/trigger operation. Any existing-table alteration requires its own explicit approval. The first execution plan should create only reviewed missing objects.
- Recovery gate: PASS on 2026-10-15. Custom-format backup and isolated restore verified; see STOKIT_BACKUP_RESTORE_GATE_REPORT.md.
6. **Approval gate.** Obtain explicit approval for the exact candidate SQL, target database, operation list, and backup/restore result. Only then apply approved schema changes.
7. **Schema verification.** Re-query `information_schema`, `pg_constraint`, `pg_indexes`, and `django_migrations`; compare actual results to the approved manifest. Run DB-backed tests only against a verified isolated test target first.
8. **Admin provisioning gate.** After the role table and schema are verified, provision one React-compatible `admins` account with an explicit positive ID, hidden interactive password input, secure hash, and active `SUPER_ADMIN` role. Do not use a Django `createsuperuser` as a substitute; the React app authenticates against the legacy admin/role system.
9. **Application data gate.** Add only new test/business data explicitly requested by the user, through the application APIs or approved seed procedure. Never import legacy rows.
10. **Final validation.** Run backend checks, React tests/build, endpoint smoke tests, auth/role tests, and PostgreSQL-backed integration tests. Confirm PHP and Flutter files remain untouched.

## Current stop point

**No schema candidate has been approved or applied. No migrations have run. No administrator has been created. No historical data has been imported.**

The next action is to resolve the remaining table-scope, conversion, role-bootstrap, and migration-history decisions; generate and validate a complete legacy business-schema candidate; then review the exact operation manifest. Do not apply migrations or provision accounts until those gates are satisfied.
