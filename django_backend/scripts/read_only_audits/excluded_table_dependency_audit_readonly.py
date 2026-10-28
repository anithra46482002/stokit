"""READ-ONLY static dependency audit for the 16 excluded historical tables.
Reads: PHP backup tree, original SQL dump, Django/React sources. Writes only the JSON output file.
Static evidence only: it cannot prove runtime reachability or deployment provenance.
usage: excluded_table_dependency_audit_readonly.py [--php ROOT] [--dump FILE] [--out FILE]
"""
import argparse, json, re
from pathlib import Path

TABLES = ["users1", "zg_api_keys", "zg_banner", "zg_brands", "zg_cod", "zg_headings", "zg_headings_new", "zg_logo",
          "zg_product_warehouse", "zg_reels", "zg_social_media", "zg_target_activity_log", "zg_testy",
          "zg_vari_product", "zg_vari_product_images", "zg_vari_variant"]
ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
KW = [("INSERT", r"INSERT\s+(?:IGNORE\s+)?INTO"), ("REPLACE", r"REPLACE\s+INTO"), ("DELETE", r"DELETE\s+FROM"),
      ("UPDATE", r"UPDATE"), ("SELECT/read", r"(?:FROM|JOIN)"), ("SCHEMA", r"(?:ALTER|CREATE|DROP|TRUNCATE)\s+TABLE")]
NAME_RE = {t: re.compile(r"(?<![A-Za-z0-9_])" + re.escape(t) + r"(?![A-Za-z0-9_])", re.I) for t in TABLES}


def is_comment(line, pos):
    s = line.lstrip()
    if s.startswith(("//", "#", "*", "/*", "<!--")):
        return True
    i = line.find("//")
    return 0 <= i < pos and "http" not in line[max(0, i - 6):i]


def classify(lines, idx, m):
    win_start = max(0, idx - 4)
    before = " ".join(l.strip() for l in lines[win_start:idx]) + " " + lines[idx][:m.start()]
    before = before[-260:]
    best, best_pos = None, -1
    for label, pat in KW:
        for mm in re.finditer(r"(?<![A-Za-z_])" + pat + r"(?![A-Za-z_])", before, re.I):
            if label == "SELECT/read" and re.search(r"DELETE\s+$", before[:mm.start()], re.I):
                continue
            if mm.start() >= best_pos:
                best, best_pos = label, mm.start()
    return best or "unclear"


def enclosing_function(lines, idx):
    for j in range(idx, -1, -1):
        m = re.search(r"function\s+(\w+)\s*\(", lines[j])
        if m:
            return m.group(1)
    return "(top-level script)"


PREFIX_RES = [re.compile(r"\{\$(?:qt|table_prefix|prefix)\}_"), re.compile(r"\$(?:qt|table_prefix|prefix)\s*\.\s*['\"]_")]


def normalize(line):
    """Resolve the PHP table-prefix variable ($qt / $table_prefix = 'zg') so interpolated names become literal."""
    for rx in PREFIX_RES:
        line = rx.sub("zg_", line)
    return line


def scan_php(php_root):
    hits = {t: [] for t in TABLES}
    dyn = []
    files = sorted(php_root.rglob("*.php"))
    texts = {}
    for f in files:
        try:
            texts[f] = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
    for f, raw in texts.items():
        rel = str(f.relative_to(php_root)).replace("\\", "/")
        lines = [normalize(x) for x in raw]
        for i, line in enumerate(lines):
            for t, rx in NAME_RE.items():
                m = rx.search(line)
                if m:
                    c = is_comment(line, m.start())
                    hits[t].append({"file": rel, "line": i + 1, "function": enclosing_function(lines, i),
                                    "kind": "comment-only" if c else classify(lines, i, m),
                                    "via_prefix_variable": not rx.search(raw[i]),
                                    "text": raw[i].strip()[:160]})
            if re.search(r"(?:FROM|INTO|UPDATE|JOIN)\s+[`]?(?:\{?\$)", line, re.I) or re.search(r"['\"]zg_['\"]\s*\.", line):
                dyn.append({"file": rel, "line": i + 1, "text": line.strip()[:160]})
    inc = {}
    for f, lines in texts.items():
        for i, line in enumerate(lines):
            for m in re.finditer(r"(?:include|require)(?:_once)?\s*\(?\s*['\"]([^'\"]+\.php)['\"]", line):
                inc.setdefault(Path(m.group(1)).name, set()).add(str(f.relative_to(php_root)).replace("\\", "/"))
    return hits, dyn, inc, len(files)


def scan_dump(dump):
    info = {t: {"columns": [], "inbound_fk": [], "outbound_fk": [], "triggers_mentioning": [], "approx_rows": 0,
                "create_found": False} for t in TABLES}
    cur_create = cur_alter = cur_insert = None
    trig = None
    other_tables_fk = []
    with open(dump, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = re.match(r"CREATE TABLE `(\w+)`", line)
            if m:
                cur_create = m.group(1)
                if cur_create in info:
                    info[cur_create]["create_found"] = True
                cur_insert = None
                continue
            if cur_create:
                if line.startswith(")"):
                    cur_create = None
                elif cur_create in info:
                    mc = re.match(r"\s+`(\w+)` (.+?),?$", line)
                    if mc:
                        info[cur_create]["columns"].append(f"{mc.group(1)} {mc.group(2)[:60]}")
                continue
            m = re.match(r"ALTER TABLE `(\w+)`", line)
            if m:
                cur_alter = m.group(1)
            fk = re.search(r"FOREIGN KEY \(([^)]*)\) REFERENCES `(\w+)`", line)
            if fk and cur_alter:
                if cur_alter in info:
                    info[cur_alter]["outbound_fk"].append(f"{fk.group(1)} -> {fk.group(2)}")
                if fk.group(2) in info:
                    info[fk.group(2)]["inbound_fk"].append(f"{cur_alter}.{fk.group(1)}")
            if line.rstrip().endswith(";") and not line.startswith(" "):
                cur_alter = None if not line.startswith("ALTER") else cur_alter
            mi = re.match(r"INSERT INTO `(\w+)`", line)
            if mi:
                cur_insert = mi.group(1)
                continue
            if cur_insert:
                if line.startswith("("):
                    if cur_insert in info:
                        info[cur_insert]["approx_rows"] += 1
                    if line.rstrip().endswith(";"):
                        cur_insert = None
                elif line.strip() == "" or line.startswith("--"):
                    cur_insert = None
                continue
            if "TRIGGER `" in line:
                trig = {"name": re.search(r"TRIGGER `(\w+)`", line).group(1), "body": line}
            elif trig is not None:
                trig["body"] += line
            if trig is not None and line.rstrip().endswith(";;"):
                for t in TABLES:
                    if NAME_RE[t].search(trig["body"]):
                        info[t]["triggers_mentioning"].append(trig["name"])
                trig = None
    return info


def scan_repo_sources():
    res = {t: {"django_runtime": [], "django_tests_migrations_tools": [], "react": []} for t in TABLES}
    for base, exts, key_fn in ((ROOT, (".py",), "django"), (REPO / "admin_frontend" / "src", (".js", ".jsx", ".ts", ".tsx"), "react")):
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if not f.is_file() or f.suffix not in exts or any(p in f.parts for p in (".venv", "node_modules", "backups")):
                continue
            rel = str(f.relative_to(REPO)).replace("\\", "/")
            if "/docs/" in rel or rel.endswith("collation_eval.py") or "excluded_table_dependency_audit" in rel:
                continue
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines):
                for t, rx in NAME_RE.items():
                    if rx.search(line):
                        if key_fn == "react":
                            res[t]["react"].append(f"{rel}:{i + 1}")
                        else:
                            bucket = "django_tests_migrations_tools" if ("test" in f.name or "/scripts/" in rel or "/migrations/" in rel) else "django_runtime"
                            res[t][bucket].append(f"{rel}:{i + 1}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--php", default=r"C:\Users\.MSI\Downloads\StokIt_PHP_Backup_20261012\Host")
    ap.add_argument("--dump", default=r"C:\Users\.MSI\Downloads\stokit_sql_work\u144866523_stokitDB.sql")
    ap.add_argument("--out", default=str(ROOT / "docs" / "STOKIT_EXCLUDED_TABLE_DEPENDENCY_MATRIX.json"))
    a = ap.parse_args()
    hits, dyn, inc, nfiles = scan_php(Path(a.php))
    dump = scan_dump(a.dump)
    repo = scan_repo_sources()
    out = {"php_files_scanned": nfiles, "dynamic_table_name_candidates": dyn, "tables": {}}
    for t in TABLES:
        h = hits[t]
        files = sorted({x["file"] for x in h})
        out["tables"][t] = {"php_hits": h, "php_files": files,
                            "included_by": {Path(f).name: sorted(inc.get(Path(f).name, [])) for f in files},
                            "dump": dump[t], "repo": repo[t]}
    Path(a.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    for t in TABLES:
        h = out["tables"][t]["php_hits"]
        kinds = {}
        for x in h:
            kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
        d = out["tables"][t]["dump"]
        print(f"{t}: php_hits={len(h)} kinds={kinds} files={out['tables'][t]['php_files']} dump_rows~{d['approx_rows']} "
              f"inFK={d['inbound_fk']} outFK={d['outbound_fk']} trig={d['triggers_mentioning']} "
              f"django_rt={len(repo[t]['django_runtime'])} django_other={len(repo[t]['django_tests_migrations_tools'])} react={len(repo[t]['react'])}")
    print("dynamic_candidates:", len(dyn))


if __name__ == "__main__":
    main()
