"""READ-ONLY: can the configured role create a scratch database? Prints role flags and server version only."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.db import connection, transaction  # noqa: E402

with transaction.atomic():
    c = connection.cursor()
    c.execute("SET TRANSACTION READ ONLY")
    c.execute("SELECT rolcreatedb, rolsuper FROM pg_roles WHERE rolname = current_user")
    print("role can create db / is superuser =", c.fetchone())
    c.execute("SHOW server_version")
    print("server_version =", c.fetchone()[0])
    c.execute("SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY 1")
    print("databases on this server =", [r[0] for r in c.fetchall()])
print("Done. Nothing was written.")
