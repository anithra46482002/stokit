# StokIt Banner, Maps and Order Management Audit

**Date:** 2026-10-16 | **Status:** PARTIAL

## Banner image replacement
The existing React path already uploaded multipart `file` to `/admin-api/uploads`, then PATCHed `/admin-api/banners` with the returned `image_path`. Django validates extension/signature/size and stores under `MEDIA_ROOT/uploads`; the banner handler persists the relative path in existing `zg_slider.image_path`. UI changes add selected replacement preview, file validation, upload/save status and errors, preview cleanup, and preserve the current image when no replacement is selected. Mocked banner create/update and upload temp-storage tests pass; real upload -> DB -> served URL remains unverified.

## Place selection
The warehouse form already supports address, place, state, pincode, latitude and longitude, with server-side coordinate validation and existing-schema persistence. Google Places is used when `VITE_GOOGLE_MAPS_API_KEY` is configured; otherwise the form falls back to OpenStreetMap/Nominatim. Added no-results/error messaging, clearing stale coordinates on manual address edits, map preview/link, attribution, and slower fallback debounce. No Google key was found/configured, added, or enabled; no paid API was enabled. Browser search/selection/save/reload remains untested.

The separate `zg_location` table stores only `location_id` and `city_name`, so it cannot store full address/coordinates without a separately approved schema/API change. Current `zg_checkout` has address/city/state/postal code/country but no delivery latitude/longitude. No schema changes were made.

## Order management
The existing `OrderAdminCRUDView` had GET/PATCH but no POST, and the permission allowlist excluded order creation. Added admin-only order creation using server-fetched product/variant prices, validation for customer/address and positive whole quantities, duplicate-line rejection, transaction-wrapped checkout/items/initial history writes, and server-computed totals. Added a React form for customer/contact/address, product and quantity. UI prevents double-click while pending; however, a replay after a timeout is not persistently idempotent without a stored idempotency key.

Fixed one-sided date filters and added delivery-boy filtering to the UI and parameterized backend list/statistics filters. Filter and mocked order-create tests pass. Real order creation/readback, revenue/pending summaries, status transitions and assignment remain unverified against an isolated DB.

## Files changed
- `admin_frontend/src/BannersPage.jsx`
- `admin_frontend/src/CrudDialog.jsx`
- `admin_frontend/src/App.jsx`
- `admin_frontend/src/OrdersPage.jsx`
- `django_backend/adminapi/crud.py`
- `django_backend/adminapi/order_pages.py`
- `django_backend/adminapi/permissions.py`
- `django_backend/adminapi/tests_ui_workflows.py`

## Actual evidence
- Frontend tests: PASS 27/27.
- Frontend lint: PASS, zero warnings/errors.
- Production build: PASS, 1,988 modules.
- Focused Django tests: PASS 37/37.
- Full Django suite: PASS 139 tests, 1 expected failure.
- `manage.py check`: PASS; `migrate --check`: PASS, no migration applied.
- Python compilation: PASS.
- No authenticated DB-backed browser/API tests or external place-search tests were run.

## Approvals / blockers
1. To use Google Places, approve API/billing, configure `VITE_GOOGLE_MAPS_API_KEY`, restrict it by HTTP referrer and required APIs. No key should be committed as a server secret.
2. Approve a disposable isolated PostgreSQL DB, synthetic fixture data and test lifecycle; never use `stokit_postgres_dev` for writes.
3. Approve temporary media operations and authorized test identity.
4. Decide whether persisted idempotency keys, checkout coordinates and full `zg_location` addresses are required; approve a separate schema/API proposal before implementing those changes.

No live DB writes, DDL, migrations, imports, restores, account creation or destructive cleanup were performed. PHP and Flutter remain unchanged. **Status: PARTIAL.**


### Additional order-management risks found during source inspection
- `OrderManageView.get` currently runs an UPDATE setting `zg_checkout.view='y'` for all orders whenever the returned list is non-empty. This is a write inside a GET request and can alter existing rows during a live browser check. It was not executed against the live database. Preserve this legacy behavior until the owner approves changing the view/new-order flag semantics; integration tests must use an isolated database.
- Status endpoint accepts role-authorized values from the existing status list but there is no explicit allowed-from -> allowed-to transition graph. Strict transition rules need owner-approved business policy.
- Revenue currently sums all statuses except pending. Whether cancelled/failed orders should count as revenue needs owner confirmation and database-backed acceptance.
- Order creation has no persisted idempotency token and does not reserve/decrement stock. Do not claim replay safety or inventory correctness until these rules are approved and tested.
