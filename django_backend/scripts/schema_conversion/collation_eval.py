"""Evaluate zg_location.city_name collation parity: MariaDB utf8mb4_uca1400_ai_ci vs PostgreSQL candidates.

SAFETY: runs ONLY against (a) a disposable MariaDB instance on 127.0.0.1:3399 and (b) a disposable PostgreSQL
database that this script creates (default stokit_collation_eval_20261015). It refuses any other database name
and never connects to stokit_postgres_dev for writes. Credentials come from .env.postgres and are never printed.

usage: collation_eval.py [--pg-db NAME] [--maria-port 3399] [--out PATH]
"""
import argparse, json, subprocess
from pathlib import Path
import psycopg

ROOT = Path(__file__).resolve().parents[2]
MARIADB = r"C:\Program Files\MariaDB 13.0\bin\mariadb.exe"
SRC_COLL = "utf8mb4_uca1400_ai_ci"

PAIRS = [  # (label, a, b)
    ("case Kochi/kochi", "Kochi", "kochi"),
    ("accent cafe-acute/cafe", "caf\u00e9", "cafe"),
    ("NFC vs NFD cafe-acute", "caf\u00e9", "cafe\u0301"),
    ("trailing space", "Kochi", "Kochi "),
    ("two trailing spaces", "Kochi", "Kochi  "),
    ("leading space", "Kochi", " Kochi"),
    ("trailing tab", "Kochi", "Kochi\t"),
    ("trailing NBSP", "Kochi", "Kochi\u00a0"),
    ("inner space", "Ko chi", "Kochi"),
    ("sharp s Strasse", "Stra\u00dfe", "Strasse"),
    ("ae ligature", "\u00e6", "ae"),
    ("dotted I Istanbul", "\u0130stanbul", "istanbul"),
    ("dotless i", "\u0131", "i"),
    ("fullwidth K", "\uff2bochi", "Kochi"),
    ("ligature fi", "\ufb01", "fi"),
    ("zero-width joiner", "Koc\u200dhi", "Kochi"),
    ("Kelvin sign", "\u212a", "k"),
    ("o-stroke", "\u00f8", "o"),
    ("l-stroke", "\u0142", "l"),
    ("Malayalam precomposed vs decomposed vowel", "\u0d15\u0d4a", "\u0d15\u0d46\u0d3e"),
    ("hyphen Kochi-City/KochiCity", "Kochi-City", "KochiCity"),
    ("empty vs space", "", " "),
    ("control Kochi/Kochin", "Kochi", "Kochin"),
]


def hexlit(s):
    return "X'" + s.encode("utf-8").hex() + "'"


def load_env():
    env = {}
    for line in (ROOT / ".env.postgres").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("\"'")
    return env


def maria(sql, port):
    p = subprocess.run([MARIADB, "-uroot", "-h127.0.0.1", f"-P{port}", "--protocol=tcp",
                        "--default-character-set=utf8mb4", "--batch", "--raw", "--skip-column-names", "--force"],
                       input=sql, capture_output=True, text=True, encoding="utf-8")
    return p.stdout, p.stderr


def run_mariadb(port):
    res = {"equality": {}, "unique_collision": {}, "like_contains": {}}
    lines = ["SELECT 'VERSION', VERSION();", "DROP DATABASE IF EXISTS collation_eval;",
             "CREATE DATABASE collation_eval DEFAULT CHARACTER SET utf8mb4 COLLATE " + SRC_COLL + ";",
             "USE collation_eval;",
             "CREATE TABLE zg_location (location_id int(11) NOT NULL AUTO_INCREMENT, city_name varchar(100) NOT NULL,"
             " PRIMARY KEY (location_id), UNIQUE KEY city_name (city_name)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
             " COLLATE=" + SRC_COLL + ";",
             "SELECT 'TABLE_COLLATION', TABLE_COLLATION FROM information_schema.TABLES"
             " WHERE TABLE_SCHEMA='collation_eval' AND TABLE_NAME='zg_location';"]
    for i, (label, a, b) in enumerate(PAIRS):
        A, B = "_utf8mb4 " + hexlit(a), "_utf8mb4 " + hexlit(b)
        lines.append(f"SELECT 'EQ|{i}', ({A} COLLATE {SRC_COLL}) = {B};")
        lines.append("TRUNCATE zg_location;")
        lines.append(f"INSERT INTO zg_location (city_name) VALUES ({A});")
        lines.append(f"INSERT INTO zg_location (city_name) VALUES ({B});")
        lines.append(f"SELECT 'ROWS|{i}', COUNT(*) FROM zg_location;")
        lines.append(f"SELECT 'LIKE|{i}', COUNT(*) FROM zg_location WHERE city_name LIKE CONCAT('%', {A}, '%');")
    out, err = maria("\n".join(lines) + "\n", port)
    meta = {}
    for ln in out.splitlines():
        parts = ln.split("\t")
        if parts[0] in ("VERSION", "TABLE_COLLATION"):
            meta[parts[0]] = parts[1]
        elif "|" in parts[0]:
            kind, idx = parts[0].split("|")
            idx = int(idx)
            if kind == "EQ":
                res["equality"][idx] = parts[1] == "1"
            elif kind == "ROWS":
                res["unique_collision"][idx] = parts[1] == "1"  # 1 row => 2nd insert rejected as duplicate
            elif kind == "LIKE":
                res["like_contains"][idx] = int(parts[1])
    return meta, res, len([e for e in err.splitlines() if "ERROR" in e])


def dec(s):
    return f"convert_from(decode('{s.encode('utf-8').hex()}','hex'),'UTF8')"


def run_pg(dbname):
    env = load_env()
    assert dbname.startswith("stokit_collation_eval_"), "refusing non-disposable database name"
    base = dict(host=env["DB_HOST"], port=env["DB_PORT"], user=env["DB_USER"], password=env["DB_PASSWORD"])
    adm = psycopg.connect(dbname="postgres", autocommit=True, **base)
    info = {}
    c = adm.cursor()
    c.execute("select version()"); info["server"] = c.fetchone()[0]
    c.execute("select datname, datlocprovider, datcollate from pg_database"
              " where datname='stokit_postgres_dev'")
    info["target_db_locale"] = c.fetchall()
    c.execute("select 1 from pg_database where datname=%s", (dbname,))
    if c.fetchone():
        raise SystemExit(f"{dbname} already exists; choose a new disposable name")
    c.execute(f"CREATE DATABASE \"{dbname}\" TEMPLATE template0 ENCODING 'UTF8'")
    conn = psycopg.connect(dbname=dbname, autocommit=True, **base)
    c = conn.cursor()
    c.execute("select collname, collprovider, collisdeterministic from pg_collation"
              " where collprovider='i' and collname like 'und%' order by 1")
    info["icu_und_collations_preinstalled"] = [(r[0], r[2]) for r in c.fetchall()][:20]
    c.execute("select name from pg_available_extensions where name in ('citext','unaccent') order by 1")
    info["extensions_available"] = [r[0] for r in c.fetchall()]
    c.execute("CREATE COLLATION ci_ai (provider=icu, locale='und-u-ks-level1', deterministic=false)")
    c.execute("CREATE COLLATION ci_as (provider=icu, locale='und-u-ks-level2', deterministic=false)")
    cands = {
        "default_deterministic": ("", "{a} = {b}", True),
        "und-x-icu_deterministic": ('COLLATE "und-x-icu"', "{a} = {b}", True),
        "nondeterministic_ks-level1 (ci+ai)": ("COLLATE ci_ai", "{a} COLLATE ci_ai = {b}", True),
        "nondeterministic_ks-level2 (ci, accent-sensitive)": ("COLLATE ci_as", "{a} COLLATE ci_as = {b}", True),
        "ks-level1 + rtrim expression unique index": ("COLLATE ci_ai",
                                                       "rtrim({a}, ' ') COLLATE ci_ai = rtrim({b}, ' ')", False),
    }
    results = {}
    for n, (name, (colcoll, expr, plain_uq)) in enumerate(cands.items()):
        tbl = f"t_cand_{n}"
        c.execute(f"CREATE TABLE {tbl} (location_id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,"
                  f" city_name varchar(100) NOT NULL {colcoll})")
        if plain_uq:
            c.execute(f"ALTER TABLE {tbl} ADD CONSTRAINT uq_{n} UNIQUE (city_name)")
        else:
            c.execute(f"CREATE UNIQUE INDEX uq_{n} ON {tbl} ((rtrim(city_name, ' ') COLLATE ci_ai))")
        eq, uqres, like = {}, {}, {}
        for i, (label, a, b) in enumerate(PAIRS):
            c.execute("select " + expr.format(a=dec(a), b=dec(b)))
            eq[i] = c.fetchone()[0]
            c.execute(f"truncate {tbl}")
            c.execute(f"insert into {tbl}(city_name) values ({dec(a)})")
            try:
                c.execute(f"insert into {tbl}(city_name) values ({dec(b)})")
                uqres[i] = False
            except psycopg.errors.UniqueViolation:
                uqres[i] = True
            try:
                c.execute(f"select count(*) from {tbl} where city_name LIKE '%'||{dec(a)}||'%'")
                like[i] = c.fetchone()[0]
            except Exception as e:
                like[i] = "ERR:" + type(e).__name__
        r = {"equality": eq, "unique_collision": uqres, "like_contains_first_value": like}
        c.execute(f"truncate {tbl}")
        c.execute(f"insert into {tbl}(city_name) select 'City'||g from generate_series(1,5000) g")
        c.execute(f"analyze {tbl}")
        c.execute("set enable_seqscan=off")
        try:
            c.execute(f"explain select * from {tbl} where city_name = 'city77'")
            plan = " ".join(x[0] for x in c.fetchall())
        except Exception as e:
            plan = "ERR " + type(e).__name__
        r["equality_plan_uses_index"] = "Index" in plan and f"uq_{n}" in plan
        try:
            c.execute(f"explain select * from {tbl} where city_name ILIKE 'city77%'")
            r["ilike_supported"] = True
        except Exception as e:
            r["ilike_supported"] = "ERR:" + type(e).__name__
        c.execute("reset enable_seqscan")
        results[name] = r
    conn.close(); adm.close()
    return info, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pg-db", default="stokit_collation_eval_20261015")
    ap.add_argument("--maria-port", default="3399")
    ap.add_argument("--out", default=str(ROOT / "docs" / "STOKIT_CITY_NAME_COLLATION_EVAL.json"))
    a = ap.parse_args()
    meta, mres, merrs = run_mariadb(a.maria_port)
    info, pres = run_pg(a.pg_db)
    rng = range(len(PAIRS))
    detail = []
    for i, (label, x, y) in enumerate(PAIRS):
        row = {"case": label, "mariadb_equal": mres["equality"].get(i),
               "mariadb_unique_collision": mres["unique_collision"].get(i)}
        for name, r in pres.items():
            row[name] = {"equal": r["equality"][i], "unique_collision": r["unique_collision"][i]}
        detail.append(row)
    summary = {}
    for name, r in pres.items():
        bad = [PAIRS[i][0] for i in rng if r["equality"][i] != mres["equality"].get(i)
               or r["unique_collision"][i] != mres["unique_collision"].get(i)]
        summary[name] = {"cases": len(PAIRS), "mismatches": len(bad), "mismatched_cases": bad,
                         "equality_plan_uses_index": r["equality_plan_uses_index"],
                         "ilike_supported": r["ilike_supported"]}
    out = {"mariadb": meta, "mariadb_forced_error_lines": merrs, "postgres": info, "summary": summary,
           "detail": detail, "mariadb_like_contains": {PAIRS[i][0]: v for i, v in mres["like_contains"].items()}}
    Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"mariadb": meta, "postgres": info, "summary": summary}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
