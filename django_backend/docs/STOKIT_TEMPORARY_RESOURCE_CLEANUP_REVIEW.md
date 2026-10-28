# STOKIT Temporary Resource Cleanup Review

Date: 2026-10-16 | Scope: read-only review | Status: **NOTHING DELETED, STOPPED OR CHANGED**

Labels: **OBSERVED TODAY** = checked read-only in this session (file system or port listing only); **PREVIOUSLY REPORTED** = taken from earlier reports and not freshly verified (no database connection was made for this document); **PROPOSED** = not executed.

Location note: the task named `docs/`; the file sits beside its sibling reports in `django_backend/docs/`.

## 1. Summary of risks

1. A disposable MariaDB 13.0.2 instance (port 3399, PID 4572) is **running** and holds an open handle on its data directory. Earlier reports said it had been stopped; that was wrong. Deleting the directory while it runs is unsafe.
2. Eight PostgreSQL databases with StokIt-style names were reported. Several hold evidence that later reports cite; dropping them too early destroys that evidence.
3. Two further databases, `wholesale_db` and `test_wholesale_db`, are **not assumed to belong to StokIt** and must not be touched.
4. Temporary folders hold the only copies of browser and server logs that support the "page-load only" browser evidence and the "0 5xx" statement.
5. The only PostgreSQL backups of the target are tiny, predate the schema implementation, and cover a 3-table baseline (see section 6).
6. Dev servers on ports 8000 and 5173 are listening now (OBSERVED TODAY), although the 2026-10-16 report said they had been stopped. They were not started by this task.

## 2. PostgreSQL databases (PREVIOUSLY REPORTED — existence and contents not re-verified)

| Database | Reported purpose | Evidence it supports | Belongs to StokIt? | Proposed disposition |
|---|---|---|---|---|
| `stokit_collation_eval_20261015` | Collation experiment (first run) | Superseded by `...c` | Yes (name, script guard `stokit_collation_eval_*`) | Candidate for drop after approval |
| `stokit_collation_eval_20261015b` | Collation experiment | Superseded | Yes | Candidate for drop |
| `stokit_collation_eval_20261015c` | Collation experiment that produced `STOKIT_CITY_NAME_COLLATION_EVAL.json` | Raw results are saved in the JSON | Yes | Keep until the owner approves the collation review, then drop |
| `stokit_backup_restore_verify_20261015` | Restore of the pre-full-schema backup | `STOKIT_BACKUP_RESTORE_GATE_REPORT.md` and the baseline comparison | Yes | Keep until backup/restore coverage is accepted |
| `stokit_phase2_restore_verify_20261015_210457` | Restore of the phase-2 backup | Phase-2 evidence | Yes | Keep until the same acceptance; then drop |
| `stokit_schema_validate_20261015` | Early schema validation run | Superseded | Yes | Candidate for drop |
| `stokit_schema_validation_20261015` | Schema validation run | Superseded | Yes | Candidate for drop |
| `stokit_schema_validation_20261015_2` | Validation database that holds the 43-table validation (1,383 catalog checks) and was used by the backend test runs (93 tests) | Validation and test evidence | Yes | **Keep** until the backend suite has been re-run against a disposable database that replaces it |
| `wholesale_db` | Unknown | None | **Not assumed** | **DO NOT TOUCH** |
| `test_wholesale_db` | Unknown (name suggests a Django test database for `wholesale_db`) | None | **Not assumed** | **DO NOT TOUCH** |

Notes:
- Dropping any database requires no active connections and the correct owner; each name must be checked against `pg_database` before any command is built.
- The target `stokit_postgres_dev` is **not** a cleanup candidate.
- Django's test runner creates `test_<name>` databases and removes them itself; any leftover `test_*` database that is not `test_wholesale_db` should be listed during a future read-only check before any decision.

## 3. Temporary directories

| Path | Reported content | OBSERVED TODAY | Notes |
|---|---|---|---|
| `%TEMP%\stokit_mariadb_eval_20261015` | Disposable MariaDB data directory (`data\`) | Exists; 215 files, 162,057,169 bytes; `data` last written 2026-10-16 09:12:15 | In use by the running process in section 4 |
| `%TEMP%\stokit_chrome_eval_20261016` | Headless Chrome page-load evidence (`p_`, `p_login`, `p_orders`, `p_admin_nonexistent`, `p2`, DOM dumps, `net_*.json`, `err_*.txt`) | Exists; 849 files, 30,509,526 bytes; last written 2026-10-16 09:15:50 | The `p_*` and `p2` folders are probably Chrome profile data (INFERRED; contents not inspected); `err_*.txt` mostly 0 bytes, `err_root2.txt` 318 bytes |
| `%TEMP%\stokit_e2e_20261016` | Django/Vite server logs (`dj.out`, `dj2.err`, `dj2.out`, …) and DOM dumps for `/`, `/login`, `/no-such-page` | Exists; 913 files, 90,260,707 bytes; last written 2026-10-16 09:37:15 | Holds the logs behind "backend log 0 5xx" |
| `%TEMP%\stokit-sqlmigrate-review` | **Unreported before this review.** 19 files: `sqlmigrate` output for accounts, auth and contenttypes migrations (for example `accounts-0001_initial.sql`) | Exists; 19 files, 21,638 bytes; last written 2026-10-15 13:39:54 | Review evidence for the migration SQL; very small |

Also present, not covered by the task but worth recording: `%TEMP%\stokit_flutter` (a Flutter copy; last written 2026-10-09 10:40:10; workspace alias `flutter`) — **not a cleanup candidate here** because a workspace alias points to it.

## 4. MariaDB evaluation instance on port 3399

- OBSERVED TODAY: a listener on `127.0.0.1:3399` is owned by PID **4572**, process `mariadbd`, start time **2026-10-16 09:10:59**.
- The data directory is `%TEMP%\stokit_mariadb_eval_20261015\data` (PREVIOUSLY REPORTED; the process command line was not read today).
- Discrepancy: the 2026-10-16 master report says the instance was stopped afterwards; the collation review says it is still running; today's listener check agrees with the latter. The start time (09:10:59) suggests it was started or restarted this morning (INFERRED).
- Dependency: the process holds the data directory open. Removing that directory first would corrupt a running server and can leave locked files; stopping the process first is mandatory, and the stop must be graceful.
- The separate `MariaDB` Windows service on port 3306 (PID 5460 today, `C:\Program Files\MariaDB 13.0`) is a different instance and **must not be touched**.
- Nothing was stopped, restarted or deleted.

## 5. What must be retained

Keep these regardless of cleanup (all under `C:\Users\.MSI\Downloads\StokIt Backend\django_backend` unless stated):

| Item | Why |
|---|---|
| `docs/` (all reports, `STOKIT_CITY_NAME_COLLATION_EVAL.json`, `STOKIT_EXCLUDED_TABLE_DEPENDENCY_MATRIX.json`, `STOKIT_COMPLETE_DDL_CANDIDATE.sql`, validation reports) | Primary evidence and approved DDL |
| `scripts/read_only_audits/`, `scripts/schema_conversion/collation_eval.py` | Reproducibility of measurements |
| `adminapi/tests_city_name_collation.py` | Regression test that pins source behaviour |
| `backups/stokit_postgres_dev_pre_full_schema_20261015.dump` (5,117 bytes, 2026-10-15 22:32:48) and `backups/stokit_postgres_dev_pre_phase2_20261015_210457.dump` (5,117 bytes, 2026-10-15 21:04:58) | Only target backups (OBSERVED TODAY) |
| `C:\Users\.MSI\Downloads\stokit_sql_work\` (`u144866523_stokitDB.sql` 134 MB, `.sanitized.sql`, `schema_extract\`) and `C:\Users\.MSI\Downloads\StokIt Backend.zip` | Source dump and PHP source of record. Not temp; contain sensitive data; no cleanup proposed |
| From `%TEMP%\stokit_e2e_20261016`: `dj.out`, `dj2.out`, `dj2.err` (and any other `dj*` log files present), `dom_*.html` | Server logs and DOM evidence for the browser statement |
| From `%TEMP%\stokit_chrome_eval_20261016`: `net_*.json`, `err_*.txt`, `dom_root.html` | Console and network evidence. Chrome profile folders (`p_*`, `p2`) are not needed. Network JSON may contain request URLs; review for secrets before archiving |
| `%TEMP%\stokit-sqlmigrate-review\*.sql` (19 files, ~21 KB) | Migration SQL review evidence |
| PostgreSQL databases marked "Keep" in section 2 | Evidence still cited |

Proposed retention method: copy the listed evidence files into a dated folder under `django_backend/docs/evidence_20261016/` (new folder, **NOT CREATED**) and verify the copies before any removal.

## 6. Backup freshness and restore coverage (related risk)

- Both existing backups are 5,117 bytes and were taken **before** the schema implementation (21:04:58 and 22:32:48 on 2026-10-15). They describe the 3-table baseline (`admins`, `admin_cart_discount_settings`, `django_migrations`; PREVIOUSLY REPORTED).
- No backup of the current 43-table state exists (OBSERVED: no such file in `backups/`). Restore coverage is limited to the baseline restore verifications in section 2.
- Cleanup should therefore not drop the restore-verify databases until the owner has decided whether to take a fresh post-implementation backup and restore it. A backup is a database read, but it requires approval under this task's rules.

## 7. Proposed cleanup commands

> **ALL COMMANDS BELOW ARE NOT EXECUTED — REQUIRE SEPARATE APPROVAL.** Run each guard first and stop if it does not return the expected result. Substitute the real connection settings; never paste passwords into shell history or logs.

### 7.1 Read-only guards (run before anything else)

```
-- PostgreSQL: confirm existence, owner, size and connections of each candidate
SELECT datname, pg_get_userbyid(datdba) AS owner, pg_database_size(datname) AS bytes
FROM pg_database WHERE datname LIKE 'stokit\_%' ESCAPE '\' ORDER BY datname;
SELECT datname, count(*) FROM pg_stat_activity WHERE datname LIKE 'stokit\_%' ESCAPE '\' GROUP BY datname;
```
```
# PowerShell: confirm what owns port 3399 and which data directory it uses
Get-NetTCPConnection -LocalPort 3399 -State Listen | Select LocalPort,OwningProcess
Get-CimInstance Win32_Process -Filter "ProcessId=4572" | Select ProcessId,Name,CommandLine
```
Proceed only if the command line shows `--datadir` equal to `%TEMP%\stokit_mariadb_eval_20261015\data` and port 3399.

### 7.2 Step A — archive evidence (safe copy, creates a new folder)
```
$dest = "C:\Users\.MSI\Downloads\StokIt Backend\django_backend\docs\evidence_20261016"
New-Item -ItemType Directory -Path $dest
Copy-Item "$env:TEMP\stokit-sqlmigrate-review\*.sql" $dest
Copy-Item "$env:TEMP\stokit_e2e_20261016\dj*.out","$env:TEMP\stokit_e2e_20261016\dj*.err","$env:TEMP\stokit_e2e_20261016\dom_*.html" $dest
Copy-Item "$env:TEMP\stokit_chrome_eval_20261016\err_*.txt","$env:TEMP\stokit_chrome_eval_20261016\dom_root.html" $dest
```
**NOT EXECUTED — REQUIRES SEPARATE APPROVAL**

### 7.3 Step B — stop the evaluation MariaDB (graceful)
```
mysqladmin --protocol=tcp -h127.0.0.1 -P3399 -uroot shutdown
```
The credentials of the evaluation instance are not recorded in the evidence; supply them securely. Do not use `Stop-Process` unless the graceful shutdown fails and the owner agrees. Afterwards confirm that nothing listens on 3399. **NOT EXECUTED — REQUIRES SEPARATE APPROVAL**

### 7.4 Step C — remove temporary directories (only after Steps A and B are verified)
```
$t = [IO.Path]::GetFullPath($env:TEMP)
foreach ($n in 'stokit_mariadb_eval_20261015','stokit_chrome_eval_20261016','stokit_e2e_20261016','stokit-sqlmigrate-review') {
  $p = Join-Path $t $n
  if ((Test-Path -LiteralPath $p) -and ([IO.Path]::GetFullPath($p).StartsWith($t))) { Remove-Item -LiteralPath $p -Recurse -Force }
}
```
**NOT EXECUTED — REQUIRES SEPARATE APPROVAL**

### 7.5 Step D — drop superseded PostgreSQL databases (candidates only)
```
DROP DATABASE "stokit_collation_eval_20261015";
DROP DATABASE "stokit_collation_eval_20261015b";
DROP DATABASE "stokit_schema_validate_20261015";
DROP DATABASE "stokit_schema_validation_20261015";
```
Later, after the owner accepts the related evidence (section 2), a second approval may cover:
```
DROP DATABASE "stokit_collation_eval_20261015c";
DROP DATABASE "stokit_backup_restore_verify_20261015";
DROP DATABASE "stokit_phase2_restore_verify_20261015_210457";
DROP DATABASE "stokit_schema_validation_20261015_2";
```
**NOT EXECUTED — REQUIRES SEPARATE APPROVAL.** No command is proposed for `wholesale_db`, `test_wholesale_db`, `stokit_postgres_dev`, or the MariaDB service on port 3306.

## 8. Owner decisions

- [ ] Approve archiving the evidence files (Step A).
- [ ] Approve a graceful stop of the 3399 instance and supply how to authenticate (Step B).
- [ ] Approve deleting the four temp directories (Step C).
- [ ] Approve dropping the four superseded databases; decide when the others may go (Step D).
- [ ] Confirm whether `wholesale_db` and `test_wholesale_db` belong to another project (they stay untouched either way).
- [ ] Decide whether to take a fresh backup of the 43-table target and a restore test.
- [ ] Confirm who started the dev servers now listening on 8000 and 5173, and whether they should keep running.


## 9. Source-tree safe cache cleanup — 2026-10-16

Phase 1 source audit was completed before cleanup. Removed only 10 generated Python `__pycache__` directories containing 74 `.pyc` files under `accounts`, `adminapi`, `config`, `legacy_api`, and `legacydb`, including their migrations/management subfolders. These are interpreter caches regenerated from source and are not user data or source. Exact removed paths: `accounts/__pycache__`, `accounts/management/__pycache__`, `accounts/management/commands/__pycache__`, `accounts/migrations/__pycache__`, `adminapi/__pycache__`, `adminapi/migrations/__pycache__`, `config/__pycache__`, `legacy_api/__pycache__`, `legacydb/__pycache__`, `legacydb/migrations/__pycache__`.

Preserved `.venv`, `node_modules`, `.vite` caches, `dist`, source, migrations, environment files, uploads/media, SQL dumps, backup dumps, docs, audit scripts, PHP reference, Flutter source and all databases. No external temporary directories or services were touched. The Python test/check run may regenerate bytecode caches.

## 10. Final post-test cache pass — 2026-10-16

The Django test/check commands regenerated source-tree bytecode caches, as expected. After all tests were complete, a second narrowly scoped cleanup removed 9 `__pycache__` directories containing 63 `.pyc` files under the same Django source apps, excluding `.venv`. A fresh post-cleanup scan reported **0 remaining source-tree `__pycache__` directories outside `.venv`**. This is the final cleanup pass; do not run Python tests again if a cache-free tree is desired, because Python will regenerate caches. No other files or databases were touched.


## 11. Final cleanup after local smoke verification — 2026-10-16

After rerunning local frontend/backend checks, the final cleanup removed 9 generated `__pycache__` directories containing 63 `.pyc` files outside `.venv`. Final scan: 0 source-tree cache directories and 0 `.pyc` files outside `.venv`. No source, data, configuration, upload, migration, backup, SQL, PHP, Flutter or database files were changed. Do not run Python commands again if keeping the cache-free tree matters; they may regenerate bytecode.
