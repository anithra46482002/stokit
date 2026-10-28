"""Shared order-status semantics for financial aggregates."""

# Normalize stored status strings with lower/trim before comparing these values.
# Revenue is recognized only for successfully completed orders; cancelled, failed,
# placed, pending, and in-progress orders are not revenue.
REVENUE_STATUS_KEYS = ("delivered", "fulfilled")

# Operationally pending means not completed and not cancelled/failed. Keep legacy
# spellings supported because historical rows use both labels and machine keys.
PENDING_STATUS_KEYS = (
    "placed", "pending", "processing", "await_pickup", "awaiting pickup",
    "picked_up", "picked up", "shipped", "out for delivery",
)


def build_order_summary_query(base, where):
    """Build parameterized financial SQL and return its status parameters."""
    revenue_placeholders = ', '.join(['%s'] * len(REVENUE_STATUS_KEYS))
    pending_placeholders = ', '.join(['%s'] * len(PENDING_STATUS_KEYS))
    sql = (
        'SELECT COUNT(*) AS total_orders, '
        f'COALESCE(SUM(CASE WHEN LOWER(TRIM(t.status)) IN ({revenue_placeholders}) THEN CAST(t.total_amount AS DECIMAL(15,2)) ELSE 0 END), 0) AS revenue, '
        f'COALESCE(SUM(CASE WHEN LOWER(TRIM(t.status)) IN ({pending_placeholders}) THEN 1 ELSE 0 END), 0) AS pending_orders '
        'FROM (SELECT DISTINCT c.order_id, c.status, c.total_amount ' + base + where + ') t'
    )
    return sql, [*REVENUE_STATUS_KEYS, *PENDING_STATUS_KEYS]
