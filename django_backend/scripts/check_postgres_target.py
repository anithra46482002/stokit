import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
from django.conf import settings
from django.db import connection

django.setup()
config = settings.DATABASES["default"]
actual = {
    "ENGINE": config.get("ENGINE"),
    "NAME": config.get("NAME"),
    "HOST": config.get("HOST"),
    "PORT": str(config.get("PORT")),
}
expected = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "stokit_postgres_dev",
    "HOST": "127.0.0.1",
    "PORT": "5432",
}
print("Configured database target:", actual)
if actual != expected:
    raise SystemExit("Refusing to start: configured database target is not the approved PostgreSQL development database.")
connection.ensure_connection()
with connection.cursor() as cursor:
    cursor.execute(
        "SELECT current_database(), current_user, inet_server_addr()::text, "
        "inet_server_port(), current_schema(), "
        "to_regclass(%s)",
        ["public.admin_cart_discount_settings"],
    )
    database, role, address, port, schema, table = cursor.fetchone()
print("Connected database:", database)
print("Connected role:", role)
print("Server address:", address)
print("Server port:", port)
print("Current schema:", schema)
print("Cart Discount table present:", bool(table))
if database != "stokit_postgres_dev" or not table:
    raise SystemExit("Refusing to start: approved database/table verification failed.")


