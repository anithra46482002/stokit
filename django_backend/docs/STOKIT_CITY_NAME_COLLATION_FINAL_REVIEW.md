# STOKIT zg_location.city_name — Collation Final Review

Date: 2026-10-16 | Scope: read-only investigation | Status: **BLOCKED — owner decision required**

Labels: VERIFIED = measured in this session; HISTORICAL = taken from earlier reports/JSON; INFERENCE = reasoned, not measured; PROPOSED; NOT RUN; NOT EXECUTED.

No schema, application code, collation object, index or data was changed. All SQL below was SELECT-only (PostgreSQL sessions opened `read_only=True`; MariaDB statements were literal-only SELECTs).

## 1. Inputs inspected

| Item | Result |
|---|---|
| `adminapi/tests_city_name_collation.py` | VERIFIED: 7 DB-free tests. Re-run today: `Ran 7 tests ... OK (expected failures=1)`. |
| `scripts/schema_conversion/collation_eval.py` | VERIFIED read. 23 pairs; MariaDB on 127.0.0.1:3399 and disposable PostgreSQL DBs only; refuses non-`stokit_collation_eval_*` names. |
| `docs/STOKIT_CITY_NAME_COLLATION_EVAL.json` | VERIFIED read. MariaDB `13.0.2-MariaDB`, TABLE_COLLATION `utf8mb4_uca1400_ai_ci`; PostgreSQL 18.6; target DB locale provider `c`, collate `English_India.1252`. |
| Source dump version | HISTORICAL: MariaDB **11.8.9** (not available locally). |

## 2. The exact mismatch

Input pair (case label `trailing NBSP`): `a = "Kochi"` (bytes `4b6f636869`) and `b = "Kochi\u00a0"` (bytes `4b6f636869c2a0`).

| System | `a = b` | Unique index accepts both? |
|---|---|---|
| MariaDB 13.0.2, `utf8mb4_uca1400_ai_ci` | TRUE | No — second insert rejected |
| PostgreSQL ICU `und-u-ks-level1` (nondeterministic) + unique index on `rtrim(city_name, ' ')` | FALSE | Yes — both accepted |
| PostgreSQL default deterministic collation | FALSE | Yes |

This is the only residual mismatch of the best evaluated strategy (VERIFIED from JSON: `ks-level1 + rtrim expression unique index`, 1 mismatch of 23).

### Why: ordinary space vs NBSP

- VERIFIED (MariaDB 13.0.2): `WEIGHT_STRING` of U+0020 and U+00A0 under `utf8mb4_uca1400_ai_ci` are both `0209`. The collation is PAD SPACE, so trailing characters whose weight equals space are ignored in comparison. `utf8mb4_uca1400_nopad_ai_ci` returns FALSE for both `Kochi`/`Kochi ` and `Kochi`/`Kochi\u00a0`.
- VERIFIED (PostgreSQL 18.6, ICU): `' ' = NBSP` under ks-level1 is TRUE (they are level-1 equal), but ICU does **not** pad-trim, so `Kochi ` ≠ `Kochi` and `Kochi\u00a0` ≠ `Kochi`. `rtrim(x, ' ')` removes only U+0020 and leaves the NBSP in place, so the expression index still sees `Kochi\u00a0`.
- VERIFIED: `rtrim(x, ' ' || chr(160))` makes `Kochi` = `Kochi\u00a0` TRUE.

### The mismatch is a class, not one character (new finding)

Trailing-character equality to `Kochi` (VERIFIED, MariaDB 13.0.2 live vs PostgreSQL ICU in the disposable eval DB, read-only):

| Trailing char | MariaDB equal | PG ks-level1 raw | PG + rtrim(SP) | PG + rtrim(SP,NBSP) |
|---|---|---|---|---|
| U+0020 | TRUE | FALSE | TRUE | TRUE |
| U+00A0 NBSP | TRUE | FALSE | FALSE | TRUE |
| U+1680, U+2000–U+200A, U+202F, U+205F, U+3000 | TRUE | FALSE | FALSE | FALSE |
| U+200B ZWSP, U+FEFF, U+00AD | TRUE | TRUE (ignorable) | TRUE | TRUE |
| TAB, LF, U+0085, U+2028 | FALSE | FALSE | FALSE | FALSE |

Of the 17 Unicode `Zs` space separators tested, `rtrim(' ')` handles only U+0020 (1 of 17); adding NBSP handles 2 of 17; the other 15 still mismatch. VERIFIED: `rtrim(x, <all 17 Zs>)` yields TRUE for every Zs trailing character, TRUE for mixed trailing `Zs`, TRUE for NBSP-only vs empty (matches MariaDB's empty-vs-space), and FALSE for leading NBSP and trailing TAB (matches MariaDB).

Other VERIFIED MariaDB 13.0.2 facts: interior SP = interior NBSP (TRUE); leading NBSP ≠ none (FALSE); NBSP-only = empty string (TRUE).

## 3. Effect on equality, lookup, uniqueness (with current candidate and best strategy)

- Equality: PostgreSQL default is deterministic → 17 of 23 cases mismatch (HISTORICAL JSON; VERIFIED again today for case, accent, trailing space, NBSP).
- Lookup (`WHERE city_name = %s`): with a plain column collation a lookup for `Kochi` will not find `kochi`/`Kochi `. With an expression index it only uses the index when the query repeats the same `rtrim(...) COLLATE ...` expression (HISTORICAL JSON: `equality_plan_uses_index`).
- Uniqueness: duplicates that MariaDB would reject (`Kochi` / `kochi` / `Kochi `/ `Kochi\u00a0`) are accepted by the candidate schema → duplicate cities and ambiguous `users.city` joins.
- Search: `ILIKE` on a nondeterministic collation fails: VERIFIED `FeatureNotSupported: nondeterministic collations are not supported for ILIKE`. VERIFIED on 18.6: `LIKE` **does** work with the nondeterministic ks-level1 collation (`'Kochi' LIKE 'ko%'` TRUE; `'Café' LIKE 'cafe%'` TRUE). The JSON did not record LIKE results for PostgreSQL (gap in evidence). Current code (`adminapi/operations.py`, `LocationAdminView.get`) uses `city_name ILIKE %s`, so it would raise on that column. Today (default collation) ILIKE works but is accent-sensitive, unlike the source.
- Python side: VERIFIED `str.strip()` removes NBSP, TAB and the other Unicode whitespace (not ZWSP). The admin API (`post`/`put` in `LocationAdminView`) already strips input, so NBSP-trailing values cannot arrive through the Django admin API. They could arrive only through direct SQL or another writer. PHP `admin/manage/locations.php` was the only PHP writer found; the Flutter-facing `api/*.php` files do not write `zg_location`.
- Related columns: `users.city`, `zg_warehouse.place` and `zg_checkout.city` are joined/compared by string equality (`legacy_api/views_catalog.py`, delete guard in `LocationAdminView.delete`). Their source collations were **not verified** in this session; if they were `ai_ci` in MariaDB, `city_name` parity alone does not restore source lookup behavior. INFERENCE / NOT VERIFIED.

## 4. MariaDB 11.8.9 availability

VERIFIED: only `C:\Program Files\MariaDB 13.0` (13.0.2.0) is installed; no 11.8.x binary found by searching `C:\` to depth 3. Service `MariaDB` (port 3306, `C:\Program Files\MariaDB 13.0\data`) is running and was **not** touched. The disposable evaluation instance (pid 4572, port 3399, datadir `%TEMP%\stokit_mariadb_eval_20261015\data`) is **still running** — earlier reports said it was stopped (discrepancy; see cleanup review). Nothing was installed or downloaded.

**All MariaDB results are for 13.0.2. They are not verified for 11.8.9.** The NBSP/pad behavior on 11.8.9 is INFERENCE.

## 5. Candidate policies

| # | Policy | Parity (measured) | Cost / risk |
|---|---|---|---|
| A | Keep default deterministic collation + unique constraint (current candidate) | 17/23 mismatches | Simplest; duplicate cities by case/accent/space; ILIKE works. |
| B | ICU `und-u-ks-level1` nondeterministic column collation + unique index on `rtrim(city_name, ' ')` (the evaluated "best") | 1/23 (NBSP); 16 other Zs trailing chars also mismatch (new) | Needs `CREATE COLLATION`; `ILIKE` fails (use `LIKE`); queries must repeat expression to use index; slower; no prefix index scans. |
| B2 | B but `rtrim(city_name, <17 Zs chars>)` in the expression index | 0 mismatches on all measured trailing cases (VERIFIED equality; index collision INFERRED from equality) | Same as B; longer expression, must be repeated everywhere. |
| C | Deterministic column + generated/normalized key column (`city_key`: trimmed Zs, NFKC/casefold or ICU sort-key) with UNIQUE on it | Not measured | Adds a column to an existing table (changes column count, not table count); parity for ligature/Kelvin/etc. depends on normalization, not measured. |
| D | Application-level normalization only (already `strip()`), accept DB-level deviation | Mismatches remain at DB level | No schema change; relies on Django being the sole writer. |

## 6. Recommendation (PROPOSED — not applied)

1. Adopt **B2** if source-faithful case/accent/pad-space semantics are required: nondeterministic `und-u-ks-level1` collation on `zg_location.city_name`, unique expression index on `rtrim(city_name, <Zs set>) COLLATE <that collation>`, and a single helper (query + DB constraint name) so every lookup/uniqueness check reuses the identical expression.
2. Replace `ILIKE` in `LocationAdminView.get` with `LIKE` on the collated column (VERIFIED to work on 18.6) — a behavioral policy: search becomes case- and accent-insensitive, matching the source collation.
3. Keep the application `strip()`; document that it is stricter than the source (also strips leading space/TAB, which the source treats as distinct).
4. If the owner prefers no custom collation and accepts deviations, choose A or D and delete the `expectedFailure` by changing the test to assert the documented deviation. That would be an explicit parity waiver.

Trade-off summary: B2 gives measured parity at the cost of a custom collation object, slower matching and expression-bound queries; A/D keep the schema as-is but duplicates differing only by case/accent/space become possible.

## 7. Regression-test matrix (PROPOSED — NOT RUN; DB-backed tests need an isolated database)

| Category | Pair (a, b) | Source | Expected under B2 |
|---|---|---|---|
| Case | Kochi / kochi | equal | equal; unique conflict |
| Accent | café / cafe | equal | equal; conflict |
| Unicode normalization | café / cafe + U+0301 | equal | equal |
| Trailing SP (1, 2) | Kochi / `Kochi ` | equal | equal |
| Trailing NBSP | Kochi / `Kochi\u00a0` | equal | equal (fails today under B) |
| Trailing other Zs | Kochi / Kochi + U+2003, U+3000, U+202F | equal | equal |
| Mixed trailing | Kochi / `Kochi \u00a0\u2003` | equal | equal |
| Leading SP / NBSP | Kochi / ` Kochi`, `\u00a0Kochi` | distinct | distinct |
| Trailing TAB/LF | Kochi / `Kochi\t` | distinct | distinct |
| Interior SP vs NBSP | `Ko chi` / `Ko\u00a0chi` | equal | equal |
| Inner space | `Ko chi` / Kochi | distinct | distinct |
| Whitespace-only vs empty | `\u00a0` / `` | equal | equal (API still rejects empty) |
| Compat chars | ß/ss, æ/ae, İ/i, fullwidth K, ﬁ/fi, Kelvin, ø/o, ł/l | equal | equal |
| Distinct | ı / i, Kochi-City / KochiCity, Kochi / Kochin | distinct | distinct |
| Malayalam | U+0D15 U+0D4A / U+0D15 U+0D46 U+0D3E | equal | equal |
| Ignorables | Kochi / Kochi+U+200B | equal | equal |
| Uniqueness | insert a then b for each equal pair | 2nd rejected | `UniqueViolation` → API 400 "city may already exist" |
| Update uniqueness | rename row to a value equal to another row | rejected | rejected, original unchanged |
| Lookup | `WHERE city_name = %s` returns same row for each equal variant | — | one row |
| Search | `LIKE 'ko%'`, `'cafe%'` (not ILIKE) | accent/case-insens. | matches |
| Delete guard | delete location while `users.city` equals a case/space variant | counts via source collation | depends on `users.city` collation — **decision** |
| API | POST/PUT with NBSP input | — | stripped by `strip()` before DB |

## 8. Remaining uncertainty

- MariaDB **11.8.9** behavior (only 13.0.2 measured).
- PostgreSQL LIKE results for each candidate were not stored in the JSON (only spot-checked today).
- Unique-index collision for B2 is inferred from equality; not inserted (no writes were permitted).
- Source collation of `users.city`, `zg_warehouse.place`, `zg_checkout.city`.
- Full UCA1400 trailing-space-class beyond the 17 `Zs` plus ignorables tested (e.g. other format characters).

## 9. Owner decisions required before any change

1. Choose policy A / B / B2 / C / D (or waive parity).
2. Approve (or reject) a custom ICU collation in the target database.
3. Approve switching location search from `ILIKE` to `LIKE` with the new semantics.
4. Decide handling of `users.city`/`zg_warehouse.place` equality.
5. Approve supplying/using MariaDB 11.8.9 (needs install or an existing instance — requires approval) for final parity confirmation.

NOT EXECUTED: `CREATE COLLATION`, `CREATE UNIQUE INDEX`, any `ALTER TABLE`, any application change.
.

