"""Database-FREE tests for PostgreSQL SQL compatibility.

1. A static scan fails if MySQL-only SQL syntax returns to application code.
2. Real view functions run with the SQL helper layer replaced by test doubles, proving the exact SQL
   and parameter order that would be sent to PostgreSQL. They do NOT prove behaviour against a
   real PostgreSQL database (no connection is made)."""
import json
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase

from adminapi import order_pages
from legacy_api import views_catalog, views_commerce

USER = {"id": 7, "username": "contract-user", "email": "c@example.invalid"}
AUTH = {"HTTP_AUTHORIZATION": "Bearer " + "a" * 64}
SCANNED_DIRS = ("adminapi", "legacy_api", "accounts", "legacydb", "config")

BANNED = [
    (r"\bCURDATE\s*\(", "CURDATE() (use CURRENT_DATE)"),
    (r"\bCURTIME\s*\(", "CURTIME()"),
    (r"\bDATE_FORMAT\s*\(", "DATE_FORMAT() (use to_char)"),
    (r"\bIFNULL\s*\(", "IFNULL() (use COALESCE)"),
    (r"\bGROUP_CONCAT\s*\(", "GROUP_CONCAT()"),
    (r"\bSTR_TO_DATE\s*\(", "STR_TO_DATE()"),
    (r"\b(UNIX_TIMESTAMP|FROM_UNIXTIME|DATEDIFF|TIMESTAMPDIFF)\s*\(", "MySQL date function"),
    (r"ON\s+DUPLICATE\s+KEY", "ON DUPLICATE KEY (use ON CONFLICT)"),
    (r"\bINSERT\s+IGNORE\b", "INSERT IGNORE"),
    (r"\bREPLACE\s+INTO\b", "REPLACE INTO"),
    (r"\bLIMIT\s+%s\s*,\s*%s", "LIMIT offset, count (use LIMIT n OFFSET m)"),
    (r"\.lastrowid\b", "cursor.lastrowid (use RETURNING)"),
    (r"\b(?:SELECT|INSERT|UPDATE|DELETE|FROM|JOIN|WHERE)\b.*`\w+`", "backtick-quoted identifier in SQL"),
    (r"INTERVAL\s+\d+\s+(DAY|HOUR|MINUTE|SECOND|MONTH|YEAR)\b", "MySQL INTERVAL syntax"),
    (r"\bis_read\s*=\s*[01]\b", "boolean column compared with an integer"),
    (r"\bhighlight\s*=\s*[01]\b", "boolean column compared with an integer"),
    (r"\b(view|main)\s*=\s*[01]\b", "text column compared with an integer"),
    (r"\bLIKE\s+%s", "case-sensitive LIKE (use ILIKE to keep case-insensitive search)"),
    (r"\b(?:INSERT\s+INTO|UPDATE|SELECT)\b.*\(\s*user\s*,", "unquoted reserved word user in SQL column list (quote it)"),
]


def application_sources():
    base = Path(settings.BASE_DIR)
    for directory in SCANNED_DIRS:
        for path in sorted((base / directory).rglob("*.py")):
            name = path.name
            if "migrations" in path.parts or name.startswith("tests") or name == "mariadb_integration.py":
                continue
            yield path, path.read_text(encoding="utf-8-sig")


class MySqlOnlySyntaxScanTests(SimpleTestCase):
    def test_application_code_contains_no_mysql_only_sql(self):
        findings = []
        for path, text in application_sources():
            for number, line in enumerate(text.splitlines(), start=1):
                stripped = line.lstrip()
                # Do not flag Python comments/docstrings for SQL tokens like backticks.
                if stripped.startswith(("#", '\"\"\"', "'''")):
                    continue
                for pattern, label in BANNED:
                    if re.search(pattern, line, re.IGNORECASE):
                        findings.append(f"{path.name}:{number}: {label}")
        self.assertEqual(findings, [], "MySQL-only SQL found:\\n" + "\\n".join(findings))

    def test_postgresql_replacements_are_present(self):
        orders = (Path(settings.BASE_DIR) / "legacy_api" / "views_orders.py").read_text(encoding="utf-8")
        self.assertIn("to_char(changed_at, 'Mon DD, YYYY')", orders)
        self.assertIn("FOR UPDATE OF c", orders)  # PostgreSQL cannot lock the nullable side of an outer join


class OrderDateFilterTests(SimpleTestCase):
    def test_default_today_filter_uses_postgresql_date_arithmetic(self):
        where, args = order_pages._filters({}, default_today=True)
        self.assertIn("CURRENT_DATE", where)
        self.assertIn('c.order_date < CURRENT_DATE + INTERVAL ' + chr(39) + '1 day' + chr(39), where)
        self.assertEqual(args, [])


class CatalogSqlTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_product_detail_display_uses_full_configured_amount_when_customer_rate_is_blank(self):
        self.assertEqual(views_catalog._display_gst_percentage(None, "Y"), "100")
        self.assertEqual(views_catalog._display_gst_percentage("", "Y"), "100")
        self.assertEqual(views_catalog._display_gst_percentage("   ", "Y"), "100")

    def test_product_detail_display_uses_saved_customer_rate_and_falls_back_when_zero(self):
        self.assertEqual(views_catalog._display_gst_percentage("5", "Y"), "5")
        self.assertEqual(views_catalog._display_gst_percentage("18", "Y"), "18")
        self.assertEqual(views_catalog._display_gst_percentage("0", "Y"), "100")
        self.assertEqual(views_catalog._display_gst_percentage("invalid", "Y"), "0")
    def test_product_gst_disabled_always_displays_zero_rate(self):
        for flag in ("N", None, "", "invalid"):
            self.assertEqual(views_catalog._display_gst_percentage(None, flag), "0")
        request = self.rf.get("/api/banner?skip=5&limit=7")
        with mock.patch.object(views_catalog, "fetchone", return_value={"total": 3}), \
                mock.patch.object(views_catalog, "fetchall", return_value=[]) as fetchall:
            response = views_catalog.banner(request)
        self.assertEqual(response.status_code, 200)
        sql, params = fetchall.call_args[0]
        self.assertIn("LIMIT %s OFFSET %s", sql)
        self.assertEqual(params, [7, 5])
        body = json.loads(response.content)
        self.assertEqual((body["skip"], body["limit"], body["total"]), (5, 7, 3))

    def test_category_view_insert_quotes_reserved_user_column(self):
        request = self.rf.post("/api/product-api", data=json.dumps({"product_id": 5}),
                               content_type="application/json", **AUTH)
        with mock.patch("accounts.services.authenticate_token", return_value=(object(), USER)), \
                mock.patch.object(views_catalog, "fetchone", side_effect=[None, None]), \
                mock.patch.object(views_catalog, "execute", return_value=1) as execute:
            response = views_catalog.product_api(request)
        self.assertEqual(response.status_code, 404)
        sql, params = execute.call_args[0]
        self.assertIn('("user", category_id)', sql)
        self.assertEqual(params, ["contract-user", 0])


class NotificationSqlTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def _auth(self):
        return mock.patch("accounts.services.authenticate_token", return_value=(object(), USER))

    def test_mark_read_uses_boolean_literal(self):
        request = self.rf.put("/api/noti_list?action=mark_read", data=json.dumps({"notification_id": 3}),
                              content_type="application/json", **AUTH)
        with self._auth(), \
                mock.patch.object(views_commerce, "fetchone", return_value={"id": 7}), \
                mock.patch.object(views_commerce, "execute", return_value=1) as execute:
            response = views_commerce.noti_list(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("is_read=TRUE", execute.call_args[0][0])

    def test_list_filters_with_boolean_and_keeps_the_response_contract(self):
        request = self.rf.get("/api/noti_list?filter_read=1", **AUTH)
        row = {"id": 1, "heading": "h", "message": "m", "is_read": True, "created_at": "2026-01-01 00:00:00",
               "recipient_type": "ALL", "sent_by": "admin"}
        with self._auth(), \
                mock.patch.object(views_commerce, "fetchone",
                                  side_effect=[{"id": 7}, {"total": 1}, {"read_count": 1, "unread_count": 0}]), \
                mock.patch.object(views_commerce, "fetchall", return_value=[row]) as fetchall:
            response = views_commerce.noti_list(request)
        sql, params = fetchall.call_args[0]
        self.assertIn("is_read=%s", sql)
        self.assertEqual(params, [7, True, 30, 0])
        body = json.loads(response.content)
        self.assertIs(body["notifications"][0]["is_read"], True)
        self.assertEqual((body["read"], body["unread"], body["total"]), (1, 0, 1))
