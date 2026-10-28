"""READ-ONLY verification of stokit_postgres_dev (READ ONLY transaction; no DDL/DML). Credentials never printed."""
import json
from pathlib import Path
import psycopg

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = ["users1", "zg_api_keys", "zg_banner", "zg_brands", "zg_cod", "zg_headings", "zg_headings_new", "zg_logo",
            "zg_product_warehouse", "zg_reels", "zg_social_media", "zg_target_activity_log", "zg_testy", "zg_vari_product",
            "zg_vari_product_images", "zg_vari_variant"]
env = {}
for line in (ROOT / ".env.postgres").read_text().splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip().strip("\"'")
conn = psycopg.connect(host=env["DB_HOST"], port=env["DB_PORT"], user=env["DB_USER"], password=env["DB_PASSWORD"],
                       dbname="stokit_postgres_dev")
conn.read_only = True
c = conn.cursor()
c.execute("select current_database(), current_setting('server_version'), current_schema()")
print("identity:", c.fetchone())
c.execute("select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1")
tables = [r[0] for r in c.fetchall()]
print("public base tables:", len(tables))
print("excluded present:", [t for t in EXCLUDED if t in tables])
inv = json.loads((ROOT / "docs" / "STOKIT_COMPLETE_POSTGRESQL_SCHEMA_INVENTORY.json").read_text(encoding="utf-8-sig"))
text = json.dumps(inv)
print("tables not mentioned in inventory JSON:", [t for t in tables if f'"{t}"' not in text])
nonempty = {}
for t in tables:
    c.execute(f'select count(*) from "{t}"')
    n = c.fetchone()[0]
    if n:
        nonempty[t] = n
print("non-empty tables:", nonempty)
c.execute("select count(*) from admins"); print("admins rows:", c.fetchone()[0])
c.execute("select count(*) from admin_cart_discount_settings"); print("admin_cart_discount_settings rows:", c.fetchone()[0])
c.execute("select app, name from django_migrations order by id")
rows = c.fetchall()
print("django_migrations:", len(rows), "first:", rows[0])
c.execute("select count(*) from pg_trigger t join pg_class r on r.oid=t.tgrelid join pg_namespace n on n.oid=r.relnamespace "
          "where n.nspname='public' and not t.tgisinternal")
print("user triggers:", c.fetchone()[0])
c.execute("select count(*) from pg_indexes where schemaname='public'"); print("indexes:", c.fetchone()[0])
c.execute("select count(*) from pg_collation where collname in ('ci_ai','ci_as')"); print("eval collations in target:", c.fetchone()[0])
c.execute("select exists(select 1 from pg_extension where extname in ('citext','unaccent'))"); print("citext/unaccent installed in target:", c.fetchone()[0])
c.execute("select datname from pg_database where datname like 'stokit%' order by 1")
print("stokit databases on server:", [r[0] for r in c.fetchall()])
conn.rollback()
