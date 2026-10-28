"""Add zg_variant.minimum_buying_count (minimum purchase quantity per variant).

zg_variant is an unmanaged legacy table, so Django's AddField would change only migration
state. The real column is added with explicit SQL, wrapped in SeparateDatabaseAndState so the
model state and the database stay in step. The change is additive and idempotent:
existing rows receive the default 1 and no other column or table is touched.
"""
from django.db import migrations, models

ADD_COLUMN_SQL = """
ALTER TABLE zg_variant
    ADD COLUMN IF NOT EXISTS minimum_buying_count integer NOT NULL DEFAULT 1;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_zg_variant_minimum_buying_count'
          AND conrelid = 'zg_variant'::regclass
    ) THEN
        ALTER TABLE zg_variant
            ADD CONSTRAINT ck_zg_variant_minimum_buying_count CHECK (minimum_buying_count >= 1);
    END IF;
END
$$;
"""

DROP_COLUMN_SQL = """
ALTER TABLE zg_variant DROP CONSTRAINT IF EXISTS ck_zg_variant_minimum_buying_count;
ALTER TABLE zg_variant DROP COLUMN IF EXISTS minimum_buying_count;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('legacydb', '0003_advancepaytransaction'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='variant',
                    name='minimum_buying_count',
                    field=models.IntegerField(default=1),
                ),
            ],
            database_operations=[
                migrations.RunSQL(sql=ADD_COLUMN_SQL, reverse_sql=DROP_COLUMN_SQL),
            ],
        ),
    ]
