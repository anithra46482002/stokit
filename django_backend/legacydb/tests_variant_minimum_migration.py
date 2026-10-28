"""Database-free checks for migration 0004 (zg_variant.minimum_buying_count) and the Variant model mapping."""
import importlib

from django.db import migrations
from django.test import SimpleTestCase

from legacydb.models import Variant

migration_module = importlib.import_module('legacydb.migrations.0004_variant_minimum_buying_count')


class VariantMinimumBuyingCountMigrationTests(SimpleTestCase):
    def test_migration_is_narrow_and_depends_on_the_latest_legacydb_migration(self):
        migration = migration_module.Migration
        self.assertEqual(migration.dependencies, [('legacydb', '0003_advancepaytransaction')])
        self.assertEqual(len(migration.operations), 1)
        self.assertIsInstance(migration.operations[0], migrations.SeparateDatabaseAndState)

    def test_forward_sql_adds_a_not_null_default_one_column_with_a_check_and_nothing_else(self):
        sql = migration_module.ADD_COLUMN_SQL
        self.assertIn('ALTER TABLE zg_variant', sql)
        self.assertIn('ADD COLUMN IF NOT EXISTS minimum_buying_count integer NOT NULL DEFAULT 1', sql)
        self.assertIn('CHECK (minimum_buying_count >= 1)', sql)
        for forbidden in ('DROP', 'DELETE', 'TRUNCATE', 'UPDATE', 'RENAME', 'zg_product', 'quantity'):
            self.assertNotIn(forbidden, sql)

    def test_reverse_sql_removes_only_the_new_constraint_and_column(self):
        sql = migration_module.DROP_COLUMN_SQL
        self.assertIn('DROP CONSTRAINT IF EXISTS ck_zg_variant_minimum_buying_count', sql)
        self.assertIn('DROP COLUMN IF EXISTS minimum_buying_count', sql)
        self.assertNotIn('DROP TABLE', sql)

    def test_model_maps_the_new_column_without_letting_django_manage_the_legacy_table(self):
        field = Variant._meta.get_field('minimum_buying_count')
        self.assertEqual(field.get_internal_type(), 'IntegerField')
        self.assertEqual(field.default, 1)
        self.assertFalse(field.null)
        self.assertFalse(Variant._meta.managed)
        self.assertEqual(Variant._meta.db_table, 'zg_variant')

    def test_stock_quantity_column_is_unchanged(self):
        quantity = Variant._meta.get_field('quantity')
        self.assertEqual(quantity.default, 0)
        self.assertNotEqual(quantity.name, 'minimum_buying_count')
