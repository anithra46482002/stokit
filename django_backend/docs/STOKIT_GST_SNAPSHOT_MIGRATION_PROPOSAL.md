# GST order-snapshot migration — PROPOSAL (NOT APPLIED)

Status: code is in place and inert; the migration is **not applied** and no DDL or backfill has been run.
Database engine confirmed: PostgreSQL (`stokit_postgres_dev` for development).

## Findings
- `zg_order_items` currently has: item_id, order_id, product_id, variant_id, product_name, variant_name, quantity, price,
  discount, total_price. **No GST field exists.** `zg_checkout` has none either, and there are no invoice/tax/payment tables.
- In all 5 dev orders, `zg_checkout.total_amount` equals the sum of `zg_order_items.total_price` (GST-exclusive), so original
  GST cannot be derived by subtraction.
- Before this change, order details, credit-release statements and the admin order page recomputed old-order GST from
  *today's* product/variant settings (so editing a product changed old orders).

## Proposed schema change (all nullable, metadata-only on PostgreSQL)
`zg_order_items` gains `gst_applicable char(1)`, `gst_percentage numeric(5,2)`, `gst_unit_amount numeric(10,2)`,
`gst_amount numeric(10,2)` (line total), `gst_snapshot_at timestamp`, plus two CHECK constraints.
File: `django_backend/legacydb/pending_migrations/0005_order_item_gst_snapshot.py.pending` (RunSQL, with reverse SQL).
The unmanaged `OrderItem` model is intentionally not edited until approval.

## Code (already written, inert until the columns exist)
- `legacydb/order_gst_snapshot.py`: `snapshot_available()` checks `information_schema` (positive result cached).
- `order_post` stores the snapshot per line, computed by `gst_rules` from persisted settings (client values never read).
- `order_details`, `_credit_release_report` and the admin order detail read the stored snapshot only, and report
  `gst_source` = `snapshot` | `legacy_unrecorded` | `partial_snapshot` | `current_settings_pre_snapshot`.
- Before the migration, behaviour is exactly as before (`current_settings_pre_snapshot`); the INSERT is unchanged.

## Expected impact on existing orders
No rows are rewritten. After migration, existing orders have NULL snapshots. Their totals, payments and
`zg_checkout.total_amount` are untouched. Display changes for them (see policy below).

## Backfill strategy
- Reliably reconstructable: **none** in the current data. Original rates/amounts were never recorded, and current product
  settings are not historical evidence (can't distinguish "was never taxed" from "settings edited since").
- Not reconstructable: all 5 dev orders (and any production order predating the migration).
- Proposed legacy-data policy **(needs your decision)**: leave snapshots NULL; display GST for these orders as 0 with
  `gst_source = "legacy_unrecorded"` so it is flagged, not silent and not invented. Alternatives: (B) keep current-settings
  recomputation for legacy orders only, labelled as an estimate; (C) if the business can supply authoritative historical
  GST for specific orders (invoices/PHP records), load those via a reviewed one-off script.
- Production orders must be reviewed separately; this inspection covered only the dev database.

## Deployment order
1. Approve policy and migration. 2. Deploy code (safe before the migration). 3. Take a backup/snapshot.
4. Apply migration (`manage.py sqlmigrate legacydb 0005`, then `migrate legacydb`). 5. Place a test order and confirm the
snapshot row. Orders created between steps 2 and 4 are legacy (NULL).
## Rollback
`migrate legacydb 0004` runs the reverse SQL and drops the five columns (loses snapshots written since). Code keeps working
after rollback because it re-checks `snapshot_available()` (restart the process to clear the cached positive result).
