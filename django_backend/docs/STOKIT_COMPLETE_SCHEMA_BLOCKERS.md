# StokIt Complete Schema Blockers

Status: Schema provisioned for the approved 43-table inventory; remaining compatibility blockers are documented in the execution update.

| ID | Blocker | Evidence / risk | Required resolution | Status |
|---|---|---|---|---|
| S01 | Table scope and excluded dependencies | Source inventory reports 45 tables; 16 remain excluded. | Trace PHP/API/UI/trigger/FK dependencies and obtain owner scope approval. | OPEN |
| S02 | admins ID and uniqueness | Existing target admins table; prior audit reports no username/email unique constraint. | Approve ID allocation and concurrency-safe uniqueness policy. | OPEN |
| S03 | React Super Admin bootstrap | React role contract includes SUPER_ADMIN; role assignment table pending. | Approve bootstrap actor, role assignment, and rollback procedure. | OPEN |
| S04 | zg_location.city_name collation | MariaDB uniqueness may differ from PostgreSQL. | Define and test case/accent/trailing-space semantics. | OPEN |
| S05 | zg_product.youtube_link prefix index | Source uses first-100-character prefix. | Approve equivalent PostgreSQL index strategy and query plan. | OPEN |
| S06 | ENUM-like fields | 13 enum-like fields reported. | Confirm labels, casing, invalid legacy values, and check/lookup approach. | OPEN |
| S07 | TINYINT(1) conversions | Five fields require semantic verification. | Verify actual values and boolean vs integer meaning. | OPEN |
| S08 | ON UPDATE CURRENT_TIMESTAMP | 11 source fields reported; seven in first phase. | Select trigger/application strategy and test write paths. | OPEN |
| S09 | update_target_progress_after_order trigger | Concurrency/retry semantics not validated. | Review source trigger and specify transaction-safe PostgreSQL equivalent. | OPEN |
| S10 | Six-digit checkout IDs | Random check-then-insert may race. | Define collision-safe allocator preserving API contract. | OPEN |
| S11 | zg_product.set_contains JSON | Legacy JSON validity unverified. | Profile source values and define validation/error policy. | OPEN |
| S12 | Timezone | USE_TZ=False; account migrations use timezone defaults. | Approve storage/API timezone policy. | OPEN |
| S13 | Django auth/contenttypes scope | React admin does not use Django built-in admin; migrations pending. | Approve whether these tables are required. | OPEN |
| S14 | Migration history | Only adminapi.0001_cart_discount_settings previously recorded. | Reconcile state without faking migrations or rewriting history. | OPEN |
| S15 | Complete SQL grammar validation | Prior validation covered managed tables only. | Generate approved legacy candidate and validate in isolation. | PARTIALLY VERIFIED |
| S16 | Recovery gate | Phase 2 report says backup/restore inventory matched. | Preserve report and verify backup before implementation. | RESOLVED WITH EVIDENCE (historical report) |
| S17 | Historical tuple count discrepancy | Phase 4 scan counted 39 INSERT statements and 3,224 tuples in both original and sanitized dumps under both escape modes; prior 3,219 result was not reproduced. | Identify provenance/parser version for the historical 3,219 count before declaring fully resolved. | PARTIALLY RECONCILED |
| S18 | Excluded-table dependencies | Prior report notes PHP references to excluded tables. | Produce per-table references and owner decisions. | OPEN |
| S19 | Inventory completeness | Derived from existing structural report. | Independently compare all names to original dump before final approval. | PARTIALLY VERIFIED |
| S20 | Target baseline | Phase 4 freshly verified target identity, three public tables, columns, constraints, indexes, exact row counts, and migration record read-only. | Re-run immediately before any separately approved implementation. | VERIFIED READ-ONLY IN PHASE 4 |

Do not execute DDL or migrations until blockers relevant to approved scope have evidence-backed resolutions.

## Phase 4 evidence and additional blockers (2026-10-15 21:45:11 +05:30)

| ID | Finding / blocker | Evidence | Status / required resolution |
|---|---|---|---|
| S21 | Active PHP source authority | Available PHP root C:/Users/.MSI/Downloads/StokIt_PHP_Backup_20261012/Host is a backup snapshot (153 PHP files); active source root not confirmed. | OPEN — identify authoritative deployed PHP revision and scan it before scope decisions. |
| S22 | Per-table excluded dependencies | Eight excluded tables have literal references in the scanned backup: zg_brands, zg_cod, zg_headings_new, zg_reels, zg_social_media, zg_testy, zg_vari_product_images, zg_vari_variant. Eight have no literal reference in this snapshot. | OPEN — trace routes/includes, indirect SQL, cron/admin workflows, FKs and owner decisions for all 16. |
| S23 | Existing admins ID allocation | Live admins.id is integer default 0, not identity/serial; no username/email unique constraints; row count 0. | OPEN — approve collision-safe ID generation and uniqueness/collation policy before any account/bootstrap work. |
| S24 | Existing cart-discount table DB defaults | Live table has no catalog defaults on its five columns; model defaults are application-side. | OPEN — confirm intended contract; do not alter existing table without separate approval. |
| S25 | Trigger conversion | Source trigger is AFTER UPDATE ON zg_checkout, conditional on transition to fulfilled, and updates target progress using checkout/order/product/category records. Full semantics/concurrency validation incomplete. | OPEN — inspect full trigger in authoritative source and approve transaction-safe PostgreSQL equivalent/tests. |
| S26 | Complete source reconciliation | Source column/key details were enriched from existing parsed inventory; original 134 MB dump not independently rescanned and active PHP source unconfirmed. | OPEN — independently reconcile dump/table/column/key/FK/trigger metadata; identify why the historical 3,219 count was previously reported. |
| S27 | DDL grammar validation | Candidate remains comments-only; no complete legacy candidate exists to parse. | OPEN — resolve scope/conversions, then validate only in verified isolated disposable database. |

### Per-table scan interpretation
The existing inventory JSON/Markdown now lists source columns, key definitions, PHP backup references, Django runtime references, Django test/migration/audit-tool references, and React literal table-name references for all 45 tables. These scans are evidence, not proof of runtime usage or non-usage. Classifications and approval values were not changed.



## Execution update (2026-10-15)

| Area | Current status | Evidence / next action |
|---|---|---|
| Approved table scope | RESOLVED FOR CURRENT MANIFEST | Target has 43 tables; 16 historical exclusions remain absent. Revisit only with authoritative active-source evidence and scope decision. |
| Django auth/contenttypes and migration history | RESOLVED FOR CURRENT TARGET | Normal migrations applied; 20 records; migrate --check passes. |
| Checkout target-progress trigger | VALIDATED IN ISOLATION | Corrected PostgreSQL trigger passes functional assertion. |
| Enum/JSON/identity/FK/timestamp sample behavior | VALIDATED IN ISOLATION | All 12 functional assertions pass; catalog validator 1,383 checks, 0 failures. |
| Checkout ID collisions | PARTIALLY RESOLVED | Django now retries real primary-key collisions; active PHP writer remains unconfirmed. |
| zg_location.city_name collation | OPEN | Source uses utf8mb4_uca1400_ai_ci; exact PostgreSQL case/accent/trailing-space parity remains unverified. |
| Excluded-table references | OPEN | Eight excluded tables have literal references in the available PHP backup. Confirm active source and dependencies before changing scope. |
| Admin ID/bootstrap | INTENTIONALLY DEFERRED | Existing admins table unchanged; no account created. Decide allocation/uniqueness/bootstrap policy before future account creation. |
| Browser-level end-to-end | BLOCKED BY TOOLING | Playwright CLI unavailable; no package installed without approval. HTTP/CORS smoke checks passed. |

Schema provisioning is complete for the approved inventory. Do not claim full behavioral parity until the remaining compatibility and browser-testing items are resolved.


## Continuation audit update (2026-10-15)

| Workstream | Latest evidence | Status | Next action |
|---|---|---|---|
| Target identity/inventory | Read-only Django connection: PostgreSQL 18.6, `stokit_postgres_dev`, `public`, 43 public tables; none of the 16 excluded names present. `admins=0`, `admin_cart_discount_settings=0`, `django_migrations=20`. | PASS for inventory checkpoint | Continue read-only verification only unless separately authorized. |
| `zg_location.city_name` collation | Only `und-x-icu` appeared in the inspected target ICU candidates; `und-u-ks-level1` is not installed there. Default equality was false for Kochi/kochi, café/cafe and Kochi/Kochi-space. No source-parity conclusion can be drawn. | BLOCKED | Test source semantics and candidate strategies in a disposable DB; document uniqueness/trailing-space behavior and obtain approval before target changes. |
| Active PHP provenance | Available root is the 153-file `StokIt_PHP_Backup_20261012\Host` snapshot; timestamps indicate backup-era files; no Git metadata at root. Active deployment revision remains unconfirmed. | BLOCKED | Obtain authoritative deployed source/commit or deployment confirmation. |
| Excluded table references | Literal backup references in `zg_brands`, `zg_cod`, `zg_headings_new`, `zg_reels`, `zg_social_media`, `zg_testy`, `zg_vari_product_images`, `zg_vari_variant`. No literal match in snapshot for `users1`, `zg_api_keys`, `zg_banner`, `zg_headings`, `zg_logo`, `zg_product_warehouse`, `zg_target_activity_log`, `zg_vari_product`. | PARTIAL | Trace includes/routes/cron and indirect SQL against authoritative source; keep all exclusions unchanged until owner decision. |
| Browser E2E | `playwright-cli` unavailable. HTTP checks: frontend 200; protected API unauthenticated 401; CORS preflight 200 with expected origin; backend root 404 (no root route observed). | BLOCKED BY TOOLING | Use approved browser automation/session; do not install dependencies without approval. |
| Authenticated admin workflow | Protected endpoint rejection verified; no account created. Authenticated navigation/CRUD not verified without an existing authorized test account. | PARTIAL / BLOCKED | Obtain authorization and credentials for an existing test account, or keep authenticated CRUD blocked. |

Safety: no target writes, schema changes, account creation, historical import, dependency installation, PHP/Flutter edits, or destructive cleanup occurred during this continuation audit. Overall project status remains PARTIAL.


### Excluded-table scan refinement (backup only)
- Direct SQL line evidence: `zg_brands` SELECT/INSERT/DELETE (`admin/manage/brands.php`); `zg_cod` SELECT/UPDATE/INSERT (`admin/manage/cod.php`); `zg_reels` SELECT/INSERT/UPDATE/DELETE (`admin/manage/reels.php`); `zg_testy` SELECT/INSERT/UPDATE/DELETE (`admin/manage/testmo.php`); `zg_headings_new` SELECT (`admin/manage/editProduct.php`, `admin/manage/product.php`); `zg_social_media` SELECT (`admin/manage/navbar.php`); `zg_vari_product_images` SELECT (`admin/manage/col.php`).
- `zg_vari_variant` has a literal match in `admin/manage/edit_col.php`, but the matched line is a comment; no direct SQL operation was confirmed by that line.
- No literal match in this PHP backup was found for `users1`, `zg_api_keys`, `zg_banner`, `zg_headings`, `zg_logo`, `zg_product_warehouse`, `zg_target_activity_log`, `zg_vari_product`.
- This is static line-level evidence only. It does not establish active deployment provenance, complete multiline SQL semantics, indirect dependencies, or runtime reachability. All 16 exclusions remain unchanged pending authoritative source and owner decision.

## Master completion pass (2026-10-16)

| ID | Finding | Status |
|---|---|---|
| S04 | zg_location.city_name collation: source behavior measured; best candidate leaves 1 of 23 cases unmatched; strategy needs approval | BLOCKED (was OPEN) |
| S18/S22 | Excluded-table dependencies: 14 of 16 referenced in backup PHP once the $qt prefix is resolved (earlier count of 8 was incomplete); runtime reachability unknown | PARTIAL (matrix complete, runtime BLOCKED) |
| S21 | Active PHP source authority: no VCS/deploy evidence; uniform extraction mtimes | BLOCKED - owner must supply deployed revision |
| S28 | Inventory JSON had a UTF-8 BOM (rejected by strict parsers) and omitted the 12 Django-managed tables; BOM removed, note added | RESOLVED (documentation) |
| S29 | Browser interaction and authenticated flows | BLOCKED - needs approved automation tool and authorized existing account |
| S30 | Disposable artifacts left in place for owner review/authorization to delete: PostgreSQL DBs stokit_collation_eval_20261015 (partial, failed run), ..._20261015b (failed run), ..._20261015c (final); temp dirs under %TEMP%: stokit_mariadb_eval_20261015, stokit_chrome_eval_20261016, stokit_e2e_20261016 | OPEN (housekeeping) |

Section-by-section detail and the 16-table matrix: see the primary execution report and the inventory.
