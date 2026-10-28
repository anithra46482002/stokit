# StokIt Complete DDL Validation Report

Status: NOT READY FOR HUMAN REVIEW as an executable complete schema.

## Phase 3 initial checks (historical)

- Cody workspace listing succeeded for the requested StokIt workspace.
- Existing Phase 2 source inventory, blockers, target audit, review, and migration files were read.
- Source table names were parsed from STOKIT_SOURCE_SCHEMA_INVENTORY.md; PowerShell reported 45 source tables and 16 excluded tables.
- The complete inventory JSON and Markdown were generated from the existing source inventory.
- PowerShell ConvertFrom-Json successfully parsed both generated JSON files in this session.

## Historical evidence (not rerun in this session)

STOKIT_POSTGRESQL_PHASE2_REVIEW.md reports successful backup/restore verification and rollback-only PostgreSQL validation of the Django-managed candidate on isolated database stokit_phase2_restore_verify_20261015_210457. It reports 17 migration-guard tests passed. Those results apply only to the managed candidate, not complete legacy DDL.

## Phase 3 gaps; Phase 4 update below

- At the time of the Phase 3 report, no fresh read-only connection to stokit_postgres_dev had been executed; Phase 4 subsequently completed this check.
- No complete legacy DDL was parsed or engine-validated; candidate SQL is comments-only because conversion decisions remain blocked.
- At Phase 3, no independent re-scan of the original 134 MB SQL dump or complete PHP/frontend dependency trace had been performed. Phase 4 rechecked tuple counts and ran partial literal-reference scans, but full source reconciliation remains incomplete.
- No target database writes, migrations, account creation, data import, package installation, or PHP/Flutter edits were performed.

## Conclusion

No executable complete DDL is supplied. Do not execute the earlier Phase 2 candidate as if it were the complete schema.

## Phase 4 checks (2026-10-15 21:45:11 +05:30)

### Workspace and source scans
- Cody workspace path verified: C:/Users/.MSI/Downloads/StokIt Backend; the eight existing STOKIT_COMPLETE artifacts were read before update.
- Updated the existing inventory JSON and Markdown in place. The JSON records source columns/key definitions and per-table reference evidence for all 45 tables; classifications and approvals remain unchanged.
- PHP backup snapshot C:/Users/.MSI/Downloads/StokIt_PHP_Backup_20261012/Host: 153 PHP files scanned. This is not confirmed as the active source. Django scan: 62 runtime app Python files and 34 test/migration/audit files. React scan: 20 JS/JSX/TS/TSX files.
- Excluded tables with literal PHP backup references: zg_brands, zg_cod, zg_headings_new, zg_reels, zg_social_media, zg_testy, zg_vari_product_images, zg_vari_variant. No literal PHP match was found for the other eight excluded tables in this snapshot. Missing literal references do not prove non-use; indirect routes/includes and active source remain unverified.

### Live PostgreSQL baseline
- Connection succeeded after loading the existing local PostgreSQL environment into the process without printing credentials.
- Read-only SQL used catalog SELECTs, exact COUNT queries and migration-history SELECT inside BEGIN READ ONLY, followed by ROLLBACK.
- Identity: stokit_postgres_dev, postgres, public, PostgreSQL 18.6, 127.0.0.1:5432.
- Public base tables: exactly 3 — admin_cart_discount_settings, admins, django_migrations.
- Counts: admins=0, admin_cart_discount_settings=0, django_migrations=1.
- Sole migration: adminapi / 0001_cart_discount_settings / 2026-10-15 15:44:38.022359+05:30.
- admins: id, username, email, fullname, password, phone, address, paymentDate, token, api_token, last_login; primary key on id; no username/email unique constraints; id default 0, not identity/serial.
- admin_cart_discount_settings: id, enabled, minimum_subtotal, fixed_discount_amount, updated_at; primary key on id; check id >= 0. No catalog defaults were found.
- django_migrations: id, app, name, applied; primary key on id; one record above.
- No DDL/DML, migrations, account creation, or historical import was executed.

### Conversion evidence and unresolved issues
- The existing source inventory reports 45 tables, 92 ALTER TABLE statements, 39 INSERT statements and one trigger. Original/sanitized table-name parity comes from the earlier inventory; the original 134 MB dump was not independently re-parsed in this run.
- The trigger starts AFTER UPDATE ON zg_checkout, conditional on a status transition to fulfilled; its visible logic recalculates target-assignment progress from checkout/order/product/category records. Full trigger semantics, concurrency/retry behavior, and PostgreSQL equivalence remain unvalidated.
- Tuple scan recheck: the existing scanner reports 39 INSERT statements and 3,224 tuples in both original and sanitized dumps under both escape modes. The earlier 3,219 count was not reproduced; its origin remains unknown. Active PHP source authority and table-scope decisions remain open, MariaDB collation, prefix index, ENUM values, TINYINT semantics, update timestamps, JSON validity, checkout ID allocation, timezone, admin ID/uniqueness, Super Admin bootstrap, auth/contenttypes scope, migration-history reconciliation, and complete DDL grammar validation.

### Conclusion
- Candidate SQL remains comments-only with zero executable operations. JSON validation was rerun after final document edits.
- No target writes, migrations, account creation, package installation, or PHP/Flutter edits occurred.
- Result: NOT READY FOR HUMAN REVIEW as an executable complete schema.




## Phase 5 execution results (2026-10-15)

- Corrected the translated checkout-progress trigger after isolated execution exposed an invalid reference to the UPDATE target alias. The corrected CTE/LATERAL implementation passes the target-progress functional assertion.
- Functional SQL no longer has the stray EOF_X marker. Assertions now raise exceptions on failure. All 12 assertions passed and the transaction rolled back with zero leftover users.
- Fresh backup django_backend/backups/stokit_postgres_dev_pre_full_schema_20261015.dump restored to isolated stokit_backup_restore_verify_20261015; table names, row counts, and migration records matched.
- Isolated database stokit_schema_validation_20261015_2: 43 public tables after legacy DDL, normal Django migrations, and copying the existing admins table definition for preservation coverage. Catalog validator: 1,383 checks, 0 failures.
- Applied validated 28-table legacy DDL to stokit_postgres_dev, then ran normal Django migrations without --fake. Target now has 43 public tables and 20 migration records. The original adminapi migration record remains.
- Target comparison confirms admins and admin_cart_discount_settings definitions and row counts are unchanged; all 16 excluded tables remain absent; all 28 new legacy tables contain zero rows.
- Backend tests: 86 passed. Frontend tests: 15 passed; Vite build passed; lint 0 warnings/errors.
- HTTP smoke: nonexistent login returned expected 401; protected cart-discount endpoint without credentials returned expected 401; frontend returned 200; CORS preflight returned 200.
- Remaining limitations: active PHP source unconfirmed; exact case/accent/trailing-space parity for zg_location.city_name is unverified; Playwright CLI unavailable; no authenticated admin workflow tested because no admin account may be created.


## Continuation audit checkpoint (2026-10-15)

- Fresh read-only Django connection confirmed target `stokit_postgres_dev` on PostgreSQL 18.6, schema `public`, with 43 public base tables. All 16 excluded historical table names remain absent. Counts: `admins=0`, `admin_cart_discount_settings=0`, `django_migrations=20`.
- Source collation `utf8mb4_uca1400_ai_ci` still has no proven PostgreSQL equivalent. Target catalog inspection found `und-x-icu`; `und-u-ks-level1` was not installed in the target. Default equality checks returned false for `Kochi`/`kochi`, `café`/`cafe`, and `Kochi`/`Kochi `; this is not source parity evidence. No target schema changes were made.
- Available PHP source remains an unversioned backup snapshot (153 PHP files; no Git metadata at its root). Eight excluded tables have literal references in that snapshot; active deployment provenance and indirect dependencies remain unresolved.
- Browser E2E remains blocked because Cody reports `playwright-cli not found on PATH`. Fresh HTTP smoke checks: frontend 200, unauthenticated protected endpoint 401, CORS preflight 200 with the expected origin; backend root 404 (no root route observed). No browser E2E claim is made.
- Authenticated admin CRUD remains unverified; no account was created.
- This checkpoint does not reverse the prior validated schema-provisioning evidence. It confirms the current approved inventory and records the remaining application/compatibility blockers. Overall status: PARTIAL, not full behavioral parity.

## Master completion pass (2026-10-16)

### zg_location.city_name collation (Workstream A)
Verified facts: source dump (MariaDB 11.8.9) declares the table with `DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci` and `UNIQUE KEY city_name (city_name)`; the PostgreSQL candidate is `varchar(100)` with the database default collation and `UNIQUE (city_name)`; the app searches with `ILIKE` (case-insensitive, accent-sensitive) in adminapi/operations.py and duplicate detection relies on the unique index.

Executable evidence: `scripts/schema_conversion/collation_eval.py` ran 23 value pairs on a disposable MariaDB 13.0.2 (temp datadir, port 3399, stopped afterwards; the original 11.8.9 server was not available) and on disposable PostgreSQL 18.6 databases (stokit_collation_eval_20261015c). Raw results: docs/STOKIT_CITY_NAME_COLLATION_EVAL.json.
- Source behavior measured (equal AND unique-collision): Kochi/kochi, cafe-acute/cafe, NFC/NFD, trailing space(s), trailing NBSP, sharp s/ss, ae ligature/ae, Istanbul dotted I, fullwidth, ligature fi, ZWJ, Kelvin sign, o-stroke, l-stroke, Malayalam vowel forms, and empty/space are all equal. Different: leading space, trailing tab, inner space, dotless i/i, hyphen, Kochi/Kochin. Equality and unique collision agreed for all 23 pairs.
- PostgreSQL candidates vs source (mismatching cases of 23): deterministic default 17; und-x-icu deterministic 17; nondeterministic ICU und-u-ks-level1 4 (trailing space, two trailing spaces, trailing NBSP, empty vs space); ks-level2 10; ks-level1 plus unique index on rtrim(city_name, ' ') 1 (trailing NBSP only).
- Query behavior: plain equality uses the unique index for all but the rtrim expression index, which is used only when the query repeats the same expression. `ILIKE` fails on nondeterministic collations (FeatureNotSupported), so the search would need `LIKE` (not recorded in the JSON) or normalization. ICU collations ci_ai/ci_as do not exist in the target; creating them is a schema change that was NOT made.
- Assumption vs fact: PAD SPACE behavior was measured on 13.0.2, not 11.8.9. Public MariaDB naming material lists uca1400_ai_ci and uca1400_nopad_ai_ci as separate collations, consistent with the measured padding, but one naming document is internally inconsistent, so the version-to-version claim is an inference.
- Proposed (needs approval): nondeterministic `und-u-ks-level1` collation on the column plus a unique expression index on `rtrim(city_name, ' ')`, with application queries using the same expression; decide NBSP handling and replace `ILIKE`. Trade-offs: nondeterministic collations are slower, cannot use LIKE-prefix index scans, and cannot back some features; the expression index changes how queries must be written.
- Regression tests added: adminapi/tests_city_name_collation.py (7 tests, DB-free): pins the measured source behavior, asserts the DDL candidate declares no collation, and carries one expectedFailure documenting that parity is not met. Status: BLOCKED (parity unproven; not changed).

Backend regression: 93 tests OK (1 expected failure) in an isolated database; catalog validation results from the earlier stage are unchanged (1,383 checks, 0 failures). Target re-verified read-only: 43 tables, 20 migration records.
