import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'scripts' / 'stokit_pg_migration.py'
spec = importlib.util.spec_from_file_location('stokit_pg_migration', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class MigrationGuardTests(unittest.TestCase):
    def test_expected_database_names_and_engines_pass(self):
        module.validate('stokit_legacy_test', 'django.db.backends.mysql', 'stokit_postgres_dev', 'django.db.backends.postgresql')

    def test_unexpected_source_is_refused(self):
        with self.assertRaises(ValueError):
            module.validate('production', 'mysql', 'stokit_postgres_dev', 'postgresql')

    def test_unexpected_target_is_refused(self):
        with self.assertRaises(ValueError):
            module.validate('stokit_legacy_test', 'mysql', 'postgres', 'postgresql')

    def test_wrong_engines_are_refused(self):
        with self.assertRaises(ValueError):
            module.validate('stokit_legacy_test', 'sqlite', 'stokit_postgres_dev', 'postgresql')
        with self.assertRaises(ValueError):
            module.validate('stokit_legacy_test', 'mysql', 'stokit_postgres_dev', 'sqlite')

    def test_same_database_is_refused(self):
        with self.assertRaises(ValueError):
            module.validate('stokit_legacy_test', 'mysql', 'stokit_legacy_test', 'postgresql')
    def test_insert_tuple_parser_handles_parentheses_semicolons_and_doubled_quotes(self):
        sql = "INSERT INTO `t` (`id`, `note`) VALUES (1, 'a; (b)'), (2, 'it''s (ok);');"
        self.assertEqual(module.parse_insert_tuple_count(sql), 2)

    def test_insert_tuple_parser_handles_backslash_escapes(self):
        sql = r"INSERT INTO t (id, note) VALUES (1, 'escaped \' quote; (x)'), (2, 'slash \\ and parens ()');"
        self.assertEqual(module.parse_insert_tuple_count(sql), 2)

    def test_insert_tuple_parser_handles_multiple_statements(self):
        sql = "INSERT INTO t VALUES (1, 'semi;colon'); INSERT INTO t VALUES (2), (3);"
        self.assertEqual(module.parse_insert_tuple_count(sql), 1)

    def test_fingerprint_is_deterministic_and_type_aware(self):
        from datetime import datetime
        from decimal import Decimal
        cols = ['id', 'amount', 'when', 'optional']
        values = [7, Decimal('1.00'), datetime(2026, 10, 15, 9, 30), None]
        first = module.canonical_row_fingerprint(cols, values)
        self.assertEqual(first, module.canonical_row_fingerprint(cols, values))
        self.assertNotEqual(first, module.canonical_row_fingerprint(cols, [7, Decimal('1.0'), datetime(2026, 10, 15, 9, 30), None]))
        self.assertNotEqual(module.canonical_row_fingerprint(['x'], [None]), module.canonical_row_fingerprint(['x'], ['']))

    def test_fingerprint_is_column_order_sensitive(self):
        self.assertNotEqual(module.canonical_row_fingerprint(['a', 'b'], [1, 'x']), module.canonical_row_fingerprint(['b', 'a'], ['x', 1]))

    def test_insert_tuple_parser_handles_no_values(self):
        self.assertEqual(module.parse_insert_tuple_count("INSERT INTO t SELECT * FROM other;"), 0)

    def test_schema_difference_report_is_metadata_only(self):
        source = [{"name": "id", "type": "int", "nullable": "NO", "default": None}]
        target = [{"name": "id", "type": "bigint", "nullable": "NO", "default": None}, {"name": "extra", "type": "text", "nullable": "YES", "default": None}]
        diff = module.compare_column_definitions(source, target)
        by_column = {item["column"]: item for item in diff}
        self.assertEqual(by_column["id"]["kind"], "definition_mismatch")
        self.assertEqual(by_column["extra"]["kind"], "target_only")

    def test_dependency_order_respects_prerequisites(self):
        order = module.dependency_order({"orders": {"users"}, "users": set(), "products": set()})
        self.assertLess(order.index("users"), order.index("orders"))

    def test_dependency_order_rejects_cycles(self):
        with self.assertRaises(ValueError):
            module.dependency_order({"a": {"b"}, "b": {"a"}})

    def test_duplicate_classification_is_read_only(self):
        row = {"id": 1, "name": "safe"}
        self.assertEqual(module.classify_duplicate(row, dict(row), ["id"]), "identical_duplicate")
        self.assertEqual(module.classify_duplicate(row, {"id": 1, "name": "changed"}, ["id"]), "conflicting_duplicate")
        self.assertEqual(module.classify_duplicate(row, {"id": 2, "name": "safe"}, ["id"]), "different_key")

    def test_execute_requires_confirmation_and_remains_disabled(self):
        import contextlib
        import io
        from unittest.mock import patch
        with patch("sys.argv", ["stokit_pg_migration.py", "--execute"]):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(module.main(), 2)
        with patch("sys.argv", ["stokit_pg_migration.py", "--execute", "--confirm", module.CONFIRM]):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(module.main(), 3)

    def test_import_remains_disabled_even_after_operator_phrase(self):
        self.assertFalse(module.execution_is_implemented())

if __name__ == '__main__':
    unittest.main()
