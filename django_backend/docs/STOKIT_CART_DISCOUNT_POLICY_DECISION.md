# StokIt Cart Discount Policy — Owner Decision Required

**Date:** 2026-10-16 | **Status:** DECISION PENDING; preserve current behavior

## Current implementations are separate

| Rule | Legacy GET /api/cart_api_test | Admin helper /admin-api/cart-discount-settings |
|---|---|---|
| Threshold | Hard-coded ₹14,000; qualifies at >= 14000 | Configured minimum_subtotal; qualifies only when eligible subtotal > threshold |
| Discount amount | Hard-coded 10% | Configured fixed_discount_amount |
| Threshold base | Undiscounted group total, not already-discounted group | Sum of server-derived lines without recognized product/line discounts |
| VIP | vip_discount='Y' and vip_percentage > 0 suppresses cart promotion; VIP discount calculated separately | vip_applied=True suppresses helper promotion |
| Discounted products | Already-discounted group is excluded from 10% promotion | Excludes has_disc, positive discount_percent, discount_value, product_discount, line_discount, or product_discounted |
| Mixed cart | 10% only on undiscounted group | Fixed amount only against eligible subtotal |
| Rounding | ROUND_HALF_UP to 2 decimals | money() uses ROUND_HALF_UP to 2 decimals |
| Maximum | No separate configured cap; 10% calculated on eligible lines | min(configured amount, eligible subtotal) |

The admin settings are **not wired into** /api/cart_api_test. Combining or switching rules without approval could change customer pricing. No rule was changed for this task.

## Owner must approve

1. Authoritative rule: retain ₹14,000 / 10%, switch to admin fixed amount, or specify a new rule.
2. Threshold base and comparator: total cart vs undiscounted subtotal vs eligible subtotal; >= or >.
3. Discount type: percentage or fixed amount; per order or per line.
4. VIP precedence and exact eligibility; confirm whether VIP excludes cart promotion.
5. Treatment of any product/line discount, including has_disc with zero percentage/value.
6. Mixed-cart threshold and eligible lines.
7. Rounding method and line/order rounding points.
8. Maximum/cap, including whether a fixed discount can exceed eligible subtotal (recommended: never).
9. Missing/disabled admin-setting fallback and approved integration point.

## Approval record required

Record owner name/role, date, selected policy, threshold/base/comparator, amount semantics, VIP rules, discounted-product/mixed-cart rules, rounding, cap, and fallback. Then execute STOKIT_CART_DISCOUNT_INTEGRATION_TEST_PLAN.md only against an approved isolated test environment. This document authorizes no live DB writes, DDL, migrations, imports, restores, account creation, or cleanup.