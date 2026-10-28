# StokIt PostgreSQL ? Schema Decisions and Blockers

Generated: 2026-10-15T20:44:15+05:30

This is a decision register. Nothing below has been treated as approved by inference. Resolve each item before finalizing candidate PostgreSQL DDL.

| ID | Topic | Required decision / evidence | Status |
|---|---|---|---|
| S01 | Phase-one table manifest | Confirm exact business tables to create; 16 excluded tables remain out until owner dependency review. | BLOCKED |
| S02 | `admins` table | Preserve existing table and PK. Choose explicit ID allocation policy. Decide whether username/email uniqueness constraints are required before first account. Existing app-level checks alone are not concurrency-safe. | BLOCKED |
| S03 | Admin role bootstrap | Create `accounts_adminroleassignment` only after DDL review. First account must be `SUPER_ADMIN`; confirm role bootstrap and actor policy. | BLOCKED |
| S04 | `zg_location.city_name` | Source uniqueness may be case/accent/trailing-space insensitive under MariaDB collation; PostgreSQL default UNIQUE is not semantically identical. Choose approved equivalent and tests. | BLOCKED |
| S05 | `zg_product.youtube_link` | Source prefix index (first 100 characters) was not represented in the previous candidate. Decide whether to preserve the prefix behavior and select a PostgreSQL expression/index strategy. | BLOCKED |
| S06 | ENUM-like fields | Review allowed labels and case policy for 13 ENUM-like fields. Define checks or lookup tables; do not silently widen/narrow values. | BLOCKED |
| S07 | Boolean conversions | Validate five `TINYINT(1)` fields and decide Boolean vs small integer where values/semantics require it. | BLOCKED |
| S08 | Timestamp update behavior | Decide how to preserve seven first-phase `ON UPDATE CURRENT_TIMESTAMP` fields (11 across the complete dump): triggers vs application updates; test all write paths. | BLOCKED |
| S09 | Trigger semantics | Review `update_target_progress_after_order` for exact PostgreSQL behavior, concurrency, transaction ordering, and duplicate/retry behavior. | BLOCKED |
| S10 | Checkout ID allocation | Existing six-digit random check-then-insert can race. Define collision-safe allocation while preserving the legacy string/API contract. | BLOCKED |
| S11 | JSON validity | Validate PostgreSQL equivalent for the `zg_product.set_contains` JSON check and edge cases. | BLOCKED |
| S12 | Timezone policy | Decide storage/serialization timezone policy and `USE_TZ` behavior before accepting timezone-aware columns in the accounts migrations. | BLOCKED |
| S13 | Django system tables | Decide exact scope for `auth_*` and `django_content_type`; current React admin does not use Django built-in admin. | BLOCKED |
| S14 | Existing migration history | Preserve `django_migrations` and its existing `adminapi.0001_cart_discount_settings` record. Reconcile model/migration state without `--fake` or history rewrites until reviewed. | BLOCKED |
| S15 | SQL grammar parser | PostgreSQL validated the managed Django candidate in an isolated restored database inside a rolled-back transaction. Full legacy-business conversion DDL has not been generated or validated. | PARTIAL |
| S16 | Recovery | Custom-format backup created and restored to an isolated database; exact table inventory, row counts, and migration records matched. See STOKIT_BACKUP_RESTORE_GATE_REPORT.md. | PASS |
| S17 | Dump tuple discrepancy | Sanitized dump scan reports 3,224 tuples in both escape modes; original standard mode reports 3,224, while original no-backslash scan timed out. Earlier 3,219-vs-3,224 discrepancy is not reproduced yet not independently explained. No import is permitted. | OPEN |
| S18 | Source dependencies | Some excluded tables are referenced in legacy PHP. Reconcile those references with active API/UI contracts and owner decisions before expanding scope. | BLOCKED |

## Fixed preservation requirements

- Existing target tables: `admins`, `admin_cart_discount_settings`, `django_migrations`.
- Do not drop, truncate, recreate, or blindly migrate these tables.
- No legacy `INSERT` data may be imported.
- Do not modify PHP or Flutter source.
- Do not create the React Super Admin until `accounts_adminroleassignment` and the schema are verified.
## Phase 2 update (2026-10-15)

- S15 is partially resolved for the generated Django-managed candidate only; the 29-table legacy schema conversion remains unvalidated.
- S16 recovery gate passed with a custom-format backup and isolated restore; the restore database is retained for inspection.
- S01-S14, S17, and S18 remain blocked/open as detailed above. No target migrations or account provisioning were performed.
