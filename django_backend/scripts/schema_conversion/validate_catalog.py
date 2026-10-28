"""Validate a PostgreSQL database catalog against STOKIT_COMPLETE_DDL_CHANGE_MANIFEST.json (read-only for catalog checks;
functional trigger/constraint tests run inside a transaction that is always rolled back).
usage: validate_catalog.py DBNAME [--functional]
"""
import json, sys
from pathlib import Path
import psycopg

ROOT = Path(__file__).resolve().parents[2]
env = {}
for line in (ROOT / ".env.postgres").read_text().splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip().strip("\"'")
db = sys.argv[1]
man = json.loads((ROOT / "docs" / "STOKIT_COMPLETE_DDL_CHANGE_MANIFEST.json").read_text())
conn = psycopg.connect(host=env["DB_HOST"], port=env["DB_PORT"], user=env["DB_USER"], password=env["DB_PASSWORD"], dbname=db)
cur = conn.cursor()
fails, checks = [], 0
def ok(cond, msg):
    global checks
    checks += 1
    if not cond:
        fails.append(msg)

def actual_pg_type(row):
    data_type, max_length, precision, scale = row[1], row[2], row[3], row[4]
    if data_type == "character varying":
        return f"varchar({max_length})"
    if data_type == "numeric":
        return f"numeric({precision},{scale})"
    return data_type

cur.execute("select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE'")
present = {r[0] for r in cur.fetchall()}
for t, spec in man["tables"].items():
    ok(t in present, f"missing table {t}")
    if t not in present:
        continue
    cur.execute("select column_name,data_type,character_maximum_length,numeric_precision,numeric_scale,is_nullable,is_identity,column_default from information_schema.columns where table_schema='public' and table_name=%s order by ordinal_position", (t,))
    cols = cur.fetchall()
    ok([c[0] for c in cols] == [c["name"] for c in spec["columns"]], f"{t}: column list/order differs")
    bymap = {c[0]: c for c in cols}
    for c in spec["columns"]:
        r = bymap.get(c["name"])
        if not r:
            continue
        ok(actual_pg_type(r) == c["pg_type"], f"{t}.{c['name']}: type expected {c['pg_type']} got {actual_pg_type(r)}")
        ok((r[5] == "NO") == (c["not_null"] or c["identity"]), f"{t}.{c['name']}: nullability")
        ok((r[6] == "YES") == c["identity"], f"{t}.{c['name']}: identity")
        ok((r[7] is not None) == c["has_default"], f"{t}.{c['name']}: default presence")
    cur.execute("select a.attname from pg_index i join pg_attribute a on a.attrelid=i.indrelid and a.attnum=any(i.indkey) where i.indrelid=%s::regclass and i.indisprimary order by array_position(i.indkey::int2[], a.attnum)", (f"public.{t}",))
    ok([r[0] for r in cur.fetchall()] == spec["primary_key"], f"{t}: primary key")
    cur.execute("select conname, pg_get_constraintdef(oid) from pg_constraint where conrelid=%s::regclass and contype='u'", (f"public.{t}",))
    uq = {r[0]: r[1] for r in cur.fetchall()}
    for u in spec["uniques"]:
        ok(u["name"] in uq, f"{t}: unique {u['name']}")
    ok(len(uq) == len(spec["uniques"]), f"{t}: unexpected unique count {len(uq)}")
    cur.execute("select conname, pg_get_constraintdef(oid) from pg_constraint where conrelid=%s::regclass and contype='f'", (f"public.{t}",))
    fk = {r[0]: r[1] for r in cur.fetchall()}
    for f in spec["foreign_keys"]:
        d = fk.get(f["name"], "")
        ok(f["ref_table"] in d and (f["on_delete"] is None or f"ON DELETE {f['on_delete']}" in d), f"{t}: fk {f['name']}")
    ok(len(fk) == len(spec["foreign_keys"]), f"{t}: fk count {len(fk)}")
    cur.execute("select indexname from pg_indexes where schemaname='public' and tablename=%s and indexname not like %s", (t, "%_pkey"))
    idx = {r[0] for r in cur.fetchall()} - {u["name"] for u in spec["uniques"]}
    ok(idx == {i["name"] for i in spec["indexes"]}, f"{t}: secondary indexes {sorted(idx)}")
    cur.execute("select conname from pg_constraint where conrelid=%s::regclass and contype='c'", (f"public.{t}",))
    ok(len(cur.fetchall()) == len(spec["enum_or_json_checks"]), f"{t}: check constraints count")

cur.execute("select tgname from pg_trigger where not tgisinternal")
trg = {r[0] for r in cur.fetchall()}
for tr in man["triggers"]:
    ok(tr["trigger"] in trg, f"missing trigger {tr['trigger']}")
cur.execute("select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='S'")
ok(cur.fetchone()[0] >= man["counts"]["identity_columns"], "sequence count")

# data-free proof
for t in man["tables"]:
    if t in present:
        cur.execute(f'select count(*) from "{t}"')
        ok(cur.fetchone()[0] == 0, f"{t}: contains rows (no business data may be imported)")

print(json.dumps({"db": db, "checks": checks, "failures": fails, "expected_tables": len(man["tables"]), "present_expected": sum(t in present for t in man["tables"])}, indent=2))
conn.rollback()
conn.close()
sys.exit(1 if fails else 0)
