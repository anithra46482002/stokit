"""READ-ONLY: server/database clocks and ledger sequence health. Nothing is written."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from django.db import connection, transaction  # noqa: E402

print("django TIME_ZONE =", settings.TIME_ZONE, "| USE_TZ =", settings.USE_TZ)
with transaction.atomic():
    c = connection.cursor()
    c.execute("SET TRANSACTION READ ONLY")
    c.execute("SELECT NOW(), current_setting('TimeZone')")
    print("PG now / session TimeZone =", c.fetchone())
    c.execute("SELECT last_value, is_called FROM advance_pay_transactions_id_seq")
    print("ledger id sequence (last_value, is_called) =", c.fetchone())
    c.execute("SELECT COUNT(*), MAX(id) FROM advance_pay_transactions")
    print("ledger rows, max id =", c.fetchone())
    c.execute("SELECT created_at, updated_at FROM advance_pay_allocations WHERE id=4")
    print("allocation 4 created/updated =", c.fetchone())
    c.execute("SELECT MAX(order_date) FROM zg_checkout")
    print("latest order_date in zg_checkout =", c.fetchone())
print("Done. Nothing was written.")
