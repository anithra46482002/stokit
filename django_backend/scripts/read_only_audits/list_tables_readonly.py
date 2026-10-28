"""READ-ONLY: connect to stokit_postgres_dev and list public tables with column and row counts."""
from pathlib import Path
import psycopg

ROOT = Path(__file__).resolve().parents[2]
env = {}
for line in (ROOT / ".env.postgres").read_text().splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip().strip("\"'")
conn = psycopg.connect(host=env["DB_HOST"], port=env["DB_PORT"], user=env["DB_USER"], password=env["DB_PASSWORD"],
                       dbname="stokit_postgres_dev")
conn.read_only = True
cur = conn.cursor()
cur.execute("select current_database(), current_setting('server_version')")
print("connected:", cur.fetchone())
cur.execute("""select t.table_name, (select count(*) from information_schema.columns k
               where k.table_schema='public' and k.table_name=t.table_name)
               from information_schema.tables t where t.table_schema='public' and t.table_type='BASE TABLE' order by 1""")
rows = cur.fetchall()
print("table count:", len(rows))
for i, (name, ncols) in enumerate(rows, 1):
    cur.execute(f'select count(*) from "{name}"')
    print(f"{i:2d}. {name:<32} cols={ncols:<3} rows={cur.fetchone()[0]}")
cur.execute("select count(*) from pg_constraint c join pg_namespace n on n.oid=c.connamespace where n.nspname='public' and c.contype='f'")
print("foreign keys:", cur.fetchone()[0])
cur.execute("select count(*) from pg_indexes where schemaname='public'")
print("indexes:", cur.fetchone()[0])
cur.execute("select count(*) from pg_trigger t join pg_class r on r.oid=t.tgrelid join pg_namespace n on n.oid=r.relnamespace where n.nspname='public' and not t.tgisinternal")
print("triggers:", cur.fetchone()[0])
conn.rollback()
