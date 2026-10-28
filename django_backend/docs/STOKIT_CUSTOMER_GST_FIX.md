# StokIt — Customer GST percentage fix (cart, checkout, order placement)

Date: 2026-10-27. Scope: `django_backend` only. No Flutter, PHP, frontend, schema, migration or data changes.

## The rule (single shared implementation: `legacydb/gst_rules.py`)

```
line_gst  = configured_gst_amount_per_unit x quantity x customer_gst_percentage / 100
total_gst = sum(line_gst for every eligible cart line)      # each line rounded once, half-up, to 2 decimals
```

* **Customer percentage** = the authenticated customer's saved `users.gst_percentage` (the field Customer Management
  writes via `adminapi/crud.py`, validated finite and 0-100). It is read from the database; request payloads are ignored.
* **Configured amount** = `zg_variant.gst_price` for a variant line; `zg_product.gst_price` for a product without
  variants (variant id 0).
* **The selling price is not an input.** `calculate_gst_amount` has no price parameter.
* **Eligibility:** product `gst_applicable` must be `Y`; a variant line also needs `zg_variant.gst = 'Y'`. Product `N`
  always wins. Missing/blank/other flags are `N`. A configured amount alone never enables GST.
* **Zero/blank/NULL customer percentage -> GST is exactly 0.** No existing documented rule or test defined a fallback,
  so none is assumed.
* **Invalid customer percentage** (negative, NaN/Infinity, unparseable, >100) -> GST is 0. A negative configured amount -> 0.
* **Product-level `zg_product.gst_percentage` is no longer used** by any calculation (the column and admin field remain).

Worked example, customer 5%: variants with configured amounts 120 / 135 / 145 -> 6.00 / 6.75 / 7.25 -> **20.00**.

## Where it is applied

| Path | File |
|---|---|
| Cart (`cart_api_test`) | `legacy_api/views_commerce.py` |
| Checkout preview (`checkout`) | `legacy_api/views_commerce.py` |
| Order placement + snapshot (`order_post`) | `legacy_api/views_orders.py`, `legacydb/order_gst_snapshot.py` |
| Order details, statements, admin order page | stored snapshot when the snapshot columns exist; otherwise the same shared rule with the customer's current percentage (pre-migration only) |

Order snapshot (when the approved columns exist): `gst_percentage` = customer percentage used, `gst_unit_amount` =
configured per-unit amount used, `gst_amount` = calculated line GST. Historical GST never changes afterwards; orders
without a snapshot keep reporting `gst_source = "legacy_unrecorded"`.

## Compatibility notes

* All Flutter endpoint paths and response keys are unchanged (`GST`, `gst_amount`, `total_with_gst`, `pricing.*`, ...).
* `pricing.gst_percentage` (order details / statements) is still the derived ratio GST / subtotal; the customer's
  rate is exposed as `customer_billed_percentage`.
* Product detail `GST_price` still shows the admin-configured per-unit amount (zero when GST is disabled).
* The customer's separate `users.gst` Y/N flag is not used as a gate.

## Known limitation / follow-up

The admin product screen still shows a product-level GST percentage that no longer affects GST. Hiding it is a
frontend change and was not made.
