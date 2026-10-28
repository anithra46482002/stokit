# StokIt API Contract Matrix — Static Source Review

**Reviewed:** 2026-10-16  
**Status: PARTIAL.** This is a source-derived route/call-site map, not proof of live end-to-end parity. No PHP or Flutter files were modified. No database row contents were inspected.

## React admin → Django REST Framework

All relative React `api.*` requests use the configured Axios client in `admin_frontend/src/api.js`; Django mounts these routes under `/admin-api/`. Authenticated behavior is enforced by the view classes and/or shared `AdminRolePermission`, except login/refresh routes. Static route declarations and frontend call sites were inspected; the method column reflects methods visible in current React call sites and view implementation, not a claim that every role/method combination was integration-tested.

| React resource / workflow | React request paths | Django route / handler | Methods observed in UI | Verification status |
|---|---|---|---|---|
| Login/session | `auth/login`, `auth/refresh` | `AdminLoginView`, `AdminRefreshView` | POST | Unit coverage exists; successful authenticated browser flow not run |
| Dashboard | `dashboard` | `DashboardView` | GET | Static mapping only |
| Reports | `reports` | `ReportsAdminView` | GET | Static mapping only |
| Categories | `categories` | `CategoryCRUDView` | GET, POST, PATCH, DELETE | Pagination fix in shared `fetchAll` does not change resource CRUD semantics; live CRUD blocked |
| Subcategories | `subcategories` | `SubcategoryCRUDView` | GET, POST, PATCH, DELETE | Parent category is sent as `category_id`; live CRUD blocked |
| Products | `products` | `ProductCRUDView` | GET, PATCH, DELETE; shared `App.jsx` CRUD also handles POST | Query filters include optional `warehouse_id`; live workflow blocked |
| Product variants | `product-variants` | `VariantCRUDView` | POST, PATCH; shared CRUD also supports GET/DELETE where configured | Static mapping only |
| Product images | `product-images` | `ProductImageCRUDView` | POST; shared CRUD may load list | Upload + database effect not tested end-to-end |
| Customers | `customers` | `CustomerCRUDView` | GET, POST, PATCH, DELETE | `fetchAll` used by notifications/product-related forms; pagination now follows backend count |
| Orders | `orders`, `orders/manage`, `orders/bulk-assign`, `orders/<id>/detail`, `orders/<id>/status` | `OrderAdminCRUDView`, `OrderManageView`, `OrderBulkAssignView`, `OrderDetailView`, `OrderStatusView` | GET, POST, PATCH, DELETE according to the corresponding page action | Order write/delete policy and full CRUD remain unverified |
| Banners | `banners` | `BannerAdminView` | GET, POST, PATCH, DELETE | Upload + DB + served URL not tested end-to-end |
| Notifications | `notifications` | `NotificationAdminView` | GET, POST, DELETE | Recipient behavior and role matrix not fully integration-tested |
| Warehouses | `warehouses` | `WarehouseAdminView` | GET and shared CRUD methods | Product/warehouse relation is incomplete pending excluded-table decision |
| Inventory | `inventory` | `InventoryAdminView` | Shared CRUD methods | Transaction/concurrency behavior not tested against isolated DB |
| Cart discount | `cart-discount-settings` | `CartDiscountSettingsView` | GET, PUT | Main target currently reports zero rows; no write test was run |
| Staff | `staff?kind=salesmen|delivery` | `StaffAdminView` | Shared CRUD methods | Role/warehouse dependencies require isolated integration tests |
| Advance payment offers | `advance-payments` | `AdvancePaymentOffersView` | GET, POST, PATCH, DELETE | Business formula differences between legacy add/edit behavior need owner-approved policy review |
| Advance allocations | `advance-allocations` | `AdvanceAllocationAdminView` | Shared CRUD methods | Ledger integrity/concurrency not tested against isolated DB |
| Locations | `locations` | `LocationAdminView` | Shared CRUD methods | City-name collation mismatch remains blocked |
| Targets | `targets` | `TargetAdminView` | Shared CRUD methods | Assignment/progress integrity not tested against isolated DB |
| Image upload | `uploads` | `ImageUploadView` | POST multipart | Upload type/size/production serving acceptance not run |

## Flutter-facing `/api/*` routes

Django mounts `legacy_api.urls` under `/api/`. The current registered path-to-view mapping is:

| Path | Django handler | Status |
|---|---|---|
| `login`, `logout`, `profile`, `geocode` | `views_auth` | Route registration verified; payload/status/auth parity not complete |
| `banner`, `category`, `sub_categories`, `getCategory`, `search`, `highlights`, `recommended`, `product-api` | `views_catalog` | Route registration verified; payload/status parity not complete |
| `fav`, `favpage` | `views_favorites` | Route registration verified; behavior parity not complete |
| `cart_action` | `views_cart` | PostgreSQL rollback workflow passed 17 checks; product_id disambiguates multiple variant-0 products; full Flutter UI remains unverified |
| `product-api-cart`, `cart_api_test`, `checkout`, `noti_list`, `notification_action`, `notify` | `views_commerce` | Route registration verified; side effects and status parity not complete |
| `order_post`, `orders`, `order_details`, `order_cancel` | `views_orders` | Route registration verified; order lifecycle parity not complete |
| `acc/`, `acc/reset` | `views_reset` | Route registration verified; reset-flow acceptance not complete |
| `saveCheck`, `targets`, `coabout` | `views_remaining` | Route registration verified; behavior parity not complete |
| `advancePay-api`, `crd_rel`, `contactus` | `views_finance` | Route registration verified; finance parity not complete |

## Known scope gaps and required contract tests

- `zg_product_warehouse` is explicitly excluded from the current PostgreSQL target and has no confirmed Django model/API equivalent. The available PHP backup contains SQL references in product/warehouse management pages, including product list joins and assignment writes. The backup is not proven to be the active deployed revision. Do not add the table or change behavior until the owner approves scope and schema design.
- `zg_location.city_name` uses a source MariaDB collation whose tested PostgreSQL candidate still mismatches trailing NBSP behavior. No target collation change is approved.
- The PHP backup and Flutter source remain read-only. Route registration is not equivalent to request/response parity. A complete contract suite must compare HTTP method, auth, query/body fields, nullability/types, response keys, status codes, error payloads, image URLs, side effects and transaction behavior for every route.
- Required E2E evidence: approved isolated PostgreSQL instance and configuration, approved disposable fixtures, owner-authorized test accounts/roles, browser automation already available or explicitly approved, and assertions over UI/network/console plus database effects. Do not create databases/accounts or install tooling without approval.

## Detailed source-derived contracts (2026-10-16 continuation)

This section records fields visible in the current React request construction and Django handlers. It does not prove successful live requests. The target database was not used for writes, and authenticated browser CRUD was not executed.

### Admin request/response contract map

| Endpoint / methods | Request fields and query parameters | Response fields | Validation and limits | Permission source |
|---|---|---|---|---|
| /admin-api/categories GET, POST, PATCH, DELETE | GET: search, page, page_size; writes: id, name, image, active | Paged results: id, name, image, image_url, active; writes return row fields or 204 | Name required, max 255; delete returns 409 if used by products/subcategories; page size 1–100 | AdminRolePermission, catalogue |
| /admin-api/subcategories GET, POST, PATCH, DELETE | GET: category_id, search, page, page_size; writes: id, name, category_id, image, active | Paged results: id, name, category_id, category_name, image, image_url, active | Category must exist; name required; delete returns 409 if a product references it | AdminRolePermission, catalogue |
| /admin-api/products GET, POST, PATCH, DELETE | GET: search, category_id, visible, warehouse_id, page, page_size; writes include id, name, code, price, mrp, discount, category_id, subcategory_id, stock, color, gst_applicable, gst_percentage, gst_price, description, keywords, visible, highlight | Paged products with image and variant arrays; writes return product ID and category/subcategory fields or 204 | Category and matching subcategory required; finite non-negative monetary values; delete preserves order history and returns 409 for referenced products. Warehouse assignment remains unresolved because zg_product_warehouse is excluded | AdminRolePermission, catalogue |
| /admin-api/product-variants GET, POST, PATCH, DELETE | GET: product_id, page, page_size; writes: id, product_id, name, price, variant_price, mrp, quantity, discount, gst, gst_price | Paged results include id, product_id, name, price, mrp, quantity, discount, gst, gst_price; writes return variant fields or 204 | Product must exist; amounts and quantity non-negative; GST is Y/N; discount is 0–100; deletion blocked by order/cart references | AdminRolePermission, catalogue |
| /admin-api/product-images GET, POST, DELETE | GET: product_id, page, page_size; POST: product_id, image_path, main; DELETE: id | Paged image records; POST returns id, product_id, image_path, main; DELETE returns 204 | Existing product and image_path required; selecting main clears other main flags for that product in one transaction | AdminRolePermission, catalogue |
| /admin-api/customers GET, POST, PATCH, DELETE | GET: search, vip, color, warehouse_id, offer_id, page, page_size; writes support username, password, email, full_name, phone, shop_name, address, city, state, pincode, GST fields, status, VIP fields, delivery_charges, store_maped, category_id, color_code, warehouse_id, profile_picture | Paged results plus filters and shop_categories; customer output includes contact, GST, VIP, warehouse and profile fields | Username format/uniqueness; password minimum 10; email/mobile validation; numeric filter IDs; salesman PATCH limited to contact/shop fields; referenced customers are deactivated rather than deleted | AdminRolePermission, customers; additional salesman field restriction |
| /admin-api/orders/manage GET | from_date, to_date, status, color_code, warehouse_id | count, ranged, stats, filters, delivery_boys, orders[] | Dates require real YYYY-MM-DD dates; exclusive next-day upper bound. GET no longer updates `zg_checkout.view`; mocked read-only regression passes | OrderActionPermission |
| /admin-api/orders/bulk-assign POST | order_ids[], delivery_boy_id | assigned, message | Requires at least one order ID and an existing delivery boy | OrderActionPermission; default write roles SUPER_ADMIN/ADMIN |
| /admin-api/orders/{id}/detail GET, PATCH, DELETE | PATCH: customer address/contact fields and items[] entries with item_id, quantity, price, discount | Detail object from _build_detail; DELETE returns 204 | Full name required; bounded fields; valid email; non-negative whole quantity; discount cannot exceed line total; item must belong to order. Delete removes order items and status history | OrderActionPermission; write policy requires owner acceptance |
| /admin-api/orders/{id}/status POST | status, status_message, delivery_boy_id | Order detail, optionally credit_release | Status must be in legacy status set; role-specific status limits; delivery boy must exist. Admin transition to Processing may release bonus credit. Source permits writes for all five roles; test every role before acceptance | OrderActionPermission, write_roles and ROLE_STATUS_LIMITS |
| /admin-api/banners GET, POST, PATCH, DELETE | GET: search, page, page_size; writes: id, image_path, text_content, styled_text, styled_color, background, text_content2 | Paged rows with image_path and image_url; writes return ID/path or 204 | Image path required; image hosting and serving not browser-tested | AdminRolePermission, banners |
| /admin-api/notifications GET, POST, DELETE | GET: search, page, page_size; POST: title, message, recipient_type, customer_id; DELETE: id | Paged rows; POST returns stored notification and delivery=stored | Title required/max 255; message required/max 5000; recipient type all/selected; selected customer must exist. Push delivery is not configured | AdminRolePermission, notifications |
| /admin-api/warehouses GET, POST, PATCH, DELETE | GET: search, page, page_size; writes: id, name, address, pincode, state, place, latitude, longitude | Paged rows; writes return ID/name or 204 | Name required/max 100; coordinates must be finite and in geographic range with at most 8 decimals; deletion checks known dependencies | AdminRolePermission, warehouse |
| /admin-api/inventory GET, PATCH | GET: search, page, page_size; PATCH: id, quantity, reason | Paged variant stock rows; PATCH returns id, quantity | Warehouse filter explicitly rejected because legacy variant stock is not warehouse-scoped; quantity non-negative integer and reason required; stock update and log are atomic | AdminRolePermission, inventory |
| /admin-api/cart-discount-settings GET, PUT | PUT: enabled, minimum_subtotal, fixed_discount_amount | enabled, minimum_subtotal, fixed_discount_amount, updated_at | Boolean required; amounts finite/non-negative; settings row ID 1 locked in a transaction. No target write test was run | AdminRolePermission, cart_discount; writes restricted to SUPER_ADMIN/ADMIN |
| /admin-api/staff GET, POST, PATCH, DELETE | kind=salesmen/delivery; username, email, full_name, password, phone, address, commission_rate, target_sales, hire_date, id | Paged rows; writes return ID, username, email, full_name, kind | Password minimum 10; email/mobile validation; supported staff type required; database write behavior not integration-tested | AdminRolePermission, staff |
| /admin-api/advance-payments GET, POST, PATCH, DELETE | offer_name, payment_amount, bonus_percentage, duration_months, status, image_path, offer_image, id | Paged offers; writes return offer values, benefit and image URL | Amount positive, bonus 0–100, duration positive, status ACTIVE/INACTIVE; image upload max 5 MB and supported image formats; delete deactivates offers with allocations | AdminRolePermission, advance_payments |
| /admin-api/advance-allocations GET, POST, PATCH, DELETE | offer_id, user_id, payment_date, start_date, end_date, payment_reference, notes, status, remaining_credit, adjustment_note, id | Paged rows with user/offer labels and balances; writes return allocation ID/status/balance | Customer and active offer required on create; ISO dates; statuses ACTIVE/COMPLETED/CANCELLED; one active allocation per customer; credit adjustments create transaction records. Ledger acceptance remains unverified | AdminRolePermission, advance_payments |
| /admin-api/locations GET, POST, PATCH, DELETE | GET: search, page, page_size; writes: id, city_name | Paged id/city_name rows; writes return ID/name or 204 | Name required/max 100; deletion blocked when customers or warehouses reference the city; collation parity unresolved | AdminRolePermission, locations |
| /admin-api/targets GET, POST, PATCH, DELETE | target_name, category_id, target_amount, reward_description, reward_image, scheme_benefits, start_date, end_date, status, id | Paged rows with ISO date strings | Category must exist; amount finite and greater than zero; ISO dates; end date cannot precede start date; deletion blocked when assignments/achievements exist | AdminRolePermission, targets |
| /admin-api/uploads POST multipart | Multipart field file | image_path, url | JPG/PNG/GIF/WEBP signature must match extension; max 5 MB; actual file creation/serving not tested in this continuation | AdminRolePermission, catalogue |

### Role and permission summary from current source

| Role | Readable resources in ROLE_RESOURCES | Source restrictions |
|---|---|---|
| SUPER_ADMIN | All resources | Full access according to current map |
| ADMIN | dashboard, catalogue, customers, orders, banners, notifications, advance_payments, reports, targets, locations, warehouse, inventory, staff, cart_discount | Write access only on supported methods/resources; integration not run |
| SALESMAN | dashboard, customers, orders, reports | Customer PATCH restricted to contact/shop fields; order status limited by ROLE_STATUS_LIMITS |
| WAREHOUSE_STAFF | dashboard, catalogue, warehouse, inventory, orders | Inventory PATCH allowed; warehouse/product assignment semantics incomplete |
| DELIVERY_BOY | dashboard, orders | Order status limited by ROLE_STATUS_LIMITS; no delivery assignment changes unless admin |

For AdminRolePermission, GET uses the resource map. POST and DELETE have explicit allowlists; PUT/PATCH have a separate role map. Order pages use OrderActionPermission. This is source evidence only; positive and negative authenticated tests for every role/method/resource combination remain required.

### Evidence status

- Frontend unit suite after pagination edge-case changes: 24/24 PASS, including repeated-page and 1,000-page hard-limit cases.
- Database-free CRUD validation module adminapi.tests_crud_validation: 10/10 PASS; full Django suite: 116 tests PASS with 1 expected city-collation failure.
- Django system check: PASS; migration consistency check: PASS, with no migration applied.
- No target database writes, schema changes, migrations, imports, restores, account creation, package installation, or external temporary-resource cleanup were performed. Generated Python bytecode cache cleanup is documented in `STOKIT_TEMPORARY_RESOURCE_CLEANUP_REVIEW.md`.
- Flutter/PHP request/response parity remains UNVERIFIED. Route registration is not behavioral proof. No authenticated browser CRUD or target write test was executed. The 2026-10-16 API audit adds a Django-only `/api/search` POST compatibility extension while retaining GET behavior; 3 database-free regression tests pass, but E2E remains NOT VERIFIED.

### Test evidence by area

| Area | Source test evidence executed | What it proves | What remains unverified |
|---|---|---|---|
| Shared React pagination | admin_frontend/src/uiUtils.test.js, included in npm test 24/24 | Count handling, filter preservation, empty/short page termination, repeated-page detection, hard cap | Live endpoint pagination and concurrent dataset changes |
|| Product category/subcategory | adminapi.tests_crud_validation, 3 tests | PATCH rejects invalid relationship changes and malformed subcategory IDs before save | Database-backed product CRUD and legacy relationship parity remain unverified |
|| Product/variant numeric validation | adminapi.tests_crud_validation, 5 tests across product and variant paths | Invalid GST/discount and non-finite product/variant amounts return 400 without save | DB constraints and full create/update against isolated fixtures remain unverified |
|| Variant quantity validation | adminapi.tests_crud_validation, 2 tests | Fractional quantity is rejected on create and PATCH | DB constraints and stock transaction behavior remain unverified |
|| Category and dashboard | adminapi.tests_dashboard_categories | Category delete dependency response, category image URL serialization, dashboard revenue status selection | Live table behavior and role/method matrix |
| Cart discount | adminapi.tests_cart_discount and adminapi.tests_db_errors | Pure discount calculation and storage-error response classification | Saving settings against an isolated PostgreSQL schema; customer cart application parity |
| Uploads | adminapi.tests_uploads | Request/file validation covered by unit tests | Real file creation, media serving, production storage and cleanup behavior |
| Authentication/roles | accounts.tests, accounts.tests_roles, adminapi.tests_auth, config.tests | Token/session and role helper behavior covered by unit tests | Authenticated browser CRUD, every role/method/resource combination and token expiry in browser |
| Legacy Flutter endpoints | legacy_api.tests_contract, legacy_api.tests_postgres_sql, legacy_api.tests_runtime_contract, legacy_api.tests_reset | Static route/source contracts and selected SQL/utility rules | Full payload/status/image URL/side-effect parity against authoritative PHP and Flutter behavior |
| City collation | adminapi.tests_city_name_collation | Source evidence and the known parity gap | One expected failure remains for trailing-NBSP semantics; policy and isolated parity tests are pending |
| Orders, inventory and advance credit | Existing unit/SQL tests plus static handler inspection | Some pure calculations and SQL construction have coverage | Authenticated DB CRUD, transaction rollback, concurrency, trigger effects and business-owner acceptance |

The full Django command executed in this continuation was `python manage.py test --verbosity 1`: 116 tests, zero failures, one expected failure. No test database setup was reported by the runner. The read-only target verifier was also executed; no application writes were made.

## Continuation  -  Target Scheme image upload and cart discount contracts (2026-10-16)

### Target Scheme and reward image

| Flow / endpoint | Request | Response | Validation / permission | Evidence status |
|---|---|---|---|---|
| Target Scheme category options | GET /admin-api/categories?page=N&page_size=100; React uses fetchAll and option pairs [String(category.id), category.name] | Paged category objects include id and name | category_id must be positive integer; display label is not payload value | Frontend helper tests pass; live dropdown/browser test not run |
| Target create/update | POST/PATCH /admin-api/targets: target_name, category_id, target_amount, reward_description, reward_image, scheme_benefits, start_date, end_date, status; PATCH also id | Target response includes id, category_id, reward_image, reward_image_url, amount, descriptions, dates, status | Category must exist; amount finite and >0; ISO dates; legacy relative image paths/HTTP(S) URLs accepted | Unit validation passes; authenticated CRUD not executed |
| Reward upload | POST /admin-api/uploads multipart field file | image_path (uploads/<random>.<ext>) and url | Catalogue write permission; max 5 MB; extension and signature must match; MEDIA_ROOT/uploads | Upload API tests pass with temporary media storage; browser preview/media serving not tested |
| Target image persistence | Upload result image_path is stored in reward_image before target POST/PATCH | reward_image and derived reward_image_url | No schema change; existing saved paths/URLs remain supported | Source reviewed; target save + uploaded file not exercised end-to-end |

### Customer cart discount behavior

| Endpoint / function | Inputs / data source | Response / rule | Evidence status |
|---|---|---|---|
| GET /api/cart_api_test | Authenticated user identity; server queries users VIP flag/percentage and a_cart joined to product, variant and image rows; no client totals accepted | Preserves legacy cart_items groups, final_summary, discount and mov keys. Existing product-discount lines are excluded; active VIP suppresses cart promotion; amounts calculated server-side | Pure helper/response-builder tests pass; no authenticated DB-backed cart call or Flutter runtime test |
| legacydb.discount_rules.product_has_discount | has_disc, discount_percent, discount_value, product_discount | Any active flag or positive known discount field makes a line ineligible | Unit tests cover each flag/field |
| adminapi.cart_discount.calculate_cart_discount | Server-derived lines; enabled, minimum_subtotal, fixed_discount_amount, optional vip_applied | Excludes product_discounted, positive line discounts and known product-discount fields; VIP blocks cart promotion; fixed discount capped to eligible subtotal | Pure tests pass |
| GET/PUT /admin-api/cart-discount-settings | PUT: enabled, minimum_subtotal, fixed_discount_amount | Separate admin fixed-amount configuration | Not wired into /api/cart_api_test, which retains legacy minimum 14,000 and 10% discount. Owner decision needed before merging different rule models. |

PHP/Flutter remain read-only. Full API parity, authenticated browser tests, real database/cart integration and business acceptance remain unverified.


## Cart discount policy distinction and acceptance gate (2026-10-16)

The two current discount mechanisms are separate and must not be treated as one configuration:

- GET /api/cart_api_test calls _build_cart_response with legacy policy constants: enabled, minimum order value 14000, cart percentage 10.0. Qualification currently uses current >= min_order_value, where current is the total price of the undiscounted (discount_not_available) group. The percentage applies only to that group. Product-discounted lines are placed in the other group. Active VIP means vip_discount='Y' and positive vip_percentage; in that case the cart promotion is suppressed and VIP discount is calculated separately. Monetary rounding uses ROUND_HALF_UP to two decimal places.
- GET/PUT /admin-api/cart-discount-settings stores enabled, minimum_subtotal, and fixed_discount_amount. The pure helper calculate_cart_discount uses eligible subtotal after excluding discounted lines; qualification currently uses strict eligible_subtotal > minimum_subtotal; applied fixed amount is capped at eligible subtotal. This helper/configuration is NOT wired into /api/cart_api_test.

No behavior was changed in this continuation. Owner approval is required to choose the authoritative policy and decide threshold base/comparison, fixed-vs-percentage semantics, VIP interaction, mixed carts, rounding and cap. See STOKIT_CART_DISCOUNT_POLICY_DECISION.md and STOKIT_CART_DISCOUNT_INTEGRATION_TEST_PLAN.md.

Focused source regression tests passed, but database-backed cart calculations, authenticated Target Scheme CRUD, upload-to-target persistence, and HTTP image serving were not executed. These acceptance tests are BLOCKED pending approval of an isolated PostgreSQL test environment and fixtures. Overall status remains PARTIAL.


## Banner image, place selection and order management (2026-10-16)

- Banner API: POST/PATCH /admin-api/banners stores relative image_path in existing zg_slider.image_path. POST /admin-api/uploads accepts multipart field file, validates JPG/PNG/GIF/WEBP signature and 5 MiB size, and returns image_path plus URL. React previews a selected replacement, validates it, shows upload/save status/errors, and does not PATCH if no replacement was selected. Unit/mocked tests pass; authenticated upload -> DB -> served URL round-trip is BLOCKED.
- Warehouse place selection: Google Places Autocomplete activates only when VITE_GOOGLE_MAPS_API_KEY is configured. Without it, the form uses OpenStreetMap/Nominatim fallback and a map preview/link. WarehouseAdminView stores address/place/state/pincode/latitude/longitude in existing schema and validates coordinate bounds. No Google key was added or paid API enabled. Browser/API place-search E2E is BLOCKED.
- Locations catalog: /admin-api/locations uses zg_location, which stores city_name only. Full address/coordinates require separately approved schema/API changes; none were made.
- Orders: POST /admin-api/orders now creates checkout, items and initial status history transactionally using product/variant prices read server-side. Only SUPER_ADMIN/ADMIN can create. React has customer/contact/address, product/quantity selection and server-authoritative create request. Current zg_checkout schema has no delivery-coordinate columns; persisted idempotency for request replay is not implemented.
- Order filters: date, status, color_code, warehouse_id and delivery_boy_id are applied to list/summary query construction. One-sided date filters no longer gain an implicit today boundary. Source tests cover parameterized filter construction; isolated DB-backed list/revenue/pending verification was not performed.
- Authenticated order listing, status, assignment, summary and create/readback tests remain BLOCKED pending an approved isolated PostgreSQL fixture database. Overall status remains PARTIAL.


Order-management source caveats: `GET /admin-api/orders/manage` still writes `zg_checkout.view='y'` for all orders when the list is non-empty; it was not executed against live data. Status updates have role/value validation but no explicit transition graph. Revenue excludes pending but includes other statuses; cancelled/failed revenue policy needs owner approval. Manual order creation has no persisted idempotency key and does not reserve stock. These are not accepted as end-to-end verified.


## Complete API audit cross-reference — 2026-10-16

See `STOKIT_COMPLETE_API_AUDIT.md` for the route-by-route matrix of all 26 admin patterns and 33 Flutter-facing legacy patterns, Flutter call-site request shapes, security/configuration notes, cleanup classification, and per-route verification status. No route is certified end-to-end. STK-API-001 is fixed in Django with POST filter support while preserving GET search; 3 database-free regression tests pass, but E2E remains NOT VERIFIED. Keep `GET /admin-api/orders/manage` blocked on the live target because it mutates the legacy new-order flag.


## Search POST compatibility regression — 2026-10-16

`legacy_api.views_catalog.search` accepts both the original GET contract (`search`, `skip`, `limit`) and the current Flutter POST JSON filter contract (`min_price`, `max_price`, `sort_by`, `skip`, `limit`). The POST extension validates finite non-negative price bounds, rejects inverted ranges, allowlists sorting, rejects unsupported HTTP methods with 405, and parameterizes filter values. `legacy_api.tests_runtime_contract.FlutterSearchPostContractTests` covers POST filters/sort/page, GET compatibility, invalid range, and unsupported method. Result: 4/4 PASS with mocked SQL helpers. No Flutter or PHP source changed. This is code-level contract evidence only; authenticated database-backed parity remains NOT VERIFIED.

## Order creation, financial summary, and banner regression update (2026-10-16)

| Workflow | Current contract/source behavior | Regression evidence | Acceptance status |
|---|---|---|---|
| `POST /admin-api/orders` | Admin-only. Payload includes customer contact/address fields and `items[]` with `product_id`, optional `variant_id`, and whole positive `quantity`. If a product has variants, a variant must be selected. Backend validates variant ownership and derives price from the stored product/variant record; checkout, item snapshots, and `Placed` history are created in one transaction. | Database-free tests verify base and variant prices override client price, invalid/missing variant rejection, duplicate-line rejection, and history creation calls. | Code regression PASS; real PostgreSQL transaction, persistence, and order-list readback NOT VERIFIED. |
| `GET /admin-api/orders/manage` | Filtered order list plus date/status summary. Date filters validate real `YYYY-MM-DD` dates and use an exclusive next-day upper bound. Revenue recognizes normalized `delivered`/`fulfilled`; pending count recognizes configured open legacy statuses; cancelled/failed are excluded. DISTINCT order IDs protect aggregates from duplicate joined user rows. | Mocked SQL builder and read-only handler test pass; selected suite validates date/status filter construction. | Code regression PASS; actual row-level aggregate parity NOT VERIFIED. GET no longer changes `zg_checkout.view`. |
| `GET /admin-api/dashboard` | Revenue normalizes status case/whitespace and sums only completed `delivered`/`fulfilled` orders; empty aggregate resolves to zero. | Status normalization/source regression and Django checks pass. | Code regression PASS; authenticated database comparison NOT VERIFIED. |
| `GET /admin-api/reports` | Total and per-status revenue use the same completed-order status predicate rather than summing pending/cancelled/failed amounts as revenue. | Covered by source review and Django system checks; query not executed against an approved isolated fixture database. | Code-level change; database aggregate NOT VERIFIED. |
| `POST /admin-api/uploads` → `PATCH /admin-api/banners` → `GET /admin-api/banners` | Multipart field is `file`; upload returns legacy-relative `image_path`; PATCH persists only when a replacement is supplied; old image files are not deleted by replacement; GET chooses local DEBUG media URL when the file exists and retains legacy URLs otherwise. | Temporary-media upload tests plus mocked banner path-preservation/replacement tests pass. | Component regressions PASS; authenticated upload/save/reload/image-serving browser acceptance NOT VERIFIED. |

### Actual verification after changes

- React tests 31/31; lint 0 warnings/errors across 24 files; Vite production build PASS (1,988 modules transformed).
- Selected database-independent Django/API contract suite 105/105; `manage.py check` PASS; `migrate --check` PASS with no migration applied.
- No full test-database lifecycle, authenticated CRUD, or live target write was performed. No PHP/Flutter source was changed. Overall project status remains PARTIAL.

Banner serving follow-up: temporary upload tests now verify both file creation and byte-for-byte reads through Django's `serve` component (5/5 upload tests pass). URL routing, banner DB persistence/reload, authenticated browser refresh, and production media serving remain NOT VERIFIED.

## Combined React + Flutter route matrix — static audit continuation (2026-10-16)

The detailed request/response contracts remain in the sections above. This consolidated registry joins both clients to their separate Django namespaces so a matching path name is not mistaken for a shared endpoint. “Static match” means a source route and call site align; it does not certify authenticated runtime success.

| Client | Route | Django handler | Request contract / payload evidence | PHP reference | Audit status |
|---|---|---|---|---|---|
| React | `/admin-api/auth/login` | `AdminLoginView` | POST credentials | N/A | Static route match; browser auth not E2E verified |
| React | `/admin-api/auth/refresh` | `AdminRefreshView` | POST refresh token/session payload | N/A | Static route match; refresh E2E not verified |
| React | `/admin-api/uploads` | `ImageUploadView` | Multipart `file` | N/A | Unit/component tests pass; authenticated browser flow not verified |
| React | `/admin-api/dashboard` | `DashboardView` | GET | N/A | Static route match; authenticated response not verified |
| React | `/admin-api/reports` | `ReportsAdminView` | GET | N/A | Static route match; totals not compared with fixture orders |
| React | `/admin-api/categories` | `CategoryCRUDView` | GET/POST/PATCH/DELETE category fields | N/A | Static route match; authenticated CRUD not E2E verified |
| React | `/admin-api/subcategories` | `SubcategoryCRUDView` | GET/POST/PATCH/DELETE; `category_id` parent | N/A | Static route match; authenticated CRUD not E2E verified |
| React | `/admin-api/products` | `ProductCRUDView` | GET filters; product fields for writes | N/A | Static route match; authenticated CRUD not E2E verified |
| React | `/admin-api/product-variants` | `VariantCRUDView` | Product/variant IDs, price, quantity, discount, GST | N/A | Static route match; authenticated CRUD not E2E verified |
| React | `/admin-api/product-images` | `ProductImageCRUDView` | Product ID, image path, main-image flag | N/A | Static route match; image persistence not E2E verified |
| React | `/admin-api/customers` | `CustomerCRUDView` | Customer fields and filters | N/A | Static route match; authenticated CRUD not E2E verified |
| React | `/admin-api/orders` | `OrderAdminCRUDView` | GET/POST/PATCH; POST customer fields + items[] | N/A | Code regression tests pass; PostgreSQL create/readback not E2E verified |
| React | `/admin-api/orders/manage` | `OrderManageView` | GET date/status/warehouse/color filters | N/A | GET is now read-only; mocked regression passes; authenticated E2E not verified |
| React | `/admin-api/orders/bulk-assign` | `OrderBulkAssignView` | POST `order_ids[]`, `delivery_boy_id` | N/A | Static route match; assignment E2E not verified |
| React | `/admin-api/orders/{order_id}/detail` | `OrderDetailView` | GET/PATCH/DELETE; order/customer/items fields | N/A | Static route match; transaction/policy E2E not verified |
| React | `/admin-api/orders/{order_id}/status` | `OrderStatusView` | POST status, message, optional delivery boy | N/A | Static route match; role/status workflow not E2E verified |
| React | `/admin-api/banners` | `BannerAdminView` | GET/POST/PATCH/DELETE; `image_path` and banner text fields | N/A | Upload/PATCH components tested; persisted reload/browser refresh not verified |
| React | `/admin-api/notifications` | `NotificationAdminView` | GET filters; POST title/message/recipient fields; DELETE ID | N/A | Static route match; push delivery and role workflow not E2E verified |
| React | `/admin-api/warehouses` | `WarehouseAdminView` | GET/POST/PATCH/DELETE; location/address fields | N/A | Static route match; save/reload not E2E verified |
| React | `/admin-api/inventory` | `InventoryAdminView` | GET/PATCH; variant ID, quantity, reason | N/A | Static route match; isolated DB effects not verified |
| React | `/admin-api/cart-discount-settings` | `CartDiscountSettingsView` | GET/PUT enabled, minimum subtotal, fixed amount | N/A | Static route match; live persistence not verified |
| React | `/admin-api/staff` | `StaffAdminView` | GET/POST/PATCH/DELETE; staff identity/role fields | N/A | Static route match; account creation not run |
| React | `/admin-api/advance-payments` | `AdvancePaymentOffersView` | GET/POST/PATCH/DELETE offer fields | N/A | Static route match; isolated finance workflow not verified |
| React | `/admin-api/advance-allocations` | `AdvanceAllocationAdminView` | GET/POST/PATCH/DELETE allocation fields | N/A | Static route match; ledger workflow not verified |
| React | `/admin-api/locations` | `LocationAdminView` | GET/POST/PATCH/DELETE location fields | N/A | Static route match; collation parity remains blocked |
| React | `/admin-api/targets` | `TargetAdminView` | GET/POST/PATCH/DELETE target/assignment fields | N/A | Static route match; progress persistence not verified |
| Flutter | `/api/login` | `views_auth.login` | POST `username`, `password`; expects success/message/token/user | `api/login.php` | Static payload matches; auth E2E not run |
| Flutter | `/api/logout` | `views_auth.logout` | POST with bearer session; no active mobile caller found | No matching PHP API file found | Mobile logout gap confirmed |
| Flutter | `/api/profile` | `views_auth.profile` | POST, no body; expects `profile` object | `api/profile.php` | Static keys align; nullable-field parsing risk STK-MOB-008 |
| Flutter | `/api/geocode` | `views_auth.geocode` | POST `latitude`, `longitude` | `api/geocode.php` | Static payload mapping; persistence not E2E verified |
| Flutter | `/api/banner` | `views_catalog.banner` | GET pagination query; expects `banner[]` with `image_url` | `api/banner.php` | Static response shape aligns; live image URLs not verified |
| Flutter | `/api/category` | `views_catalog.category` | GET; expects `categories[]` and nested subcategories | `api/category.php` | Static response shape aligns; auth/data not E2E verified |
| Flutter | `/api/sub_categories` | `views_catalog.sub_categories` | POST `sub_category_id` | `api/sub_categories.php` | Static payload shape aligns; live response not verified |
| Flutter | `/api/getCategory` | `views_catalog.get_category` | POST `category_id` (actually a subcategory ID); client also sends `skip`, `limit` | `api/getCategory.php` | Pagination mismatch STK-MOB-003 confirmed; backend/PHP ignore skip/limit |
| Flutter | `/api/search` | `views_catalog.search` | POST filters `min_price`, `max_price`, `sort_by`, `skip`, `limit`; query omitted by repository | `api/search.php` (GET contract) | POST filter support is regression-tested; incomplete search scope STK-MOB-004 |
| Flutter | `/api/highlights` | `views_catalog.highlights` | GET | `api/highlights.php` | Static route match; response E2E not verified |
| Flutter | `/api/recommended` | `views_catalog.recommended` | GET | `api/recommended.php` | Static route match; data behavior not E2E verified |
| Flutter | `/api/product-api` | `views_catalog.product_api` | POST `product_id`; expects nested `product` object | `api/product-api.php` | Static shape mostly aligns; `set_contains` risk STK-MOB-007; endpoint has legacy `category_view` write side effect |
| Flutter | `/api/fav` | `views_favorites.fav` | POST `product_id` | `api/fav.php` | Static payload match; toggle persistence not E2E verified |
| Flutter | `/api/favpage` | `views_favorites.favpage` | GET; expects `fav[]` | `api/favpage.php` | Static response mapping; live data not verified |
| Flutter | `/api/cart_action` | `views_cart.cart_action` | POST `product_id`, `variant_id`, `action` | `api/cart_action.php` | PostgreSQL rollback workflow passed; `variant_id` scopes candidate lines and `product_id` selects the intended product when variantless lines collide; ambiguous requests make no mutation |
| Flutter | `/api/product-api-cart` | `views_commerce.product_api_cart` | POST `product_id`, `variants:[{variant_id,qty}]` | `api/product-api-cart.php` | Static payload matches; DB effects not tested |
| Flutter | `/api/cart_api_test` | `views_commerce.cart_api_test` | GET; expects grouped `cart_items` summary | `api/cart_api_test.php` | Cart model key mismatch STK-MOB-005; pricing policy still needs parity review |
| Flutter | `/api/checkout` | `views_commerce.checkout` | GET; expects `checkout_data.profile`, `cart_items`, `cart_summary` | `api/checkout.php` | Static shape aligns; no authenticated flow tested |
| Flutter | `/api/saveCheck` | `views_remaining.save_check` | POST checkout payload; response uses legacy `oder_id` | `api/saveCheck.php` | Payload storage differs (Django table vs PHP file); repository call site unconfirmed; not order creation |
| Flutter | `/api/notify` | `views_commerce.notify` | POST with `Device-Token` header | `api/notify.php` | Static header matches; FCM token logging risk STK-MOB-009 |
| Flutter | `/api/noti_list` | `views_commerce.noti_list` | GET; PUT `?action=mark_read` with `notification_id` or `mark_all` | `api/noti_list.php` | Read-state workflow missing STK-MOB-006 |
| Flutter | `/api/notification_action` | `views_commerce.notification_action` | POST `message_id`; expects status/heading/body | `api/notification_action.php` | Static payload/response mapping aligns; live notification access not tested |
| Flutter | `/api/order_post` | `views_orders.order_post` | POST with no body; server uses authenticated cart | `api/order_post.php` | Actual mobile order-creation route; transaction E2E not run |
| Flutter | `/api/orders` | `views_orders.orders` | GET pagination query; expects `orders[]` and product rows | `api/orders.php` | Static model mapping; ownership/pagination E2E not run |
| Flutter | `/api/order_details` | `views_orders.order_details` | POST `order_id`; expects order/pricing/delivery_status | `api/order_details.php` | Static key mapping; pricing/ownership not E2E verified |
| Flutter | `/api/order_cancel` | `views_orders.order_cancel` | POST `order_id` | `api/order_cancel.php` | Static payload match; ownership/status workflow not E2E verified |
| Flutter | `/api/acc/` | `views_reset.request_reset` | Reset request; active constant is named `forgotPassword` | `api/acc/index.php` | Static route match; OTP flow not tested |
| Flutter | `/api/acc/reset` | `views_reset.reset_password` | Reset confirmation; no dedicated active constant/call found | `api/acc/reset.php` | Route registered; UI call path unverified |
| Flutter | `/api/targets` | `views_remaining.targets` | GET; expects success/targets[] | `api/targets.php` | Static response mapping; assignment/progress not E2E verified |
| Flutter | `/api/coabout` | `views_remaining.coabout` | GET; expects `links` object | `api/coabout.php` | Confirmed placeholder URLs; owner action required |
| Flutter | `/api/advancePay-api` | `views_finance.advance_pay` | POST `status`; model expects `data.offers` and pagination total | `api/advancePay-api.php` | Static response keys align; live finance data not verified |
| Flutter | `/api/crd_rel` | `views_finance.credit_release` | GET; expects user/summary/data | `api/crd_rel.php` | Static response mapping; ledger not E2E verified |
| Flutter | `/api/contactus` | `views_finance.contactus` | Constant exists; active call site not found | `api/contactus.php` | Inactive workflow; payload/delivery unverified |

### Confirmed mobile defects

Detailed evidence, severity and recommended fixes for STK-MOB-001 through STK-MOB-011 are recorded in `STOKIT_DEFECT_REGISTER.md`. The important distinction is that static route alignment is not runtime acceptance. No Flutter/PHP source was changed and no live API or database write was performed.


## Order + banner workflow verification — 2026-10-16

- Order create: React `POST /admin-api/orders` sends customer/address fields plus item `{product_id, variant_id, quantity}`. Django `OrderAdminCRUDView.post` recalculates prices from `Product`/`Variant`, validates duplicate lines and variants, and atomically creates checkout, items, and initial status history. Informational note about server-side totals/coordinates is not an API failure. Authenticated database-backed create/list/summary parity remains UNVERIFIED.
- Banner replacement: React `POST /admin-api/uploads` multipart `file` -> `{image_path,url}`, then `PATCH /admin-api/banners` JSON `{id,image_path}`, followed by GET refresh. Upload and patch unit tests pass. Confirmed non-debug contract gap: a locally stored file is serialized using the legacy-host URL when `DEBUG=False`, while `/admin/manage/uploads/...` is only registered for `DEBUG=True`. Production media serving URL/configuration must be established before marking reload/serving as verified.
