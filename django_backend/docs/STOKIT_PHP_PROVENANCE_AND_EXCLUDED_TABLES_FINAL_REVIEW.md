# STOKIT PHP Provenance and Excluded-Table Final Review

Date: 2026-10-16 | Scope: read-only documentation | Status: **PARTIAL / BLOCKED — owner decisions required**

Labels: **VERIFIED** = observed directly in this session; **HISTORICAL** = carried from earlier reports/JSON, not re-measured today; **INFERRED** = reasoned, not measured; **UNRESOLVED** = cannot be established from available evidence.

No schema, application code, PHP/Flutter source, database, or temporary resource was changed. The 43-table schema and the 20-record migration history are untouched. Location note: the task named `docs/`; this file sits beside its sibling reports in `django_backend/docs/`.

## 1. Provenance summary

**Deployment provenance of the PHP backend is UNVERIFIED. `phpref` must not be treated as the deployed production version.**

| # | Finding | Status |
|---|---|---|
| 1 | Workspace alias `stokit_php` points to `...\StokIt Backend\StokIt Backend\Host`. `Test-Path` returned False and the directory holds 0 items. The path is **unavailable**. | VERIFIED (today) |
| 2 | `phpref` = `C:\Users\.MSI\Downloads\StokIt_PHP_Backup_20261012\Host` is the only available PHP reference. It holds 153 `.php` files. | VERIFIED (today) |
| 3 | All 153 `phpref` PHP files exist in `C:\Users\.MSI\Downloads\StokIt Backend.zip` under `StokIt Backend/Host/` with identical byte size (0 missing, 0 size differences). The earlier session reported a content match against the originals; today's recheck compared names and sizes only, not hashes. | VERIFIED (size/name today); content match HISTORICAL |
| 4 | The ZIP also holds macOS `__MACOSX` resource-fork copies (`._*`), which inflate raw entry counts (1,960 file entries; 967 under `StokIt Backend/Host`). Counts of "files" must exclude them. | VERIFIED |
| 5 | No `.git`, manifest, checksum, or deploy file was found in `phpref` (only `.htaccess`). No Git metadata at the workspace roots. | VERIFIED (earlier pass; `phpref` listing reconfirmed today: `admin`, `api`, `st-new-2`, `.htaccess`) |
| 6 | No deployment manifest, release tag, host file listing, or access log is available. | UNRESOLVED |

## 2. Dates and timestamps

| Source | Timestamp | Meaning |
|---|---|---|
| `phpref` files and folders | 2026-10-09 10:03:59 to 10:04:09 (+05:30) | Extraction/copy time. **Not** edit history. |
| `StokIt Backend.zip` (file) | 2026-10-09 10:03:11 | ZIP creation time. |
| ZIP entry `u144866523_stokitDB.sql` | 2026-10-09 09:57:50 | SQL dump time inside the ZIP. |
| ZIP entry `Host/api/tokens.txt` | 2026-10-09 09:52:22 | Pre-extraction file time. |
| ZIP entry `Host/api/aspi_cart_error.log` | 2026-10-08 20:26:12 | Pre-extraction file time. |
| `api/aspi_cart_error.log` entries | first 13-Jul-2026 03:50:21, last 08-Oct-2026 14:56:13 | Latest PHP runtime activity recorded in the backup. |
| `api/advance_pay_offers_error.log` entries | 16-Jul-2026 11:37:08 to 18-Jul-2026 08:44:47 | |
| `admin/manage/error_log` entries | 21-Mar-2025 to 06-Aug-2025 | Old admin-side errors. |
| `admin/manage/acc/error_log`, `api/acc/error_log` entries | 22-Jan-2025 to 03-Aug-2025 | |
| `admin/manage/telebers_DB_2025-12-24-17-58-59.sql` | named 2025-12-24 | Name-embedded date of an older SQL backup inside `admin/manage/`. |

Interpretation (INFERRED): the newest runtime evidence is 2026-10-08, one day before the backup was packaged. That suggests the backup is recent, but it does not prove the files match what was running. A second PHP tree, `st-new-2/`, is also present in the backup (it carries its own `manage/config.php` with `$qt ='zg'`); which tree was live is UNRESOLVED.

## 3. Host and endpoint discrepancy

- Flutter source (`stokit_flutter` workspace, `lib/core/constants/api_constants.dart`) sets the active base URL to `https://app.stokitb2b.com/api` (line 8). **VERIFIED today.**
- The same file carries commented-out earlier bases, including `https://projects.teleber.tech/stokit`, `https://admin.stokitb2b.com/api`, and `https://projects.teleber.com/st-new/`. **VERIFIED today.**
- The backup logs (`aspi_cart_error.log`, `advance_pay_offers_error.log`) cite server paths under `/home/u144866523/domains/projects.teleber.tech/`. **VERIFIED today.** This is a different host from the Flutter active base URL.
- Meaning (INFERRED, not proven): the backup may come from an older or staging host (`projects.teleber.tech`) rather than the host behind `app.stokitb2b.com`. Alternatively one hosting account may serve both. **UNRESOLVED.**

## 4. Sensitive-looking files (existence only)

Contents were **not opened, hashed, or reproduced**. Names, sizes and dates only.

| File | Where | Size | Note |
|---|---|---|---|
| `api/tokens.txt` | `phpref` and inside the ZIP | 113,226 bytes | Sensitive-looking name. Treat as a credential/token store until the owner confirms otherwise. |
| `u144866523_stokitDB.sql` | inside the ZIP (134,426,410 bytes) and `C:\Users\.MSI\Downloads\stokit_sql_work\` | 134,426,410 bytes | Full database dump; likely contains customer and credential data. A 208,686-byte `.sanitized.sql` also exists beside it. |
| `admin/manage/telebers_DB_2025-12-24-17-58-59.sql` | `phpref` and ZIP | 25,859 bytes | Older SQL backup inside the web root. |
| `admin/manage/config.php`, `st-new-2/manage/config.php` | `phpref` | not opened beyond the `$qt` line | Typically hold database credentials. |

Recommendation (PROPOSED): the owner should decide whether `tokens.txt` and the SQL files, if they sit in a web-reachable folder on the live host, need rotation of any tokens and removal from the web root. No such action was taken here.

## 5. Table-prefix resolution

`$qt = 'zg'` is set in `admin/manage/config.php:14` and `st-new-2/manage/config.php:14`; `admin/manage/q.php` (lines 4, 189) and fallbacks in `admin/manage/get_target_data.php:11`, `admin/manage/targets.php:17` and `api/targets.php:14` default to `'zg'`; `api/sub_categories.php:35` sets `$table_prefix = $qt ?? 'zg'`. **VERIFIED today.**

Consequence: SQL such as `FROM {$qt}_api_keys` resolves to `zg_api_keys`. An earlier literal-name scan missed this and reported only 8 referenced tables; the resolved scan reports **14 of 16** referenced. That correction stands. 350 dynamic-name candidate lines exist in the JSON; only the `$qt` / `$table_prefix` pattern was resolved, so other dynamically built names are **not ruled out**.

## 6. Excluded tables, individually

Source: `STOKIT_EXCLUDED_TABLE_DEPENDENCY_MATRIX.json` (HISTORICAL, produced 2026-10-16 by `scripts/read_only_audits/excluded_table_dependency_audit_readonly.py`; references re-read today). All paths below are under `admin/manage/` of `phpref`. Operation labels are keyword heuristics (nearest SQL keyword before the table name). Dump row counts are approximate figures from the source dump (HISTORICAL). **Replacement status for every table: none. No Django runtime, test or React reference exists for any of the 16.** All hits are in `admin/manage/`; none are in `api/` files used by Flutter.

### 6.1 `zg_api_keys` (special attention)
- References (8): `keys.php` lines 18, 35 (SELECT); 84, 87, 137 (UPDATE); 97, 100 (INSERT); 120 (DELETE). Functions include `getAllKeys`, `getGroupedKeys`, `getKeyById`.
- Feature: admin management of service/payment API keys (columns include key_type, service_name, key_value, merchant_id, salt_key) [INFERRED from SQL column names; values not read].
- Dump rows: ~0. FKs/triggers: none.
- Replacement: none. Risk: **HIGH if the PHP admin is live** — payment-gateway key management would have no Django equivalent, and any live PHP code that reads keys at runtime (for example checkout or payment callbacks reading by key_type) would break. No `api/` reference was found, so Flutter-facing PHP does not read it directly. Whether any other process reads the table is UNRESOLVED.
- Secret handling: key values live in the table, not in this repo; none were read or reproduced.

### 6.2 `zg_product_warehouse` (special attention — many-to-many)
- References (8): `editProduct.php` 80 (SELECT), 258 (DELETE), 261 (INSERT); `product.php` 60 (SELECT), 144 (DELETE); `warehouse_details.php` 161 (comment-only), 165 and 224 (SELECT).
- Feature: product-to-warehouse assignment. Edit-product deletes and reinserts assignment rows; the product list joins the table; warehouse details reads it [INFERRED from operations].
- Dump rows: ~9. FKs: `product_id` → `zg_product`, `warehouse_id` → `zg_warehouse`. Triggers: none.
- Structure: this is a **many-to-many link table** (a product can be in several warehouses; a warehouse holds many products). The table is absent from the approved 43-table schema, so the target currently has no product-to-warehouse assignment structure (how the Django Warehouse and Inventory views cope without it was not re-examined here). Any decision to restore it must also decide cascade behavior on product/warehouse deletion, and how the React admin inventory and warehouse pages and `legacy_api` stock logic would read it.
- Replacement: none. Risk: **HIGH if used** — FK-linked assignment data with no Django equivalent; Django `WarehouseAdminView` and `InventoryAdminView` do not read it.

### 6.3 Remaining fourteen

| Table | Exact references (file:line:operation) | Feature (INFERRED) | Dump rows / FKs | Risk of continued exclusion |
|---|---|---|---|---|
| `users1` | none | Unknown; name suggests a legacy user copy | ~2 / none | Low |
| `zg_banner` | `ban_timer.php`:28,37,48,147,184,200,224,230,432 SELECT; 134,208,213 UPDATE; 168 INSERT; 191 DELETE. `login.php`:105 SELECT | Admin-login-page banner and countdown timer; distinct from the Django banner model (`zg_slider`) | ~1 / none | Medium if PHP admin live |
| `zg_brands` | `brands.php`:49 INSERT; 66,82,273 SELECT; 75 DELETE | Brand list management | ~3 / none | Medium |
| `zg_cod` | `cod.php`:24,39 SELECT; 100 UPDATE; 110 INSERT | Cash-on-delivery settings | ~1 / none | Medium; may influence checkout behaviour if PHP checkout reads it (not seen in `api/`) |
| `zg_headings` | `heading4.php`:18 SELECT; 46 UPDATE | Storefront/app heading text | ~1 / none | Medium |
| `zg_headings_new` | `editProduct.php`:14 comment-only, 15 SELECT; `headings.php`:30,61,88,146 SELECT; 43,74,153 UPDATE; 164 INSERT; `product.php`:11 comment-only, 12 SELECT | Product-page headings | ~7 / none | Medium |
| `zg_logo` | `logo.php`:44,81,138,206,212 SELECT; 59,96 DELETE; 174 UPDATE; 178 INSERT | Site logo and favicon | ~2 / none | Medium |
| `zg_reels` | `reels.php`:84,90 SELECT; 51 UPDATE; 59 INSERT; 72 DELETE | Reels/video content (Instagram embed) | ~1 / none | Medium |
| `zg_social_media` | `navbar.php`:3 SELECT; `social.php`:18 SELECT, 41 UPDATE | Social links | ~1 / none | Medium |
| `zg_target_activity_log` | none | Unknown; name suggests a target-activity audit log | ~0 / none | Low |
| `zg_testy` | `testmo.php`:59,104,122,133 SELECT; 68,87 UPDATE; 71,90 INSERT; 112 DELETE; 127 comment-only | Testimonials | ~4 / none | Medium |
| `zg_vari_product` | `add_col.php`:89 INSERT; `col.php`:44 SELECT, 331 DELETE; `edit_col.php`:22 SELECT, 77 UPDATE; `edit_col_.php`:22 SELECT, 70 UPDATE | Variant-collection ("col") products | ~0 / none | Medium |
| `zg_vari_product_images` | `add_col.php`:108 INSERT; `col.php`:270,319 SELECT, 329 DELETE; `edit_col.php`:27,108 SELECT, 97 INSERT, 115 DELETE, 121,122 UPDATE; `edit_col_.php`:27,101 SELECT, 90 INSERT, 108 DELETE, 114,115 UPDATE | Images for variant-collection products | ~0 / none | Medium |
| `zg_vari_variant` | `col.php`:330 DELETE; `edit_col.php`:34 SELECT, 126 comment-only, 127 DELETE, 137 INSERT | Variants of variant-collection products | ~0 / none | Medium |

Cross-cutting notes:
- The three `*_vari_*` tables are one feature (variant-collection products) and should be decided together; `edit_col.php` and `edit_col_.php` look like a live and a backup copy of the same page (INFERRED from names).
- `zg_headings` and `zg_headings_new` overlap; confirm whether `zg_headings` is superseded.
- A previous report described `zg_vari_variant` as comment-only. Today's JSON shows SQL DELETE/SELECT/INSERT hits; the comment-only description is **superseded**.

## 7. Verified, inferred, unresolved

| Verified | Inferred | Unresolved |
|---|---|---|
| `stokit_php` path missing; `phpref` has 153 PHP files all present in the ZIP with identical sizes | `phpref` is a recent snapshot (newest log 2026-10-08) | Which tree and revision was deployed |
| `$qt = 'zg'` and fallback defaults | Feature purposes of each excluded table (from names and columns) | Whether `projects.teleber.tech` and `app.stokitb2b.com` are the same host |
| 14 of 16 tables have SQL references, all in `admin/manage/` | The `*_vari_*` pair and `edit_col*` files are duplicates of one feature | Whether the PHP admin is still used, by whom, and which pages |
| No excluded table is referenced by Django runtime, React, or `api/` files | Only `$qt` was resolved among 350 dynamic-name lines | Indirect, cron, include or external-process use of any table |
| Existence and size of `tokens.txt` and SQL dumps | Rows in the dump are approximate | Whether any secret in those files is still valid |
| Flutter active base URL is `https://app.stokitb2b.com/api` | | Current existence of data in the live tables |

A static backup scan is not proof that any table is unused or used in production.

## 8. Owner-decision checklist (scope of each excluded table)

For each table choose one: **Keep excluded** (feature retired or handled elsewhere) / **Restore as-is later** (needs separate schema approval) / **Replace with a Django-native design** / **Need evidence first**.

Prerequisite for every row: owner supplies the deployed commit/tag, a host file listing with hashes, or a hosting-panel export, and states whether the PHP admin remains in use.

- [ ] `users1` — Keep excluded / Need evidence first
- [ ] `zg_api_keys` — decide with security review; do not restore blindly; decide where payment/service keys live in the new system
- [ ] `zg_banner` — login-page banner/timer still wanted?
- [ ] `zg_brands`
- [ ] `zg_cod`
- [ ] `zg_headings`
- [ ] `zg_headings_new`
- [ ] `zg_logo`
- [ ] `zg_product_warehouse` — include cascade and many-to-many semantics; decide how the React Warehouse and Inventory pages should model assignment
- [ ] `zg_reels`
- [ ] `zg_social_media`
- [ ] `zg_target_activity_log` — Keep excluded / Need evidence first
- [ ] `zg_testy`
- [ ] `zg_vari_product`, `zg_vari_product_images`, `zg_vari_variant` — decide as one feature
- [ ] Is the legacy PHP admin to be retired entirely once Django/React is accepted? (If yes, most rows resolve to Keep excluded.)
- [ ] Owner decision on `tokens.txt` and SQL dumps in the web root: rotate and remove?

NOT EXECUTED: any table creation, restoration, data import, or PHP change.
