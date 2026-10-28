# StokIt PostgreSQL Database Provenance Review

**Review date:** 2026-10-16  
**Target:** `stokit_postgres_dev`, schema `public`, PostgreSQL 18.6, local endpoint `127.0.0.1:5432`  
**Mode:** read-only catalog, migration metadata, existing reports and log configuration review.  
**Status: PARTIAL — origin of the admin/business rows is not established.**

## 1. Executive conclusion

The latest target state is verified by the read-only audit script and is detailed in the fresh snapshot and DBA checklist below. It has 43 public base tables, 111 indexes, 13 foreign keys, 8 user triggers, and 20 Django migration records. The latest point-in-time count map contains 19 non-empty tables: 16 application/business tables and three Django metadata tables. No sensitive row values were queried or reported. Earlier point-in-time lists in this document are retained as historical evidence and are superseded for current counts by the latest snapshot in Sections 9–10.

Earlier documents recorded an earlier target snapshot with only three tables and one migration record, and later documents asserted that `admins` and business tables were empty. Those statements cannot all describe the same database state at the same time. The current counts are confirmed; the precise time, actor, client, and mechanism that created the later tables and business rows are **not proven** by the available catalog metadata.

No data, schema, migration state, account, service, backup, or temporary resource was changed by this review.

## 2. Current read-only evidence

Commands executed from `django_backend`:
- `python scripts/read_only_audits/list_tables_readonly.py`
- `python scripts/read_only_audits/final_target_verify_readonly.py`
- `python manage.py showmigrations --plan`
- `python manage.py migrate --check` (readiness check only; no migration applied)
- Read-only PostgreSQL metadata query for migration timestamps, server start time, log configuration, and recent log-file metadata.

Results: database `stokit_postgres_dev`; server PostgreSQL 18.6; schema `public`; current role `postgres`; 43 base tables; 111 indexes; 13 foreign keys; 8 non-internal/user triggers; 20 migration rows. All migrations shown by `showmigrations --plan` were marked applied and `migrate --check` exited successfully.

### Affected tables and counts

| Table | Earlier snapshot rows | Interpretation |
|---|---:|---|
| `accounts_adminroleassignment` | 1 | Role assignment record exists; contents not inspected |
| `admins` | 1 | Admin account record exists; credentials/fields not inspected |
| `notifications` | 1 | Business record exists; contents not inspected |
| `users` | 1 | Customer/user record exists; contents not inspected |
| `zg_category` | 1 | Catalog record exists; contents not inspected |
| `zg_product` | 1 | Catalog record exists; contents not inspected |
| `zg_product_images` | 1 | Product-image record exists; contents not inspected |
| `zg_slider` | 1 | Slider/banner record exists; contents not inspected |
| `zg_subcategory` | 1 | Catalog record exists; contents not inspected |
| `zg_variant` | 1 | Product variant record exists; contents not inspected |
| `auth_permission` | 128 | Django framework permission metadata |
| `django_content_type` | 32 | Django framework model metadata |
| `django_migrations` | 20 | Migration ledger |

This table records the earlier 10-application-table snapshot, not the latest state. The latest 19-table count map is in the fresh point-in-time snapshot addendum below. The other 30 tables were empty in that earlier snapshot; do not treat that historical count as current. `admin_cart_discount_settings` was empty in both observations.

## 3. Timeline from available evidence

| Evidence time / source | What it says | Provenance significance / limitation |
|---|---|---|
| `STOKIT_POSTGRESQL_TARGET_READONLY_AUDIT.md`, generated 2026-10-15 20:40:43 +05:30 | Target had 3 tables: `admins`=0, `admin_cart_discount_settings`=0, `django_migrations`=1; migration listed as `adminapi.0001_cart_discount_settings` | Earlier point-in-time snapshot; strongly supports that the later 43-table state was not present in this observed snapshot. |
| `STOKIT_BACKUP_RESTORE_GATE_REPORT.md`, generated 2026-10-15 21:05:01.7401024 +05:30 | Backup/restore comparison had 3 tables and 1 migration record; target DDL/DML was said not to have been executed in that gate | Supports preservation at that specific gate, not what happened later. |
| `STOKIT_FULL_SCHEMA_AND_APPLICATION_EXECUTION_REPORT.md`, generated/updated 2026-10-15 (report labels times as local) | Says 28 legacy tables were created, 19 pending migrations applied, total 43 tables and 20 migration records; also says `admins` and business tables had no rows | Documents a later provisioning phase, but its zero-row statements conflict with the current counts. The report alone is not a transaction log and does not establish who inserted current business rows. |
| Current `django_migrations` catalog query | 20 records; one record for `adminapi.0001_cart_discount_settings` timestamped 2026-10-15 15:44:38 +05:30; remaining 19 records timestamped 2026-10-16 04:03:28 +05:30 | Confirms migration-ledger timestamps as returned by the current session. Existing reports serialize the original timestamp without an explicit offset and may show UTC-naive values; do not compare timestamps until timezone conventions are normalized. |
| Current PostgreSQL server metadata | Postmaster start time returned as 2026-10-15 20:26:19.846740 +05:30; logging collector on; `log_statement=none`; `log_min_duration_statement=-1`; log files exist for multiple dates | Server start/log-file metadata can help establish service activity, but does not timestamp individual table creation or row inserts. With statement logging disabled and no slow-query threshold, logs are not configured to provide a complete SQL write history. |
| Current read-only table count scripts, 2026-10-16 | 43 tables, 111 indexes, 8 triggers; ten application tables listed above have one row each | Confirms present state only; does not identify the writer or write time. |

## 4. Confirmed facts vs hypotheses

### Confirmed
1. Current `stokit_postgres_dev.public` has 43 base tables, 111 indexes, 13 foreign keys and 8 non-internal triggers.
2. Current `django_migrations` has 20 rows. `showmigrations --plan` marks the listed migrations as applied; `migrate --check` reported no pending migration-state difference.
3. Ten application/business tables have one row each as listed in the table above. Their row contents were not queried.
4. An earlier dated audit reported only three tables, with `admins` and cart-discount settings empty and one migration record. The backup/restore gate independently records a matching 3-table/1-migration snapshot.
5. The later execution report documents a schema-provisioning phase and 19 migrations but contains statements that business tables remained empty. Its data-state claims are stale or otherwise inconsistent with current evidence.
6. PostgreSQL catalog metadata does not generally store a reliable `created_at` timestamp or creator identity for each table/index/trigger/row. The current server setting `log_statement=none` and `log_min_duration_statement=-1` means normal statement-level history cannot be assumed from PostgreSQL logs.
7. A read-only scan of the current migration source files found no `RunPython`, `RunSQL`, literal `INSERT INTO`, `objects.create`, or `bulk_create` matches in the inspected migration directories. This suggests those migration files are not an obvious explanation for business-row seeding, but does not exclude triggers, external SQL, other code, manual operations, or unsearched paths.

### Hypotheses — not established
- The rows may have been created by manual SQL, an application/API workflow, an initialization script, another agent/tool, a test or setup command, or an operation omitted from/stale in the reports. No available evidence distinguishes these possibilities.
- The 19 migration records and 43-table schema may correspond to the documented provisioning phase, but timestamps and report labels use potentially inconsistent timezone conventions. The precise order of individual DDL/DML actions cannot be reconstructed from the migration ledger alone.
- The `admins` row and role-assignment row may be related, but their association was deliberately not inspected; do not infer identity, credentials, or actor.
- The catalog rows in `users` and catalog tables may be fixture/demo/operational data, but their purpose and origin are unknown.

## 5. What remains unknown

- Exact timestamp and SQL statement that created each non-empty application row.
- Process, database session, operating-system user, application identity, or human/agent that executed each write.
- Whether any writes were approved, accidental, test setup, or part of a documented implementation step.
- Whether historical data was imported, whether individual rows were manually inserted, or whether the application created them. The current counts alone cannot answer this.
- Whether any relevant audit/PowerShell/Cody/terminal history exists and is complete; it was not treated as authoritative evidence in this pass.
- Whether PostgreSQL logs contain any useful connection/error events for the relevant window. Logging configuration confirms that a complete SQL statement audit trail is not available from the normal statement logging settings; no claim of a successful statement-level log reconstruction is made.
- The timezone used by each historical report serializer where it emitted timestamps without an offset.

## 6. Risks

- **Safety risk:** treating the target as empty could lead to destructive cleanup or overwriting data that now exists.
- **Audit risk:** stale reports can cause incorrect claims about when schema and rows appeared.
- **Security risk:** an admin record exists, but its authorization, owner, and provenance have not been verified. Do not read or print its credentials.
- **Integrity risk:** the one-row counts do not prove cross-table relationships or that these rows are legitimate. No row-level relationship checks were run because the request limits inspection to metadata/counts.
- **Evidence gap:** with statement logging disabled, the migration ledger records migrations, not arbitrary DML. It cannot explain business rows.

## 7. Safest next steps (no fix attempted)

1. Preserve the current target unchanged. Do not delete rows, reset tables, re-run migrations, restore backups over the target, or create another account.
2. Ask the database/project owner to identify and approve the provisioning window and compare any contemporaneous operation log, shell history, deployment/agent transcript, or backup/restore log that they authorize reviewing. Keep secrets and row contents redacted.
3. Normalize all report timestamps to a single explicit timezone before comparing events. Retain original timestamps and document conversions rather than rewriting historical reports.
4. If available and authorized, have the DBA inspect external Windows service/process logs, PostgreSQL log files, and database backup/restore command history for the time window. Current PostgreSQL configuration does not provide a guaranteed statement audit trail.
5. If provenance cannot be established, record the rows as unexplained existing state and require owner approval before any future change. Keep status **PARTIAL**.

## 8. Changes made

Only documentation files requested by the user are to be updated. No application source, PHP/Flutter source, schema, data, migration history, accounts, services, backups, or temporary resources were changed by this review.


## Addendum: fresh point-in-time snapshot (2026-10-16)

A subsequent execution of `python scripts/read_only_audits/final_target_verify_readonly.py` observed the following state. This is a newer observation than the earlier 10-application-table count in Sections 1–4; it does not prove when or how any additional row appeared.

- Identity: `stokit_postgres_dev`, PostgreSQL 18.6, schema `public`.
- 43 public base tables; 111 indexes; 8 non-internal triggers; 20 `django_migrations` records. All migrations shown by `python manage.py showmigrations --plan` are marked applied; `python manage.py migrate --check` exited 0.
- Non-empty tables and counts reported by the read-only verifier:

| Table | Rows |
|---|---:|
| `accounts_adminroleassignment` | 1 |
| `admins` | 1 |
| `advance_pay_allocations` | 1 |
| `advance_pay_offers` | 1 |
| `auth_permission` | 128 |
| `delivery_boys` | 1 |
| `django_content_type` | 32 |
| `django_migrations` | 20 |
| `notifications` | 1 |
| `salesmen` | 1 |
| `users` | 1 |
| `zg_category` | 1 |
| `zg_location` | 1 |
| `zg_product` | 1 |
| `zg_product_images` | 1 |
| `zg_slider` | 1 |
| `zg_subcategory` | 1 |
| `zg_variant` | 1 |
| `zg_warehouse` | 1 |

There are now 19 non-empty tables in this snapshot: 16 application/business tables and three Django metadata tables. The six additional application tables observed relative to the earlier list are `advance_pay_allocations`, `advance_pay_offers`, `delivery_boys`, `salesmen`, `zg_location`, and `zg_warehouse`. This is a comparison between observations only, not evidence that those rows were created during this run or by any particular actor.

No row values were selected or exposed. The verifier connected read-only, set `conn.read_only = True`, and rolled back. This run did not write database data, schema, or migration state. The existing logging configuration still does not provide a complete SQL statement audit trail. The provenance and authorization of every non-empty application table remain unresolved; preserve all records and keep status PARTIAL.

## DBA reconciliation checklist (2026-10-16; read-only until owner authorizes evidence review)

The latest verifier again reported 43 tables, 111 indexes, 8 user triggers and 20 migration records. Non-empty tables and counts are:

| Table | Rows | Table | Rows |
|---|---:|---|---:|
| `accounts_adminroleassignment` | 1 | `admins` | 1 |
| `advance_pay_allocations` | 1 | `advance_pay_offers` | 1 |
| `auth_permission` | 128 | `delivery_boys` | 1 |
| `django_content_type` | 32 | `django_migrations` | 20 |
| `notifications` | 1 | `salesmen` | 1 |
| `users` | 1 | `zg_category` | 1 |
| `zg_location` | 1 | `zg_product` | 1 |
| `zg_product_images` | 1 | `zg_slider` | 1 |
| `zg_subcategory` | 1 | `zg_variant` | 1 |
| `zg_warehouse` | 1 | | |

Do not select row contents as part of this checklist. Preserve all rows.

1. **Confirm identity/time:** DBA records server/database/schema, current timezone and exact UTC offset; retain the original report timestamps and explicitly normalize UTC-naive historical timestamps.
2. **Reconcile migration ledger:** compare all 20 migration names and applied timestamps with approved deployment/terminal/Cody execution records. The ledger establishes migration application records, not arbitrary business DML.
3. **Reconcile DDL window:** compare the earlier 3-table snapshot with the documented 43-table provisioning report and authorized database/backup/restore activity. PostgreSQL catalogs do not prove object creator/time reliably.
4. **Review available audit sources:** with owner authorization, inspect PostgreSQL logs, Windows service/process logs, PowerShell/terminal transcripts, deployment logs, backup/restore command logs and automation/agent histories for the relevant time window. Current `log_statement=none` and `log_min_duration_statement=-1` mean a complete SQL write history cannot be assumed. Keep credentials and sensitive payloads redacted.
5. **Establish write attribution where evidence exists:** record timestamp/timezone, source artifact, operation, actor/process identity if actually evidenced, and approval reference. Separate facts from inference; do not infer the actor from a row count or migration timestamp.
6. **Owner acceptance:** the owner/DBA classifies each non-empty application table as authorized operational data, approved fixture/demo data, unapproved/unknown data, or unresolved. This classification must be based on evidence, not inspection of secrets.
7. **Close-out:** attach redacted evidence references, identify remaining unknowns, and obtain written approval for any future action. Until then, no deletion, reset, update, import, restore, or migration is permitted.

## City collation compatibility proposal — not applied

Source evidence describes MariaDB `utf8mb4_uca1400_ai_ci` behavior. Existing tests cover case-insensitivity, accent-insensitivity, Unicode normalization, trailing spaces, and distinctions such as leading spaces/tabs; the current PostgreSQL default fails multiple parity cases. The best evaluated expression strategy (`ks-level1` plus `rtrim` unique expression index) still mismatches trailing NBSP, and the target currently has no evaluated custom collation installed. Source test evidence was produced on MariaDB 13.0.2 while the source dump reports 11.8.9, so version-specific parity is not yet proven.

Recommended isolated evaluation only: (a) obtain owner-approved rules for case, accents, NFC/NFD, ASCII trailing spaces, trailing NBSP, leading spaces, tabs, punctuation and uniqueness collisions; (b) build a disposable PostgreSQL comparison harness for a reviewed ICU collation or deterministic normalized-key strategy; (c) compare every source test pair and duplicate-insert/unique-index behavior against an authoritative MariaDB 11.8.9-compatible source; (d) add Django/database-independent regression tests plus disposable-DB integration tests; (e) document index/query planner and migration implications; (f) prepare exact DDL/migration and rollback plan for owner review. Do not install extensions, alter target collations, create indexes, or apply migrations to `stokit_postgres_dev` without explicit approval.

## Continuation note — read-only provenance and validation updates (2026-10-16)

The current read-only verifier was rerun after the application-only fixes. It still reports PostgreSQL 18.6, database stokit_postgres_dev, schema public; 43 base tables; 111 indexes; 8 user triggers; 20 django_migrations rows; and the same 19 non-empty tables recorded in the previous count map. No excluded-table names appeared in the target. This is a matching count snapshot only; it does not establish the origin, owner, timing or authorization of any row.

The application changes in this continuation were limited to React pagination handling and Django request validation for product/subcategory relationships, finite monetary values, GST/discount values and whole-number variant quantities. The test suite used database-independent tests; the Django runner reported no test database setup. No SQL writes, DDL, migrations, imports, restores, account creation or cleanup were performed. No row contents were read. PHP and Flutter source remained read-only.

### Acceptance evidence that remains missing

1. Owner/DBA reconciliation of populated-table counts against authorized provisioning, agent, shell, application and restore history.
2. An authoritative active PHP deployment revision/hash and an owner decision for every excluded table, especially zg_product_warehouse.
3. Written source-compatible collation and trailing-NBSP policy, followed by tests only in a disposable isolated database.
4. An approved isolated integration database, approved disposable fixtures, and existing authorized test accounts/roles.
5. Executed authenticated API/browser tests with before/after assertions on the isolated database; no target write tests are authorized by this review.

Keep the current target unchanged. Count equality is not provenance proof, and the project status remains PARTIAL.
