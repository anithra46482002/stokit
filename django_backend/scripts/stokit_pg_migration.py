"""Read-only MariaDB/PostgreSQL migration planner. Import remains deliberately disabled."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE = "stokit_legacy_test"
TARGET = "stokit_postgres_dev"
CONFIRM = "MIGRATE STOKIT TO POSTGRESQL"

def validate(source_name, source_engine, target_name, target_engine):
    if source_name != SOURCE: raise ValueError("Unexpected source database; refusing")
    if target_name != TARGET: raise ValueError("Unexpected target database; refusing")
    if source_engine not in ("mysql", "mariadb", "django.db.backends.mysql"): raise ValueError("Source must be MariaDB/MySQL")
    if target_engine not in ("postgres", "postgresql", "django.db.backends.postgresql"): raise ValueError("Target must be PostgreSQL")
    if source_name == target_name: raise ValueError("Source and target must differ")

def _scan_sql_until_semicolon(sql, start):
    """Return statement end, ignoring semicolons inside quoted SQL literals."""
    i, quote, depth = start, None, 0
    while i < len(sql):
        ch = sql[i]
        if quote:
            if ch == "\\" and i + 1 < len(sql):
                i += 2
                continue
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"', chr(96)):
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
        elif ch == ";" and depth == 0:
            return i
        i += 1
    return len(sql)


def parse_insert_tuple_count(sql):
    """Count top-level VALUES tuples, respecting escaped/doubled quotes and delimiters."""
    import re
    match = re.search(r"\bVALUES\b", sql, re.I)
    if not match:
        return 0
    text = sql[match.end():_scan_sql_until_semicolon(sql, match.end())]
    depth, quote, count, i = 0, None, 0, 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\" and i + 1 < len(text):
                i += 2
                continue
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"', chr(96)):
            quote = ch
        elif ch == "(":
            if depth == 0:
                count += 1
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
        i += 1
    return count


def _canonical_value(value):
    """Convert supported DB scalars to stable, type-tagged JSON values."""
    from datetime import date, datetime, time
    from decimal import Decimal
    if value is None: return {"type": "null"}
    if isinstance(value, bool): return {"type": "bool", "value": value}
    if isinstance(value, int): return {"type": "int", "value": str(value)}
    if isinstance(value, Decimal): return {"type": "decimal", "value": format(value, "f")}
    if isinstance(value, datetime): return {"type": "datetime", "value": value.isoformat(timespec="microseconds")}
    if isinstance(value, date): return {"type": "date", "value": value.isoformat()}
    if isinstance(value, time): return {"type": "time", "value": value.isoformat(timespec="microseconds")}
    if isinstance(value, bytes): return {"type": "bytes", "value": value.hex()}
    if isinstance(value, float): return {"type": "float", "value": value.hex()}
    if isinstance(value, str): return {"type": "str", "value": value}
    return {"type": type(value).__name__, "value": str(value)}


def canonical_row_fingerprint(columns, values):
    """SHA-256 of ordered column names and type-tagged values; exclude sensitive columns upstream."""
    import hashlib
    payload = {"columns": list(columns), "values": [_canonical_value(v) for v in values]}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compare_column_definitions(source_columns, target_columns):
    """Return metadata-only column differences; never inspect table rows."""
    source = {c.get("name"): c for c in source_columns}
    target = {c.get("name"): c for c in target_columns}
    differences = []
    for name in sorted(set(source) | set(target)):
        left, right = source.get(name), target.get(name)
        if left is None:
            differences.append({"column": name, "kind": "target_only"})
        elif right is None:
            differences.append({"column": name, "kind": "source_only"})
        else:
            fields = [key for key in ("type", "nullable", "default") if left.get(key) != right.get(key)]
            if fields:
                differences.append({"column": name, "kind": "definition_mismatch", "fields": fields})
    return differences


def dependency_order(dependencies):
    """Topologically order table -> prerequisite names; reject unknowns/cycles."""
    remaining = {name: set(items) for name, items in dependencies.items()}
    unknown = {dep for deps in remaining.values() for dep in deps if dep not in remaining}
    if unknown:
        raise ValueError("Unknown dependency table(s): " + ", ".join(sorted(unknown)))
    ordered = []
    while remaining:
        ready = sorted(name for name, deps in remaining.items() if not deps)
        if not ready:
            raise ValueError("Dependency cycle detected")
        ordered.extend(ready)
        for name in ready:
            remaining.pop(name)
        for deps in remaining.values():
            deps.difference_update(ready)
    return ordered


def classify_duplicate(existing_row, incoming_row, key_fields):
    """Classify duplicate keys without performing writes."""
    if not key_fields:
        raise ValueError("At least one key field is required")
    if any(field not in existing_row or field not in incoming_row for field in key_fields):
        raise ValueError("Missing duplicate key field")
    if any(existing_row[field] != incoming_row[field] for field in key_fields):
        return "different_key"
    return "identical_duplicate" if existing_row == incoming_row else "conflicting_duplicate"


def execution_is_implemented():
    """This version deliberately has no importer; approval text cannot enable writes."""
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Read metadata and row counts only (default)")
    parser.add_argument("--execute", action="store_true", help="Request import; currently blocked pending approval and reviewed DDL")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--report", default="stokit_pg_migration_report.json")
    args = parser.parse_args()
    if args.execute:
        if args.confirm != CONFIRM:
            print("REFUSED: exact --confirm phrase required", file=sys.stderr); return 2
        print("REFUSED: import is not implemented until source authority, backup, schema conversion and manifest are reviewed", file=sys.stderr); return 3
    try:
        from dotenv import dotenv_values
        src_cfg = {k:v for k,v in dotenv_values(os.environ.get("STOKIT_SOURCE_ENV_FILE", ".env")).items() if v is not None}
        dst_cfg = {k:v for k,v in dotenv_values(os.environ.get("STOKIT_TARGET_ENV_FILE", ".env.postgres")).items() if v is not None}
        validate(src_cfg.get("DB_NAME", ""), src_cfg.get("DB_ENGINE", "django.db.backends.mysql"), dst_cfg.get("DB_NAME", ""), dst_cfg.get("DB_ENGINE", "django.db.backends.postgresql"))
        import MySQLdb
        import psycopg
        src = MySQLdb.connect(host=src_cfg.get("DB_HOST", "127.0.0.1"), port=int(src_cfg.get("DB_PORT", "3306")), user=src_cfg.get("DB_USER", ""), password=src_cfg.get("DB_PASSWORD", ""), database=src_cfg["DB_NAME"], connect_timeout=8, charset="utf8mb4")
        dst = psycopg.connect(host=dst_cfg.get("DB_HOST", "127.0.0.1"), port=int(dst_cfg.get("DB_PORT", "5432")), user=dst_cfg.get("DB_USER", ""), password=dst_cfg.get("DB_PASSWORD", ""), dbname=dst_cfg["DB_NAME"], connect_timeout=8, options="-c default_transaction_read_only=on")
        report = {"generated_at_utc":datetime.now(timezone.utc).isoformat(), "mode":"read-only dry-run", "source":{"database":src_cfg["DB_NAME"]}, "target":{"database":dst_cfg["DB_NAME"]}, "tables":{}, "schema_differences":[], "failures":[], "skipped_records":[], "warnings":["No import occurs in this version.", "No schema is created; legacy unmanaged tables need reviewed PostgreSQL DDL.", "Source of truth is not confirmed; do not execute migration."]}
        try:
            with src.cursor() as cur:
                cur.execute("SET SESSION TRANSACTION READ ONLY")
                cur.execute("SELECT VERSION()"); report["source"]["version"] = cur.fetchone()[0]
                cur.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME", (src_cfg["DB_NAME"],)); source_tables = [r[0] for r in cur.fetchall()]
                for table in source_tables:
                    cur.execute("SELECT COUNT(*) FROM `" + table.replace("`", "``") + "`"); count = int(cur.fetchone()[0])
                    cur.execute("SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION", (src_cfg["DB_NAME"], table))
                    columns = [{"name":r[0], "type":r[1], "nullable":r[2], "default":str(r[3]) if r[3] is not None else None, "extra":r[4]} for r in cur.fetchall()]
                    report["tables"][table] = {"source_rows":count, "source_columns":columns, "target_rows":None, "target_columns":None, "status":"source_only"}
            with dst.cursor() as cur:
                cur.execute("SELECT version()"); report["target"]["version"] = cur.fetchone()[0]
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name"); target_tables = [r[0] for r in cur.fetchall()]
                for table in target_tables:
                    cur.execute('SELECT COUNT(*) FROM public."' + table.replace('"', '""') + '"'); count = int(cur.fetchone()[0])
                    cur.execute("SELECT column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,))
                    columns = [{"name":r[0], "type":r[1], "nullable":r[2], "default":r[3]} for r in cur.fetchall()]
                    report["tables"].setdefault(table, {"source_rows":None, "source_columns":None}).update({"target_rows":count, "target_columns":columns, "status":"present_both" if table in source_tables else "target_only"})
            report["source"]["table_count"] = len(source_tables); report["target"]["table_count"] = len(target_tables)
        finally:
            src.close(); dst.close()
        out = Path(args.report).resolve(); out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("Read-only report written: " + str(out))
        print("Source tables: %s; target tables: %s; no database writes performed." % (report["source"]["table_count"], report["target"]["table_count"]))
        return 0
    except Exception as exc:
        print("Planner failed: %s: %s" % (type(exc).__name__, exc), file=sys.stderr); return 1

if __name__ == "__main__":
    raise SystemExit(main())
