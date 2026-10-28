"""READ-ONLY: original-vs-sanitized dump integrity and the 3,219-vs-3,224 tuple discrepancy.
Outputs only lengths, counts and structure (never row values)."""
import hashlib, itertools, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).resolve().parents[3]
ORIG = Path(r"C:\Users\.MSI\Downloads\stokit_sql_work\u144866523_stokitDB.sql")
SAN = Path(r"C:\Users\.MSI\Downloads\stokit_sql_work\u144866523_stokitDB.sanitized.sql")


def tuples(values, backslash_escapes):
    """Count top-level tuples; backslash_escapes=False emulates NO_BACKSLASH_ESCAPES."""
    n, i, depth, count = len(values), 0, 0, 0
    while i < n:
        c = values[i]
        if c in "'\"`":
            q, i = c, i + 1
            while i < n:
                d = values[i]
                if d == "\\" and backslash_escapes and q != "`":
                    i += 2
                    continue
                if d == q:
                    if i + 1 < n and values[i + 1] == q:
                        i += 2
                        continue
                    break
                i += 1
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")" and depth:
            depth -= 1
            if depth == 0:
                count += 1
        elif c == ";" and depth == 0:
            break
        i += 1
    return count


def end_of_stmt(text, start, backslash_escapes):
    n, i, depth = len(text), start, 0
    while i < n:
        c = text[i]
        if c in "'\"`":
            q, i = c, i + 1
            while i < n:
                d = text[i]
                if d == "\\" and backslash_escapes and q != "`":
                    i += 2
                    continue
                if d == q:
                    if i + 1 < n and text[i + 1] == q:
                        i += 2
                        continue
                    break
                i += 1
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")" and depth:
            depth -= 1
        elif c == ";" and depth == 0:
            return i + 1
        i += 1
    return n


def scan(path, esc):
    sql = path.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in re.finditer(r"INSERT\s+INTO\s+`([^`]+)`\s*\(.*?\)\s*VALUES\s*", sql, re.I | re.S):
        e = end_of_stmt(sql, m.end(), esc)
        out.append((m.group(1), tuples(sql[m.end():e], esc), e - m.start()))
    return out, sql


def main():
    rep = {"original_sha256": hashlib.sha256(ORIG.read_bytes()).hexdigest()}
    # 1. line-level diff of original vs sanitized (lengths only)
    diffs = []
    with ORIG.open("rb") as a, SAN.open("rb") as b:
        for n, (x, y) in enumerate(itertools.zip_longest(a, b), 1):
            if x != y:
                diffs.append({"line": n, "orig_len": None if x is None else len(x), "san_len": None if y is None else len(y)})
    rep["differing_lines"] = diffs
    # 2. tuple counts under both escape semantics, original vs sanitized
    for label, path in (("original", ORIG), ("sanitized", SAN)):
        for esc in (True, False):
            rows, sql = scan(path, esc)
            key = "%s_backslash_escapes_%s" % (label, esc)
            rep[key] = {"statements": len(rows), "tuples": sum(r[1] for r in rows),
                        "zg_product": [r[1] for r in rows if r[0] == "zg_product"],
                        "zg_product_stmt_bytes": [r[2] for r in rows if r[0] == "zg_product"]}
            if label == "original" and esc:
                # structure of backslash runs larger than 1 MiB (no content emitted)
                runs = []
                for m in re.finditer(r"\\{1048576,}", sql):
                    nxt = sql[m.end():m.end() + 1]
                    runs.append({"offset": m.start(), "length": m.end() - m.start(), "odd": (m.end() - m.start()) % 2 == 1, "next_char": nxt if nxt in ("'", ",", ")") else "other"})
                rep["giant_backslash_runs"] = runs
    out = ROOT / "docs" / "STOKIT_DUMP_INTEGRITY_READONLY.json"
    out.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "original_sha256"}, indent=1))


if __name__ == "__main__":
    main()
