# StokIt Manage Allocations — Implementation Review

Date: 2026-10-22
Status: PARTIAL — implementation is present for review; financial calculation rules are not yet approved.

## Existing schema reused

The Django `legacydb` app already maps `advance_pay_allocations`, `advance_pay_offers`, and `advance_pay_transactions` with `managed = False`. The React admin already has authenticated API access through `src/api.js` and an existing `advance-allocations` resource. This implementation adds a dedicated Manage Allocations page and separate `/admin-api/allocations` routes while preserving the old endpoint.

No model or database schema was changed. No migration was generated or applied. No SQL dump was imported. PHP and Flutter source were not modified.

## Added API surface

- `GET /admin-api/allocations?page=1&page_size=20&offer_id=<id>&user=<text>&month=YYYY-MM&as_of_date=YYYY-MM-DD` — authenticated, paginated list and server-side ledger calculations.
- `GET /admin-api/allocations/<id>` — authenticated allocation detail.
- `POST /admin-api/allocations` — creates an allocation from an active offer and existing customer.
- `PATCH /admin-api/allocations/<id>` — edits status, payment reference and notes. Dates are editable only before ledger transactions exist. Offer/user/credit amounts are immutable in this endpoint to protect financial history.
- `DELETE /admin-api/allocations/<id>` — soft-cancels the allocation by setting `CANCELLED`; does not delete transaction history.
- Offers and customer options are loaded through existing `advance-payments` and `customers` APIs.

All endpoints use the existing `BaseAdminResource` permission class and `advance_payments` resource permission.

## Calculation behavior and known gaps

- Money uses Python `Decimal` with two-place rounding.
- Monthly release amounts are found using the existing `MONTHLY_RELEASE:YYYY-MM` notes marker, rather than the time of the order that triggered release.
- Carry-forward is derived from recorded `CREDIT_ADDED` less `CREDIT_USED` transactions before the reporting month, floored at zero.
- Used this month is gross `CREDIT_USED` ledger amount in the reporting month.
- Available now uses the persisted `remaining_credit` balance only while the allocation is `ACTIVE` and within its start/end dates.
- Future monthly bonus is a provisional estimate from payment amount, bonus percentage, duration and reporting date.

**Not approved as a financial statement:** the current codebase does not define a documented refund transaction type or a complete rule for separating principal credit from monthly bonus release. Therefore “used this month” is not refund-adjusted, and total-credit/future-release reconciliation requires product-owner confirmation. Do not claim refund-adjusted calculations are verified until refund storage and attribution rules are established.

## Safety

- The new delete operation is a soft cancellation and preserves all `advance_pay_transactions` rows. Cancelled and completed allocations cannot be reactivated, and creating a second active allocation for the same customer is rejected.
- Financial identity fields and balance values cannot be edited through the new PATCH endpoint; an audited adjustment flow is required for those changes.
- No schema changes or migrations are required for the current implementation.
- Existing Flutter contracts and PHP files remain out of scope and must not be changed.

## Verification still required

Run backend system checks, isolated unit/API tests, frontend lint and production build, and authenticated API tests against the configured PostgreSQL development server. Browser verification is only complete after an authenticated session exercises filtering, create, edit and cancel without console/network errors. Until the refund and future-credit rules are confirmed and those checks pass, overall status remains PARTIAL.

## Verification record (2026-10-22)

- `python manage.py check`: PASS, no issues.
- `python manage.py test adminapi.tests_allocation_management accounts.tests_roles`: PASS, 14 tests (including mocked create, edit and soft-cancel behavior).
- Frontend `npm test`: PASS, 33 tests.
- Frontend `npm run lint`: PASS, 0 warnings and 0 errors.
- Frontend `npm run build`: PASS.
- Local frontend root: HTTP 200.
- Live unauthenticated requests to `/admin-api/allocations` and `/admin-api/advance-payments`: HTTP 401, confirming the API routes require authentication.
- Authenticated in-process APIClient verification with a SUPER_ADMIN test principal against the configured development database: list returned HTTP 200 with pagination and `as_of_date`; detail returned HTTP 200 for the returned allocation ID; offers and customers returned HTTP 200; invalid POST/PATCH/DELETE payloads returned HTTP 400. The in-process principal bypasses token issuance and is not proof of a real browser-token session.
- Browser automation: BLOCKED. Cody's browser command reports `playwright-cli not found on PATH`; no authenticated browser UI workflow or browser console/network inspection was performed.
- No migrations were generated or applied; no schema changes or data writes were performed by verification.

## Remaining blockers before declaring DONE

1. Confirm the official meaning of `total_credit` (the existing offer and allocation code stores a duration-based total, while the example description can be read as payment plus one bonus amount).
2. Define refund transaction types and reporting-period attribution so usage can be calculated net of refunds.
3. Confirm whether future monthly bonuses count toward `total_remaining` and the exact mobile-cart availability rule.
4. Complete a real authenticated browser session test for list/filter/create/edit/cancel and inspect console/network results once browser automation is available.
