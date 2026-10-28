"""Convert the reviewed MySQL/MariaDB legacy DDL (schema_extract) into PostgreSQL DDL.

Offline only: reads SQL text files, writes the candidate SQL + manifest. Never connects to any database.
Scope: the 29 active tables from STOKIT_COMPLETE_POSTGRESQL_SCHEMA_INVENTORY.json minus `admins`
(admins already exists in the target and is preserved untouched).
"""
import json, re, sys
from pathlib import Path

SRC = Path(r"C:\Users\.MSI\Downloads\stokit_sql_work\schema_extract")
DOCS = Path(__file__).resolve().parents[2] / "docs"
inv = json.loads((DOCS / "STOKIT_COMPLETE_POSTGRESQL_SCHEMA_INVENTORY.json").read_text(encoding="utf-8-sig"))
ACTIVE = [t["name"] for t in inv["tables"] if t["classification"] == "PROPOSED_PENDING_EVIDENCE"]
PRESERVED = {"admins"}
TO_CREATE = [t for t in ACTIVE if t not in PRESERVED]

create_sql = (SRC / "create_tables.sql").read_text(encoding="utf-8-sig")
alter_sql = (SRC / "alters.sql").read_text(encoding="utf-8-sig")

q = lambda s: '"' + s.replace('"', '""') + '"'
tables = {}
for m in re.finditer(r"CREATE TABLE `(\w+)` \((.*?)\n\) ENGINE=[^\n]*?(?:COMMENT='((?:[^']|'')*)')?;", create_sql, re.S):
    name, body, tcomment = m.group(1), m.group(2), m.group(3)
    cols = []
    for line in body.split("\n"):
        line = line.rstrip().rstrip(",")
        if not line.strip():
            continue
        cm = re.match(r"\s+`(\w+)`\s+(\w+)(?:\(([^)]*)\))?(.*)$", line)
        if not cm:
            raise SystemExit(f"unparsed line in {name}: {line!r}")
        cname, typ, targ, rest = cm.groups()
        comment = None
        c = re.search(r"COMMENT '((?:[^']|'')*)'", rest)
        if c:
            comment = c.group(1).replace("''", "'"); rest = rest.replace(c.group(0), "")
        chk = re.search(r"CHECK \((.*)\)\s*$", rest)
        if chk:
            rest = rest.replace(chk.group(0), "")
        rest = re.sub(r"CHARACTER SET \w+|COLLATE \w+", "", rest)
        on_update = "ON UPDATE current_timestamp()" in rest
        rest = rest.replace("ON UPDATE current_timestamp()", "")
        dm = re.search(r"DEFAULT (NULL|'(?:[^']|'')*'|current_timestamp\(\)|-?[0-9.]+)", rest)
        default = dm.group(1) if dm else None
        notnull = "NOT NULL" in rest
        cols.append(dict(name=cname, typ=typ.lower(), targ=targ, notnull=notnull, default=default,
                         on_update=on_update, comment=comment, check=chk.group(1) if chk else None, auto=False))
    tables[name] = dict(cols=cols, comment=tcomment.replace("''", "'") if tcomment else None,
                        pk=None, uniques=[], indexes=[], fks=[])

for m in re.finditer(r"ALTER TABLE `(\w+)`\n(.*?);\n", alter_sql, re.S):
    t, body = m.group(1), m.group(2)
    for part in re.split(r",\n", body):
        part = part.strip()
        if part.startswith("ADD PRIMARY KEY"):
            tables[t]["pk"] = re.findall(r"`(\w+)`", part)
        elif part.startswith("ADD UNIQUE KEY"):
            n, cols = re.match(r"ADD UNIQUE KEY `(\w+)` \((.*)\)", part).groups()
            tables[t]["uniques"].append((n, re.findall(r"`(\w+)`", cols)))
        elif part.startswith("ADD KEY"):
            n, cols = re.match(r"ADD KEY `(\w+)` \((.*)\)", part).groups()
            spec = []
            for cc in cols.split(","):
                mm = re.match(r"`(\w+)`(?:\((\d+)\))?", cc.strip())
                spec.append((mm.group(1), int(mm.group(2)) if mm.group(2) else None))
            tables[t]["indexes"].append((n, spec))
        elif part.startswith("ADD CONSTRAINT"):
            mm = re.match(r"ADD CONSTRAINT `(\w+)` FOREIGN KEY \(`(\w+)`\) REFERENCES `(\w+)` \(`(\w+)`\)(?: ON DELETE (CASCADE|SET NULL|RESTRICT|NO ACTION))?", part)
            tables[t]["fks"].append(dict(name=mm.group(1), col=mm.group(2), ref_table=mm.group(3), ref_col=mm.group(4), on_delete=mm.group(5)))
        elif part.startswith("MODIFY"):
            cn = re.match(r"MODIFY `(\w+)`", part).group(1)
            assert "AUTO_INCREMENT" in part
            for c in tables[t]["cols"]:
                if c["name"] == cn:
                    c["auto"] = True
        else:
            raise SystemExit(f"unhandled ALTER part for {t}: {part!r}")

def pg_type(c):
    t, a = c["typ"], c["targ"]
    if t == "int" or t == "integer":
        return "integer"
    if t == "tinyint" and a == "1":
        return "boolean"
    if t == "varchar":
        return f"varchar({a})"
    if t in ("text", "longtext"):
        return "text"
    if t == "decimal":
        return f"numeric({a})"
    if t == "date":
        return "date"
    if t in ("timestamp", "datetime"):
        return "timestamp without time zone"
    if t == "enum":
        vals = re.findall(r"'((?:[^']|'')*)'", a)
        return f"varchar({max(len(v) for v in vals)})"
    raise SystemExit(f"unmapped type {t}({a}) col {c['name']}")

def pg_default(c):
    d = c["default"]
    if d is None or d.upper() == "NULL":
        return None
    if d == "current_timestamp()":
        return "CURRENT_TIMESTAMP"
    if c["typ"] == "tinyint" and c["targ"] == "1":
        return {"0": "false", "1": "true"}[d]
    return d

out, manifest = [], {"scope": {"active_tables": ACTIVE, "preserved": sorted(PRESERVED), "to_create": TO_CREATE}, "tables": {}}
out.append("-- STOKIT complete legacy business schema, PostgreSQL candidate (generated by scripts/schema_conversion/convert_mysql_to_pg.py)")
out.append("-- Review/validate only. Creates ONLY missing tables; contains no DROP/TRUNCATE/DELETE/INSERT and imports no data.")
out.append("-- Excludes: admins (preserved), Django-managed tables (applied through Django migrations), the 16 excluded tables.\nBEGIN;\n")
for t in TO_CREATE:
    T = tables[t]
    lines, enum_checks = [], []
    for c in T["cols"]:
        s = f"    {q(c['name'])} {pg_type(c)}"
        if c["auto"]:
            s += " GENERATED BY DEFAULT AS IDENTITY"
        if c["notnull"]:
            s += " NOT NULL"
        d = pg_default(c)
        if d is not None and not c["auto"]:
            s += f" DEFAULT {d}"
        if c["typ"] == "enum":
            vals = re.findall(r"'((?:[^']|'')*)'", c["targ"])
            enum_checks.append(f"    CONSTRAINT {q(f'ck_{t}_{c['name']}_enum')} CHECK ({q(c['name'])} IS NULL OR {q(c['name'])} IN ({', '.join(chr(39)+v+chr(39) for v in vals)}))")
        if c["check"] and "json_valid" in c["check"]:
            enum_checks.append(f"    CONSTRAINT {q(f'ck_{t}_{c['name']}_json')} CHECK ({q(c['name'])} IS NULL OR pg_input_is_valid({q(c['name'])}, 'json'))")
        lines.append(s)
    assert T["pk"], t
    lines.append(f"    CONSTRAINT {q(t+'_pkey')} PRIMARY KEY ({', '.join(q(x) for x in T['pk'])})")
    for n, cols in T["uniques"]:
        lines.append(f"    CONSTRAINT {q('uq_'+t+'_'+n)} UNIQUE ({', '.join(q(x) for x in cols)})")
    lines += enum_checks
    out.append(f"CREATE TABLE {q(t)} (\n" + ",\n".join(lines) + "\n);")
    if T["comment"]:
        out.append(f"COMMENT ON TABLE {q(t)} IS '{T['comment'].replace(chr(39), chr(39)*2)}';")
    for c in T["cols"]:
        if c["comment"]:
            out.append(f"COMMENT ON COLUMN {q(t)}.{q(c['name'])} IS '{c['comment'].replace(chr(39), chr(39)*2)}';")
    out.append("")

all_idx_names = set()
for t in TO_CREATE:
    for n, spec in tables[t]["indexes"]:
        iname = f"ix_{t}_{n}"[:63]
        assert iname not in all_idx_names, iname
        all_idx_names.add(iname)
        parts = [q(c) if p is None else f"left({q(c)}, {p})" for c, p in spec]
        expr = ", ".join(f"({x})" if x.startswith("left(") else x for x in parts)
        out.append(f"CREATE INDEX {q(iname)} ON {q(t)} ({expr});")
out.append("")
for t in TO_CREATE:
    for fk in tables[t]["fks"]:
        assert fk["ref_table"] in TO_CREATE, (t, fk)
        od = f" ON DELETE {fk['on_delete']}" if fk["on_delete"] else ""
        out.append(f"ALTER TABLE {q(t)} ADD CONSTRAINT {q(fk['name'])} FOREIGN KEY ({q(fk['col'])}) REFERENCES {q(fk['ref_table'])} ({q(fk['ref_col'])}){od};")
out.append("")

# MySQL "ON UPDATE current_timestamp()" -> BEFORE UPDATE trigger (fires only when another column changed and the column was not set explicitly)
triggers = []
for t in TO_CREATE:
    ucols = [c["name"] for c in tables[t]["cols"] if c["on_update"]]
    if not ucols:
        continue
    fn = f"stokit_on_update_{t}"
    arr = "ARRAY[" + ", ".join(f"'{c}'" for c in ucols) + "]"
    body = [f"CREATE FUNCTION {q(fn)}() RETURNS trigger LANGUAGE plpgsql AS $fn$", "BEGIN",
            f"    IF (to_jsonb(NEW) - {arr}) IS DISTINCT FROM (to_jsonb(OLD) - {arr}) THEN"]
    for c in ucols:
        body.append(f"        IF NEW.{q(c)} IS NOT DISTINCT FROM OLD.{q(c)} THEN NEW.{q(c)} := CURRENT_TIMESTAMP; END IF;")
    body += ["    END IF;", "    RETURN NEW;", "END", "$fn$;",
             f"CREATE TRIGGER {q('trg_'+t+'_on_update')} BEFORE UPDATE ON {q(t)} FOR EACH ROW EXECUTE FUNCTION {q(fn)}();", ""]
    out.append("\n".join(body))
    triggers.append(dict(table=t, trigger="trg_"+t+"_on_update", function=fn, columns=ucols, source="ON UPDATE current_timestamp()"))

# Source trigger update_target_progress_after_order (AFTER UPDATE ON zg_checkout), translated one-to-one.
need = {"zg_checkout": ["email", "status", "order_date", "order_id"], "zg_order_items": ["total_price", "order_id", "product_id"],
        "zg_product": ["category_id", "product_id"], "users": ["email", "id"],
        "zg_target_assignments": ["achieved_amount", "order_count", "status", "achieved_date", "updated_at", "user_id", "target_id"],
        "zg_targets": ["category_id", "start_date", "end_date", "target_amount", "status", "target_id"]}
for tb, cl in need.items():
    have = {c["name"] for c in tables[tb]["cols"]}
    assert set(cl) <= have, (tb, set(cl) - have)
out.append("""CREATE FUNCTION "stokit_trg_update_target_progress_after_order"() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.status = 'fulfilled' AND OLD.status IS DISTINCT FROM 'fulfilled' THEN
        WITH progress AS (
            SELECT ta.assignment_id, t.target_amount, calc.amt, calc.cnt
            FROM zg_target_assignments ta
            INNER JOIN zg_targets t ON ta.target_id = t.target_id
            CROSS JOIN LATERAL (
                SELECT COALESCE(SUM(oi.total_price), 0) AS amt,
                       COUNT(DISTINCT oi.order_id) AS cnt
                FROM zg_order_items oi
                INNER JOIN zg_product p ON oi.product_id = p.product_id
                WHERE p.category_id = t.category_id
                  AND oi.order_id IN (
                      SELECT c.order_id FROM zg_checkout c
                      WHERE c.email = (SELECT u.email FROM users u WHERE u.id = ta.user_id)
                        AND c.status = 'fulfilled'
                        AND c.order_date BETWEEN t.start_date AND (t.end_date + 1)
                  )
            ) calc
            WHERE t.status = 'ACTIVE'
              AND ta.user_id = (SELECT u2.id FROM users u2 WHERE u2.email = NEW.email)
        )
        UPDATE zg_target_assignments ta
        SET achieved_amount = progress.amt,
            order_count = progress.cnt,
            status = CASE WHEN progress.amt >= progress.target_amount THEN 'ACHIEVED' ELSE 'PENDING' END,
            achieved_date = CASE WHEN progress.amt >= progress.target_amount THEN CURRENT_DATE ELSE ta.achieved_date END,
            updated_at = CURRENT_TIMESTAMP
        FROM progress
        WHERE ta.assignment_id = progress.assignment_id;
    END IF;
    RETURN NULL;
END
$fn$;
CREATE TRIGGER "update_target_progress_after_order" AFTER UPDATE ON "zg_checkout" FOR EACH ROW EXECUTE FUNCTION "stokit_trg_update_target_progress_after_order"();
""")
triggers.append(dict(table="zg_checkout", trigger="update_target_progress_after_order", function="stokit_trg_update_target_progress_after_order",
                     columns=[], source="MariaDB trigger translated to PL/pgSQL CTE/LATERAL; requires isolated semantic validation"))
out.append("COMMIT;")

for t in TO_CREATE:
    T = tables[t]
    manifest["tables"][t] = dict(
        columns=[dict(name=c["name"], pg_type=pg_type(c), not_null=c["notnull"], identity=c["auto"], has_default=(pg_default(c) is not None and not c["auto"])) for c in T["cols"]],
        primary_key=T["pk"], uniques=[dict(name="uq_"+t+"_"+n, columns=c) for n, c in T["uniques"]],
        indexes=[dict(name=f"ix_{t}_{n}"[:63], columns=[c for c, _ in s]) for n, s in T["indexes"]],
        foreign_keys=T["fks"], enum_or_json_checks=[c["name"] for c in T["cols"] if c["typ"] == "enum" or c["check"]])
manifest["triggers"] = triggers
manifest["counts"] = {"tables_to_create": len(TO_CREATE), "columns": sum(len(v["columns"]) for v in manifest["tables"].values()),
                      "identity_columns": sum(1 for v in manifest["tables"].values() for c in v["columns"] if c["identity"]),
                      "foreign_keys": sum(len(v["foreign_keys"]) for v in manifest["tables"].values()),
                      "secondary_indexes": sum(len(v["indexes"]) for v in manifest["tables"].values()),
                      "unique_constraints": sum(len(v["uniques"]) for v in manifest["tables"].values()),
                      "triggers": len(triggers)}
(DOCS / "STOKIT_COMPLETE_DDL_CANDIDATE.sql").write_text("\n".join(out), encoding="utf-8")
(DOCS / "STOKIT_COMPLETE_DDL_CHANGE_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(manifest["counts"]), "to_create:", len(TO_CREATE))

