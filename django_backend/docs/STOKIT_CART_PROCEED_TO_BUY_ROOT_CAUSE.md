# StokIt Cart Proceed to Buy — Root Cause and Fix Report

## Confirmed root cause

Flutter file: `lib/features/cart/presentation/cart_page.dart`, `_CheckoutBar`. The old enablement condition compared `finalTotalPrice >= mok`. `finalTotalPrice` is the payable amount after credit. When credit covered the cart, payable was ₹0.00, so the button was disabled even when the pre-credit order total exceeded the minimum.

Backend file: `django_backend/legacy_api/views_commerce.py`, `_build_cart_response`. The cart response already computed `order_total_before_credit`, but did not expose it as a dedicated field. The MOK threshold was a legacy hardcoded value of 100, while `mov.min_order_value` of 14000 is a separate cart-discount promotion threshold.

## Changes made

- Added `STOKIT_MIN_ORDER_VALUE` and `STOKIT_MONTHLY_CREDIT_RELEASE` environment-backed Django settings. Defaults preserve the existing legacy values (₹100 and ₹3,000); `.env.postgres.example` documents both. No actual secret-bearing `.env` file was changed.
- The cart API now exposes `order_total_before_credit`, `available_credit`, `carried_forward_from_previous_month`, and `carry_forward_to_next_month`. It calculates current available credit using the existing finance report's historical closing carry-forward plus the configured monthly release instead of assuming the cart always has exactly ₹3,000 available.
- The finance report and cart API share `_credit_release_report` logic, keeping historical carry-forward calculation aligned with `/api/crd_rel`.
- Flutter enables the button based on pre-credit order total versus MOK, not payable amount. The minimum message uses the pre-credit total. The summary displays previous carry-forward credit and remaining carry-forward credit separately.
- Flutter blocks checkout when delivery details cannot be verified, the phone/address is missing, or an item is marked out of stock. The repository surfaces safe backend 4xx messages; other failures receive a generic message.
- Django `/order_post` validates delivery address/phone, empty carts, missing products/variants, variant stock, and the pre-credit minimum before writing order records. Monetary calculations in this handler use `Decimal`; writes remain inside the existing transaction. A failed validation does not create an order or clear the cart.
- Existing `/order_post` route, request shape, and success response keys are retained. No migrations, SQL dump imports, Flutter API contract changes, or manual live-order tests were performed.

## Verification

- Django full test suite: **340 passed**.
- `python manage.py check`: passed with no issues.
- Flutter focused eligibility tests: **4 passed**.
- Dart analyzer on the four changed Flutter source/test files: **no issues found**.
- Full `flutter test`: still fails in the pre-existing `test/widget_test.dart` counter smoke test because `StokoApp` throws `GetIt: HomeBloc is not registered`; that test is unrelated to the cart changes.
- Full `flutter analyze` exceeded the 240-second tool timeout. Device-level checkout and live PostgreSQL/ngrok verification remain outstanding.

## Important limitation

The existing finance report's business formula (including its historical order calculations and VIP treatment) was reused rather than redesigned. The cart credit balance is derived from that report; this change does not introduce a separate persisted credit ledger or alter the legacy order-total storage semantics. Confirm the finance formula with the business owner before changing it further. The `mov.min_order_value` of ₹14,000 remains a separate legacy promotion threshold, not the checkout MOK rule.