"""One-shot report updater for the 2026-10-16 master completion pass (documentation only; idempotent)."""
import json
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"
MARK = "## Master completion pass (2026-10-16)"
m = json.loads((DOCS / "STOKIT_EXCLUDED_TABLE_DEPENDENCY_MATRIX.json").read_text(encoding="utf-8"))
ev = json.loads((DOCS / "STOKIT_CITY_NAME_COLLATION_EVAL.json").read_text(encoding="utf-8"))

PURPOSE = {
    "users1": "Unknown (no code reference found); name suggests a legacy user copy [inference]",
    "zg_api_keys": "Admin management of service/payment API keys (key_type, service_name, key_value, merchant_id, salt_key) [inferred from SQL columns]",
    "zg_banner": "Admin-login-page banner and countdown (ban_timer.php, login.php) [inferred]; distinct from the Django banner model (zg_slider)",
    "zg_brands": "Brand list management (brands.php) [inferred]",
    "zg_cod": "Cash-on-delivery settings (cod.php) [inferred]",
    "zg_headings": "Storefront/app heading text (heading4.php) [inferred]",
    "zg_headings_new": "Product-page headings (headings.php, product.php, editProduct.php) [inferred]",
    "zg_logo": "Site logo and favicon files (logo.php) [inferred]",
    "zg_product_warehouse": "Product-to-warehouse assignment; FKs to zg_product and zg_warehouse; INNER JOIN in the PHP product list [inferred]",
    "zg_reels": "Reels/video content management (reels.php) [inferred]",
    "zg_social_media": "Social links (social.php, navbar.php) [inferred]",
    "zg_target_activity_log": "Unknown (no code reference found); name suggests a target activity audit log [inference]",
    "zg_testy": "Testimonials (testmo.php) [inferred]",
    "zg_vari_product": "Variant-collection ('col') products (add_col.php, col.php, edit_col*.php) [inferred]",
    "zg_vari_product_images": "Images for variant-collection products [inferred]",
    "zg_vari_variant": "Variants of variant-collection products; only a delete comment plus SQL found [inferred]",
}
RISK = {
    "users1": "Low", "zg_target_activity_log": "Low",
    "zg_api_keys": "High if the PHP admin is live: payment-key management has no Django equivalent",
    "zg_product_warehouse": "High if used: FK-linked assignment data; PHP product list joins it; no Django equivalent",
}


def ops(hits):
    c = {}
    for h in hits:
        c[h["kind"]] = c.get(h["kind"], 0) + 1
    return ", ".join(f"{k} x{v}" for k, v in sorted(c.items())) or "none"


rows = ["| Table | PHP backup references (operation counts) | Source path : function | Inferred business purpose | Dump rows (approx) / FKs / triggers | Django runtime / React refs | Risk of continued exclusion |",
        "|---|---|---|---|---|---|---|"]
for t, d in m["tables"].items():
    hits = d["php_hits"]
    locs = sorted({f'{h["file"]}:{h["function"]}' for h in hits})
    dump = d["dump"]
    fks = "; ".join(dump["outbound_fk"] + ["in:" + x for x in dump["inbound_fk"]]) or "none"
    viapre = sum(1 for h in hits if h.get("via_prefix_variable"))
    rows.append("| `{}` | {} (hits {}, {} via $qt prefix) | {} | {} | ~{} / {} / {} | {} / {} | {} |".format(
        t, ops(hits), len(hits), viapre, "<br>".join(locs) or "-", PURPOSE[t], dump["approx_rows"], fks,
        len(dump["triggers_mentioning"]), len(d["repo"]["django_runtime"]), len(d["repo"]["react"]), RISK.get(t, "Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files")))
MATRIX = "\n".join(rows)

best = ev["summary"]["ks-level1 + rtrim expression unique index"]
lvl1 = ev["summary"]["nondeterministic_ks-level1 (ci+ai)"]
dflt = ev["summary"]["default_deterministic"]

STATUS = """| Workstream | Status | Evidence | Next action / who / authorization |
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
| Final read-only database verification | PASS | See first two rows; 8 user triggers, 111 indexes; no ci_ai/ci_as collations and no citext/unaccent in target. | none |"""

COLL = """### zg_location.city_name collation (Workstream A)
Verified facts: source dump (MariaDB 11.8.9) declares the table with `DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci` and `UNIQUE KEY city_name (city_name)`; the PostgreSQL candidate is `varchar(100)` with the database default collation and `UNIQUE (city_name)`; the app searches with `ILIKE` (case-insensitive, accent-sensitive) in adminapi/operations.py and duplicate detection relies on the unique index.

Executable evidence: `scripts/schema_conversion/collation_eval.py` ran 23 value pairs on a disposable MariaDB 13.0.2 (temp datadir, port 3399, stopped afterwards; the original 11.8.9 server was not available) and on disposable PostgreSQL 18.6 databases (stokit_collation_eval_20261015c). Raw results: docs/STOKIT_CITY_NAME_COLLATION_EVAL.json.
- Source behavior measured (equal AND unique-collision): Kochi/kochi, cafe-acute/cafe, NFC/NFD, trailing space(s), trailing NBSP, sharp s/ss, ae ligature/ae, Istanbul dotted I, fullwidth, ligature fi, ZWJ, Kelvin sign, o-stroke, l-stroke, Malayalam vowel forms, and empty/space are all equal. Different: leading space, trailing tab, inner space, dotless i/i, hyphen, Kochi/Kochin. Equality and unique collision agreed for all 23 pairs.
- PostgreSQL candidates vs source (mismatching cases of 23): deterministic default %d; und-x-icu deterministic %d; nondeterministic ICU und-u-ks-level1 %d (trailing space, two trailing spaces, trailing NBSP, empty vs space); ks-level2 %d; ks-level1 plus unique index on rtrim(city_name, ' ') %d (trailing NBSP only).
- Query behavior: plain equality uses the unique index for all but the rtrim expression index, which is used only when the query repeats the same expression. `ILIKE` fails on nondeterministic collations (FeatureNotSupported), so the search would need `LIKE` (not recorded in the JSON) or normalization. ICU collations ci_ai/ci_as do not exist in the target; creating them is a schema change that was NOT made.
- Assumption vs fact: PAD SPACE behavior was measured on 13.0.2, not 11.8.9. Public MariaDB naming material lists uca1400_ai_ci and uca1400_nopad_ai_ci as separate collations, consistent with the measured padding, but one naming document is internally inconsistent, so the version-to-version claim is an inference.
- Proposed (needs approval): nondeterministic `und-u-ks-level1` collation on the column plus a unique expression index on `rtrim(city_name, ' ')`, with application queries using the same expression; decide NBSP handling and replace `ILIKE`. Trade-offs: nondeterministic collations are slower, cannot use LIKE-prefix index scans, and cannot back some features; the expression index changes how queries must be written.
- Regression tests added: adminapi/tests_city_name_collation.py (7 tests, DB-free): pins the measured source behavior, asserts the DDL candidate declares no collation, and carries one expectedFailure documenting that parity is not met. Status: BLOCKED (parity unproven; not changed).""" % (dflt["mismatches"], 17, lvl1["mismatches"], ev["summary"]["nondeterministic_ks-level2 (ci, accent-sensitive)"]["mismatches"], best["mismatches"])

PROV = """### PHP provenance and excluded-table dependencies (Workstream B)
Verified facts: backup root `C:\\Users\\.MSI\\Downloads\\StokIt_PHP_Backup_20261012\\Host`; 153 PHP files; no `.git`, no manifest/checksum/deploy files (only .htaccess); all file mtimes are within 10 seconds on 2026-10-09 (extraction time). No `.git` at the workspace roots or C:\\Project\\stokit. The `stokit_php` workspace path resolves to an empty location. Provenance of the active deployment: BLOCKED.

CORRECTION to earlier text in these reports: the previous literal-name scan found only 8 referenced tables because the PHP code builds names as `{$qt}_table` with `$qt = 'zg'` (admin/manage/config.php). After resolving that prefix (scripts/read_only_audits/excluded_table_dependency_audit_readonly.py, output docs/STOKIT_EXCLUDED_TABLE_DEPENDENCY_MATRIX.json) 14 of 16 excluded tables have SQL references in the backup; only users1 and zg_target_activity_log have none. Operation labels are keyword-heuristic (nearest SQL keyword before the name); comment-only lines are labeled separately. All hits are under admin/manage/; none are in the backup's api/ files. No excluded table is referenced by Django runtime code, tests aside, or by React. 350 dynamic-name candidate lines exist (interpolated variables); only the `$qt`/`$table_prefix` pattern was resolved, so other dynamically built names are not ruled out. A static backup scan is not proof that any table is unused or used in production.

""" + MATRIX + """

Evidence required to change any classification: authoritative deployed source or access logs showing which admin/manage pages are actually used, plus an owner scope decision. Exclusions were preserved; nothing was created, restored or populated."""

NEW_BLOCKERS = """| ID | Finding | Status |
|---|---|---|
| S04 | zg_location.city_name collation: source behavior measured; best candidate leaves 1 of 23 cases unmatched; strategy needs approval | BLOCKED (was OPEN) |
| S18/S22 | Excluded-table dependencies: 14 of 16 referenced in backup PHP once the $qt prefix is resolved (earlier count of 8 was incomplete); runtime reachability unknown | PARTIAL (matrix complete, runtime BLOCKED) |
| S21 | Active PHP source authority: no VCS/deploy evidence; uniform extraction mtimes | BLOCKED - owner must supply deployed revision |
| S28 | Inventory JSON had a UTF-8 BOM (rejected by strict parsers) and omitted the 12 Django-managed tables; BOM removed, note added | RESOLVED (documentation) |
| S29 | Browser interaction and authenticated flows | BLOCKED - needs approved automation tool and authorized existing account |
| S30 | Disposable artifacts left in place for owner review/authorization to delete: PostgreSQL DBs stokit_collation_eval_20261015 (partial, failed run), ..._20261015b (failed run), ..._20261015c (final); temp dirs under %TEMP%: stokit_mariadb_eval_20261015, stokit_chrome_eval_20261016, stokit_e2e_20261016 | OPEN (housekeeping) |"""

TESTS = """### Execution detail (2026-10-16, local +05:30)
Commands/results: `python manage.py check` (no issues); `makemigrations --check --dry-run` (no changes); `manage.py test --noinput` with DB_NAME=stokit_schema_validation_20261015_2 (93 tests OK, 1 expected failure); `manage.py migrate --check` on target (exit 0, reads django_migrations only); `npm test` 15 pass; `npm run lint` 0/0; `npm run build` OK; collation_eval.py; excluded_table_dependency_audit_readonly.py; final_target_verify_readonly.py (READ ONLY transaction). Servers: Django (127.0.0.1:8000, DB stokit_postgres_dev) and Vite (127.0.0.1:5173) were started for the HTTP/browser checks and stopped afterwards; the dev servers that were listening at the start of this pass are not running now (ports 8000 and 5173 are free) and must be restarted by the owner if wanted. Backend log during checks: 94 lines, 0 5xx, 0 tracebacks.
Confirmed application defects: none found in this pass; no application code changed. Documentation defects corrected: incomplete PHP reference count, inventory JSON BOM/omission. Observation tied to S04: location search uses ILIKE (accent-sensitive) whereas the source collation is accent-insensitive.
Files added: adminapi/tests_city_name_collation.py; scripts/schema_conversion/collation_eval.py; scripts/read_only_audits/excluded_table_dependency_audit_readonly.py; scripts/read_only_audits/final_target_verify_readonly.py; scripts/read_only_audits/update_reports_20261016.py; docs/STOKIT_CITY_NAME_COLLATION_EVAL.json; docs/STOKIT_EXCLUDED_TABLE_DEPENDENCY_MATRIX.json. Files edited: the six docs listed in the task (inventory JSON re-saved without BOM with an added `master_completion_pass_20261016` key; exclusions and approved manifest unchanged). admin_frontend/dist was regenerated by the build. No PHP, Flutter, SQL dump, .env or secret file was modified."""


def append(name, body):
    p = DOCS / name
    text = p.read_text(encoding="utf-8-sig")
    if MARK in text:
        print("skip (already updated):", name)
        return
    p.write_text(text.rstrip() + "\n\n" + MARK + "\n\n" + body.strip() + "\n", encoding="utf-8")
    print("updated:", name)


append("STOKIT_FULL_SCHEMA_AND_APPLICATION_EXECUTION_REPORT.md",
       "Overall: **PARTIAL**. Schema provisioning and regression suites pass; collation parity, PHP provenance, runtime dependency of excluded tables, interactive browser E2E and authenticated CRUD remain BLOCKED/PARTIAL for the external reasons below. Where this section conflicts with the earlier 'Excluded-table PHP backup scan refinement' above, this section is correct.\n\n### Final status matrix\n\n" + STATUS + "\n\n" + COLL + "\n\n" + PROV + "\n\n" + TESTS)
append("STOKIT_COMPLETE_DDL_VALIDATION_REPORT.md", COLL + "\n\nBackend regression: 93 tests OK (1 expected failure) in an isolated database; catalog validation results from the earlier stage are unchanged (1,383 checks, 0 failures). Target re-verified read-only: 43 tables, 20 migration records.")
append("STOKIT_COMPLETE_SCHEMA_BLOCKERS.md", NEW_BLOCKERS + "\n\nSection-by-section detail and the 16-table matrix: see the primary execution report and the inventory.")
append("STOKIT_COMPLETE_POSTGRESQL_SCHEMA_INVENTORY.md", PROV)
append("STOKIT_COMPLETE_IMPLEMENTATION_PLAN.md",
       "Status update: the approved 43-table schema is implemented and verified; the remaining plan items are all external decisions or authorizations. (1) Provenance: owner supplies the deployed PHP revision. (2) Scope: per-table decisions for the 14 referenced excluded tables, informed by the matrix. (3) Collation: approve the ks-level1 + rtrim expression-index strategy or another one, then validate in isolation before any target change. (4) Browser/authenticated testing: approve an automation tool and provide an existing test account.\n\n" + STATUS)

p = DOCS / "STOKIT_COMPLETE_POSTGRESQL_SCHEMA_INVENTORY.json"
inv = json.loads(p.read_text(encoding="utf-8-sig"))
inv["master_completion_pass_20261016"] = {
    "note": "Evidence only; approved schema and exclusions unchanged. Django-managed tables (12) are provisioned by migrations and are not listed in this inventory.",
    "django_managed_tables_not_listed": ["accounts_adminroleassignment", "accounts_checkoutpayload", "accounts_devicetoken", "accounts_passwordresetotp",
                                          "accounts_userdevicesession", "auth_group", "auth_group_permissions", "auth_permission", "auth_user",
                                          "auth_user_groups", "auth_user_user_permissions", "django_content_type"],
    "excluded_table_php_backup_references_after_prefix_resolution": {
        t: {"hits": len(d["php_hits"]), "files": d["php_files"], "operations": ops(d["php_hits"])} for t, d in m["tables"].items()},
    "php_provenance": "BLOCKED - backup only; uniform extraction mtimes; no VCS/deploy evidence",
    "city_name_collation": "BLOCKED - see STOKIT_CITY_NAME_COLLATION_EVAL.json",
}
p.write_text(json.dumps(inv, indent=2, ensure_ascii=False), encoding="utf-8")
print("updated: inventory json (BOM removed)")
