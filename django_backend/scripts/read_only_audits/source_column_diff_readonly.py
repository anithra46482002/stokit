"""READ-ONLY dump-vs-live column-level reconciliation (aggregates only).

Reads the sanitized dump file and streams a mariadb-dump (SELECT only, --single-transaction,
no locks) of the live source through the SAME SQL-literal parser, so both sides are decoded
identically. No row values, hashes or secrets are printed or saved: only counts, column names,
and numeric timestamp deltas. Run with DJANGO_ENV_FILE-free .env credentials read in-process.
"""
import json, os, re, subprocess, sys
from collections import Counter, defaultdict
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DUMP = Path(r"C:\Users\.MSI\Downloads\stokit_sql_work\u144866523_stokitDB.sanitized.sql")
ORIG = Path(r"C:\Users\.MSI\Downloads\stokit_sql_work\u144866523_stokitDB.sql")
BIN = Path(r"C:\Program Files\MariaDB 13.0\bin")


def env_file():
    out = {}
    for line in (ROOT / "django_backend" / ".env").read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"\s*(DB_[A-Z]+)\s*=\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def skip_quoted(text, i, q):
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == q:
            if i + 1 < n and text[i + 1] == q:
                i += 2
                continue
            return i + 1
        i += 1
    return n


def split_top(text):
    out, start, i, depth, n = [], 0, 0, 0, len(text)
    while i < n:
        c = text[i]
        if c in "'\"`":
            i = skip_quoted(text, i + 1, c)
            continue
        if c == "(":
            depth += 1
        elif c == ")" and depth:
            depth -= 1
        elif c == "," and depth == 0:
            out.append(text[start:i].strip())
            start = i + 1
        i += 1
    out.append(text[start:].strip())
    return out


def parse_tuples(values):
    rows, i, n, start, depth = [], 0, len(values), None, 0
    while i < n:
        c = values[i]
        if c in "'\"`":
            i = skip_quoted(values, i + 1, c)
            continue
        if c == "(":
            if depth == 0:
                start = i + 1
            depth += 1
        elif c == ")" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                rows.append(split_top(values[start:i]))
                start = None
        elif c == ";" and depth == 0:
            break
        i += 1
    return rows


def stmt_end(text, i):
    n, depth = len(text), 0
    while i < n:
        c = text[i]
        if c in "'\"`":
            i = skip_quoted(text, i + 1, c)
            continue
        if c == "(":
            depth += 1
        elif c == ")" and depth:
            depth -= 1
        elif c == ";" and depth == 0:
            return i + 1
        i += 1
    return n


ESC = {"0": "\0", "b": "\b", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a", "\\": "\\", "'": "'", '"': '"'}


def decode(token, ctype):
    t = token.strip()
    if t.upper() == "NULL":
        return None
    base = ctype.lower().split("(")[0].strip()
    if len(t) >= 2 and t[0] in "'\"" and t[-1] == t[0]:
        raw, out, i = t[1:-1], [], 0
        while i < len(raw):
            if raw[i] == "\\" and i + 1 < len(raw):
                out.append(ESC.get(raw[i + 1], "\\" + raw[i + 1]))
                i += 2
            elif raw[i] == t[0] and i + 1 < len(raw) and raw[i + 1] == t[0]:
                out.append(t[0])
                i += 2
            else:
                out.append(raw[i])
                i += 1
        v = "".join(out)
        try:
            if base in ("tinyint", "smallint", "mediumint", "int", "integer", "bigint", "year") and v != "":
                return int(v)
            if base in ("decimal", "numeric") and v != "":
                return Decimal(v)
            if base in ("float", "double", "real") and v != "":
                return float(v)
            if base == "date" and not v.startswith("0000"):
                return date.fromisoformat(v)
            if base in ("datetime", "timestamp") and v and not v.startswith("0000"):
                return datetime.fromisoformat(v.replace(" ", "T"))
            if base == "time" and v:
                return time.fromisoformat(v)
        except (ValueError, InvalidOperation):
            pass
        return v
    if t.upper().startswith("0X"):
        return bytes.fromhex(t[2:])
    try:
        if base in ("decimal", "numeric"):
            return Decimal(t)
        if base in ("float", "double", "real"):
            return float(t)
        if re.fullmatch(r"-?\d+", t):
            return int(t)
        if re.fullmatch(r"-?\d+\.\d+", t):
            return Decimal(t)
    except (ValueError, InvalidOperation):
        pass
    return t


def eq(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, Decimal)) and isinstance(b, (int, Decimal)) and not isinstance(a, bool):
        return Decimal(a) == Decimal(b)
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-9
        except (TypeError, ValueError):
            return False
    return type(a) == type(b) and a == b


def classify(a, b):
    if a is None or b is None:
        return "null_vs_value"
    if isinstance(a, datetime) and isinstance(b, datetime):
        return "datetime_delta"
    if isinstance(a, str) and isinstance(b, str):
        if a.strip() == b.strip():
            return "str_whitespace_only"
        if a.replace("\r\n", "\n") == b.replace("\r\n", "\n"):
            return "str_newline_only"
        if a.lower() == b.lower():
            return "str_case_only"
        return "str_content"
    return "type_or_value"


def load_inserts(sql, colmeta):
    data = defaultdict(list)
    for m in re.finditer(r"INSERT\s+INTO\s+`([^`]+)`\s*(\((.*?)\))?\s*VALUES\s*", sql, re.I | re.S):
        t = m.group(1)
        end = stmt_end(sql, m.end())
        cols = [c.strip().strip("`") for c in split_top(m.group(3))] if m.group(3) else [c for c, _ in colmeta[t]]
        types = dict(colmeta[t])
        for tokens in parse_tuples(sql[m.end():end]):
            if len(tokens) != len(cols):
                data[t].append(None)
                continue
            data[t].append({c: decode(tok, types.get(c, "")) for c, tok in zip(cols, tokens)})
    return data


def main():
    cfg = env_file()
    envp = dict(os.environ, MYSQL_PWD=cfg["DB_PASSWORD"])
    base = ["-h", cfg["DB_HOST"], "-P", cfg["DB_PORT"], "-u", cfg["DB_USER"]]
    db = cfg["DB_NAME"]
    assert db == "stokit_legacy_test"

    def q(sql):
        r = subprocess.run([str(BIN / "mariadb.exe")] + base + ["-D", db, "--batch", "--skip-column-names", "-e", "SET SESSION TRANSACTION READ ONLY; " + sql],
                           capture_output=True, text=True, env=envp, encoding="utf-8")
        return [ln.split("\t") for ln in r.stdout.splitlines() if ln]

    colmeta = defaultdict(list)
    for t, c, ct in q("select table_name,column_name,column_type from information_schema.columns where table_schema=database() order by table_name,ordinal_position"):
        colmeta[t].append((c, ct))
    pk = defaultdict(list)
    for t, c in q("select table_name,column_name from information_schema.statistics where table_schema=database() and index_name='PRIMARY' order by table_name,seq_in_index"):
        pk[t].append(c)

    sql_dump = DUMP.read_text(encoding="utf-8", errors="replace")
    dump = load_inserts(sql_dump, colmeta)
    r = subprocess.run([str(BIN / "mariadb-dump.exe")] + base + ["--single-transaction", "--skip-lock-tables", "--no-create-info", "--skip-triggers", "--no-tablespaces", "--hex-blob", db],
                       capture_output=True, text=True, env=envp, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("live dump failed rc=%s" % r.returncode)
    live = load_inserts(r.stdout, colmeta)

    report = {"scope": "shared tables with INSERT data in dump or live; aggregates only", "tables": {}}
    for t in sorted(set(dump) | set(live)):
        drows, lrows = dump.get(t, []), live.get(t, [])
        bad_d, bad_l = sum(r is None for r in drows), sum(r is None for r in lrows)
        drows, lrows = [r for r in drows if r], [r for r in lrows if r]
        keycols = pk.get(t) or []
        entry = {"dump_rows": len(drows), "live_rows": len(lrows), "pk": keycols, "arity_errors": bad_d + bad_l}
        if not keycols:
            entry["note"] = "no primary key; not compared by key"
            report["tables"][t] = entry
            continue
        dk = {tuple(r[c] for c in keycols): r for r in drows}
        lk = {tuple(r[c] for c in keycols): r for r in lrows}
        entry["dump_dup_keys"] = len(drows) - len(dk)
        entry["live_dup_keys"] = len(lrows) - len(lk)
        shared = set(dk) & set(lk)
        entry["shared"] = len(shared)
        entry["dump_only"] = len(set(dk) - set(lk))
        entry["live_only"] = len(set(lk) - set(dk))
        colcount, kinds, deltas = Counter(), defaultdict(Counter), defaultdict(Counter)
        identical = 0
        for k in shared:
            diffs = [c for c, _ in colmeta[t] if not eq(dk[k].get(c), lk[k].get(c))]
            if not diffs:
                identical += 1
            for c in diffs:
                colcount[c] += 1
                kind = classify(dk[k].get(c), lk[k].get(c))
                kinds[c][kind] += 1
                if kind == "datetime_delta":
                    deltas[c][int((dk[k][c] - lk[k][c]).total_seconds())] += 1
        entry["identical_rows"] = identical
        entry["differing_rows"] = len(shared) - identical
        entry["column_diffs"] = {c: {"rows": n, "kinds": dict(kinds[c]), **({"datetime_delta_seconds": dict(deltas[c])} if deltas[c] else {})} for c, n in colcount.items()}
        # timestamp ranges (non-sensitive aggregates) for both sides
        rng = {}
        for c, ct in colmeta[t]:
            if ct.split("(")[0].lower() in ("datetime", "timestamp", "date"):
                dv = [r[c] for r in drows if isinstance(r.get(c), (datetime, date))]
                lv = [r[c] for r in lrows if isinstance(r.get(c), (datetime, date))]
                if dv or lv:
                    rng[c] = {"dump": [str(min(dv)), str(max(dv))] if dv else None, "live": [str(min(lv)), str(max(lv))] if lv else None}
        entry["datetime_ranges"] = rng
        # live-only / dump-only key ranges (integer single-key only)
        if len(keycols) == 1:
            kd = sorted(k[0] for k in dk if isinstance(k[0], int))
            kl = sorted(k[0] for k in lk if isinstance(k[0], int))
            entry["dump_pk_range"] = [kd[0], kd[-1]] if kd else None
            entry["live_pk_range"] = [kl[0], kl[-1]] if kl else None
            entry["live_only_ids"] = sorted(k[0] for k in set(lk) - set(dk))[:30]
            entry["dump_only_ids_count"] = entry["dump_only"]
        report["tables"][t] = entry
    out = ROOT / "docs" / "STOKIT_SOURCE_COLUMN_DIFF_READONLY.json"
    out.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    for t, e in report["tables"].items():
        print(t, {k: e.get(k) for k in ("dump_rows", "live_rows", "shared", "identical_rows", "dump_only", "live_only")}, "cols:", {c: v["rows"] for c, v in e.get("column_diffs", {}).items()})


if __name__ == "__main__":
    main()
