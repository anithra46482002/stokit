# STOKIT Authenticated Acceptance-Test Plan

Date: 2026-10-16 | Scope: planning document only | Status: **NOT EXECUTED — authenticated CRUD is not verified**

Labels: **VERIFIED** = read or observed in source/evidence in this session; **HISTORICAL** = reported by earlier sessions, not re-run; **PLANNED** = a test not yet run; **SUSPECTED** = needs source verification and an owner decision.

This document creates no accounts, roles, fixtures, databases or tests, and changes no code or permissions. Location note: the task named `docs/`; the file sits beside its sibling reports in `django_backend/docs/`.

## 1. Existing evidence, stated accurately

| Evidence | Status | Source / limits |
|---|---|---|
| 24 admin endpoints returned HTTP 401 without credentials | HISTORICAL | 2026-10-16 master completion pass. `adminapi/urls.py` declares 26 routes; which 24 were probed is not itemised in the evidence, so two routes (likely `auth/login`, which is public, and one other) are not accounted for. |
| Garbage, empty, Basic and `alg=none` tokens returned 401; unauthenticated POST/PUT/DELETE on 4 resources returned 401; `auth/login` with empty body returned 400; a nonexistent login returned 401 | HISTORICAL | Same pass. Valid-token behaviour not exercised. |
| CORS: allowed origin receives `Access-Control-Allow-Origin`; `http://evil.example` does not | HISTORICAL | Same pass. |
| Browser checks: headless Chrome 155 loaded `/`, `/login`, `/orders`, `/no-such-page`; each rendered the login screen; 0 console errors | HISTORICAL | **Page-load checks only.** No form input, login, session persistence, logout or CRUD was exercised. Artefacts remain in `%TEMP%\stokit_chrome_eval_20261016` and `%TEMP%\stokit_e2e_20261016` (previously reported; existence of both directories re-observed today). |
| Backend tests: 93 passed, 1 expected failure (isolated DB `stokit_schema_validation_20261015_2`); earlier run 86 passed | HISTORICAL | Reported by the 2026-10-16 master pass. **The owner states full backend tests were not run in the latest session; they are not re-run in this task.** |
| Frontend tests: 15 passed; build and lint passed | HISTORICAL | Not re-run in this task. |
| Authenticated CRUD (any role, any resource) | **NOT VERIFIED** | `admins` has 0 rows; no account was permitted. |
| Interactive browser login/CRUD | **NOT VERIFIED** | `playwright-cli` was unavailable; nothing installed. |

## 2. Suspected permission defect: POST/DELETE on `orders`

**Observation.** `adminapi/permissions.py` (`AdminRolePermission`, VERIFIED read today) grants POST and DELETE only when `resource in {'catalogue','customers','banners','notifications','warehouse','staff','advance_payments','targets','locations'}` and the role is `SUPER_ADMIN` or `ADMIN`. `orders` is not in that fixed set, so any POST or DELETE on a view that uses `AdminRolePermission` with `required_resource = "orders"` returns 403 for **every** role, including `SUPER_ADMIN`. The same rule denies POST/DELETE for `dashboard`, `inventory` and `reports`.

**What source verification shows (VERIFIED by reading source today):**
- `OrderAdminCRUDView` (`/admin-api/orders`, `crud.py:750`) uses `AdminRolePermission` but defines only `get` and `patch`. A POST or DELETE would therefore be refused by permission (403) before reaching method dispatch, and no handler exists to run anyway.
- Order creation and deletion in the React UI use other routes with a different permission class, `OrderActionPermission` (`order_pages.py:68`): `POST /orders/bulk-assign`, `DELETE /orders/<id>/detail`, `PATCH /orders/<id>/detail` (default write roles `SUPER_ADMIN` and `ADMIN`), and `POST /orders/<id>/status` (all five roles). The Orders module in `App.jsx` is flagged `updateOnly: true`; `OrdersPage.jsx` and `OrderDetailPage.jsx` call the `/detail` route for deletion.
- `inventory` has only GET and PATCH handlers (`operations.py`); `reports` only GET; `dashboard` only GET.

**Assessment.** *Suspected permission defect, partly explained:* the fixed resource list is a latent inconsistency, because `AdminRolePermission` denies `orders` writes for everyone while `OrderActionPermission` permits them for admins on the sibling routes. Whether this is a defect or deliberate policy depends on intent. Nothing in the current UI reaches the denied path.

**Policy decisions required (owner):**
1. Should orders be creatable or deletable at all through `/admin-api/orders`? (Orders originate from Flutter checkout.)
2. If deletion is allowed, which roles may delete orders, and should deletion be a soft delete or cancellation instead of removing `zg_order_items`, `zg_order_status_history` and `zg_checkout` rows (current `/detail` DELETE hard-deletes all three in one transaction)?
3. Should the two permission classes be unified so one table of role → method → resource governs everything?

**Plan impact:** tests AT-PERM-20 to AT-PERM-24 below capture current behaviour as a baseline. **No permission is changed by this document.**

## 3. Role and permission matrix (derived from source)

Derived from `ROLE_RESOURCES` and `AdminRolePermission`/`OrderActionPermission`. **VERIFIED by reading; behaviour PLANNED to be confirmed with real tokens.** G = GET allowed, W = writes allowed per method rules, – = 403 expected.

| Resource (route) | SUPER_ADMIN | ADMIN | SALESMAN | WAREHOUSE_STAFF | DELIVERY_BOY |
|---|---|---|---|---|---|
| dashboard | G | G | G | G | G |
| catalogue: categories, subcategories, products, product-variants, product-images, uploads | G, W | G, W | – | G only | – |
| customers | G, W (POST/PATCH/DELETE) | G, W | G, PATCH only | – | – |
| orders (`/orders`) | G, PATCH status (all statuses) | same | G, PATCH (Placed, Processing) | G, PATCH (Processing, Shipped) | G, PATCH (Out for Delivery, Delivered) |
| orders (`/orders/manage`, `/detail` GET) | G | G | G | G | G |
| orders (`/detail` PATCH/DELETE, `/bulk-assign`) | W | W | – | – | – |
| orders (`/<id>/status` POST) | W | W | W (role rules apply) | W (role rules apply) | W (role rules apply) |
| banners, notifications | G, W | G, W | – | – | – |
| warehouses | G, W | G, W | – | G only | – |
| inventory | G, PATCH | G, PATCH | – | G, PATCH | – |
| reports | G | G | G | – | – |
| staff, locations, targets | G, W | G, W | – | – | – |
| advance-payments / advance-allocations | G, W | G, W | – | – | – |
| cart-discount-settings | G, PUT | G, PUT | – | – | – |

Points to confirm: `advance-payments` (`offers.py`) was not read for its permission class today (UNRESOLVED; test AT-PERM-30); `/orders/<id>/status` role rules after line 370 of `order_pages.py` were not read in full.

## 4. Test matrix

Columns: ID | Requirement/trace | Steps | Expected | Source ref | Status (all PLANNED unless stated). Priority: P0 must pass for acceptance; P1 should; P2 nice.

### 4.1 Authentication (`accounts`, `adminapi/views.py`, `tests_auth.py`)

| ID | Test | Expected | P |
|---|---|---|---|
| AT-AUTH-01 | Login valid credentials, each of 5 roles | 200; token; role matches assignment | P0 |
| AT-AUTH-02 | Login wrong password | 401; no token; generic message | P0 |
| AT-AUTH-03 | Login nonexistent user | 401; message indistinguishable from AT-AUTH-02 (no user enumeration) | P0 |
| AT-AUTH-04 | Login empty/missing fields | 400 | P1 |
| AT-AUTH-05 | Valid credentials, no active role assignment | 403 and no token (see `test_valid_credentials_without_active_role_return_403_without_token`) | P0 |
| AT-AUTH-06 | Deactivated staff account logs in | refused | P0 |
| AT-AUTH-07 | Repeated failed logins | document behaviour (lockout or throttle?) — **policy decision, none is known to exist** | P1 |
| AT-AUTH-10 | No Authorization header on each protected route | 401 with Bearer challenge | P0 |
| AT-AUTH-11 | Malformed header (`Bearer`, `Token x`, double spaces, empty bearer) | 401 | P0 |
| AT-AUTH-12 | Garbage/random token, `alg=none` style token | 401 | P0 |
| AT-AUTH-13 | Tampered token (flip one character of payload/signature; swap role claim) | 401, role not elevated | P0 |
| AT-AUTH-14 | Expired token (token `max_age` exceeded; use a short test setting in the disposable env) | 401 | P0 |
| AT-AUTH-15 | Refresh with valid token (`auth/refresh`) | new token, same principal and role | P0 |
| AT-AUTH-16 | Refresh with no/expired token | 401 | P0 |
| AT-AUTH-17 | Token for a role whose assignment was revoked after issue | 401/403 (role lookup is fail-closed) | P0 |
| AT-AUTH-18 | Token issued to a Flutter customer used on `/admin-api/` | 401/403 | P0 |
| AT-AUTH-19 | Database failure during role lookup | no successful login (see `test_strict_role_lookup_propagates_database_failure_for_login`) | P1 |
| AT-AUTH-20 | Credentials or tokens appear in responses, logs or console | never | P0 |

### 4.2 Role denial and protected writes

For each row in section 3, one allowed and one denied probe per role and method. Execute as a generated grid (resource × role × {GET, POST, PATCH/PUT, DELETE}) and compare with section 3.

| ID | Test | Expected | P |
|---|---|---|---|
| AT-PERM-01 | Full grid for catalogue routes | matches section 3 | P0 |
| AT-PERM-02 | Full grid for customers | matches section 3 | P0 |
| AT-PERM-03 | Full grid for banners, notifications, warehouses, staff, locations, targets | matches section 3 | P0 |
| AT-PERM-04 | Inventory PATCH by WAREHOUSE_STAFF allowed, by SALESMAN denied | matches | P0 |
| AT-PERM-05 | cart-discount PUT by ADMIN allowed; by others 403 | matches | P0 |
| AT-PERM-06 | `uploads` POST by ADMIN allowed; by WAREHOUSE_STAFF/SALESMAN/DELIVERY_BOY 403 | matches | P0 |
| AT-PERM-07 | ADMIN creates a staff row with role `SUPER_ADMIN` | **decision**: ADMIN must not be able to self-escalate; record actual result | P0 |
| AT-PERM-08 | ADMIN edits or deletes the SUPER_ADMIN row | record actual result; decision | P0 |
| AT-PERM-09 | A user changes own role or deletes own account | record; decision | P1 |
| AT-PERM-10 | IDOR: SALESMAN reads customers/orders outside any intended scope | **decision**: no per-salesman scoping exists in `ROLE_RESOURCES`; record | P1 |
| AT-PERM-20 | `POST /admin-api/orders` as each role | 403 for all (baseline of section 2) | P0 |
| AT-PERM-21 | `DELETE /admin-api/orders?id=` as each role | 403 for all (baseline) | P0 |
| AT-PERM-22 | `DELETE /admin-api/orders/<id>/detail` as SUPER_ADMIN/ADMIN | 204; related status-history, items and checkout rows removed in one transaction | P0 |
| AT-PERM-23 | Same as SALESMAN/WAREHOUSE_STAFF/DELIVERY_BOY | 403, order intact | P0 |
| AT-PERM-24 | `POST /orders/bulk-assign` by ADMIN allowed, others 403 | matches | P0 |
| AT-PERM-25 | `PATCH /orders` status by role matches `allowed_by_role` (crud.py:791) | 403 `This role cannot set the requested order status` for out-of-role statuses | P0 |
| AT-PERM-30 | Permission class and role gating of `advance-payments` (`offers.py`) | matches section 3 once read; **UNRESOLVED** | P0 |

### 4.3 Active React pages and their APIs

Pages come from `admin_frontend/src` (VERIFIED today). Each page: load, list, search, pagination (`page_size` max 100), create, edit, delete, validation errors, empty state, error state, double-submit, session expiry mid-action.

| ID | Page (module key) | API calls (from source) | Acceptance criteria |
|---|---|---|---|
| AT-UI-01 | Login (`/login`) | `POST auth/login` | Valid login lands on `/`; invalid shows error; no token in URL; refresh keeps session; logout clears session; direct URL to a page when logged out redirects to `/login` |
| AT-UI-02 | Dashboard (`/`) | `GET dashboard` | Totals match direct SQL on the disposable DB; each role sees only permitted widgets |
| AT-UI-03 | Categories | `GET/POST/PATCH/DELETE categories` | CRUD works; duplicate name handled; delete of a category with subcategories/products refused cleanly |
| AT-UI-04 | Sub Categories | `subcategories` | Same; parent category required |
| AT-UI-05 | Products | `products`, `product-images`, `product-variants`, `uploads` | Create with images and variants; toggle visibility (PATCH `visible`); delete cascades or is refused as designed |
| AT-UI-06 | Product variants | `product-variants` | CRUD; price/stock numeric validation; variant belongs to product |
| AT-UI-07 | Customers | `customers` | CRUD; email/phone validation; delete of referenced customer returns 409 `customer_referenced`; no password hash in responses |
| AT-UI-08 | Orders list | `GET orders/manage`, `POST orders/bulk-assign` | Filters (dates, status), statistics match rows, bulk-assign works for admins only |
| AT-UI-09 | Order detail | `GET/PATCH/DELETE orders/<id>/detail`, `POST orders/<id>/status` | Edit address/items recomputes `grand_total`; status transitions per role; delete behaviour per section 2 |
| AT-UI-10 | Banners | `banners`, `uploads` | Upload then create; patch image; delete |
| AT-UI-11 | Notifications | `notifications` | Create and delete; pagination |
| AT-UI-12 | Warehouse | `warehouses` | CRUD; delete guarded when referenced |
| AT-UI-13 | Inventory | `inventory` | PATCH stock; negative or non-numeric rejected |
| AT-UI-14 | Cart Discount | `GET/PUT cart-discount-settings` | Valid and invalid values; only SUPER_ADMIN/ADMIN write; row persisted in `admin_cart_discount_settings` |
| AT-UI-15 | Staff | `staff` | CRUD; password never returned; role assignment rules (AT-PERM-07/08) |
| AT-UI-16 | Advance Payments (+ new offer form) | `advance-payments`, `advance-allocations` | Offer CRUD, multipart upload, allocation add/adjust/delete |
| AT-UI-17 | Locations | `locations` | CRUD; duplicate city per the collation policy (see `STOKIT_CITY_NAME_COLLATION_FINAL_REVIEW.md`); search; delete guard |
| AT-UI-18 | Target Schemes | `targets` | CRUD; progress fields |
| AT-UI-19 | Reports | `reports` | Role visibility; numbers reconcile with source tables |
| AT-UI-20 | Unknown route | — | Redirects to `/`, or `/login` when logged out |

### 4.4 Uploads

| ID | Test | Expected |
|---|---|---|
| AT-UPL-01 | Valid JPG/PNG/GIF/WEBP ≤ 5 MB | 201, `{image_path: "uploads/<uuid>.<ext>", url}`; file readable at `url` |
| AT-UPL-02 | Extension/content mismatch (e.g. `.png` containing text) | 400 |
| AT-UPL-03 | > 5 MB | 400 |
| AT-UPL-04 | Disallowed extension (`.svg`, `.php`, `.html`), double extension, no extension | 400; nothing written |
| AT-UPL-05 | Path traversal in filename | stored name is a generated UUID; no write outside `MEDIA_ROOT/uploads` |
| AT-UPL-06 | Missing `file` field | 400 |
| AT-UPL-07 | Role denial (non-admin) | 403 |

### 4.5 Transaction rollback and partial failure

| ID | Test | Expected |
|---|---|---|
| AT-TXN-01 | Product create with images/variants where the variant is invalid | no orphan product, images or variants |
| AT-TXN-02 | Order detail PATCH where item update fails midway | order and totals unchanged |
| AT-TXN-03 | Order DELETE interrupted (simulated failure after history delete) | all-or-nothing; order intact |
| AT-TXN-04 | Bulk-assign with one invalid order id | defined behaviour: all or nothing, documented |
| AT-TXN-05 | Customer delete when referenced | 409; no partial delete |
| AT-TXN-06 | Checkout failure after stock decrement | stock and cart consistent; no half-written order |
| AT-TXN-07 | Upload succeeds but record save fails | orphan file policy documented |
| AT-TXN-08 | Advance-allocation adjust partially fails | balance and transaction log consistent |

### 4.6 Concurrency and order-ID collisions

`views_commerce.checkout` allocates a six-digit order id and retries on actual primary-key collisions inside a savepoint (regression test exists per the execution report, HISTORICAL).

| ID | Test | Expected |
|---|---|---|
| AT-CON-01 | N parallel checkouts (e.g. 20) for different customers | all succeed, unique order ids, no 5xx |
| AT-CON-02 | Force an id collision (seed a row holding the next candidate) | retry succeeds; no duplicate; no aborted transaction |
| AT-CON-03 | Same customer double-submits checkout | defined behaviour; no double charge/duplicate order |
| AT-CON-04 | Two checkouts compete for the last unit of stock | one succeeds; stock never negative |
| AT-CON-05 | Concurrent PATCH of the same order by two staff | last-write behaviour documented; no corrupted totals |
| AT-CON-06 | Concurrent bulk-assign and delete | no orphan rows |
| AT-CON-07 | External PHP writer (if still live) and Django both allocate ids | **cannot be tested here**; the PHP path does not share the retry logic (open risk) |

### 4.7 Flutter endpoint compatibility (`/api/`, `legacy_api/urls.py`)

Flutter source and API contracts must not change. Base URL in Flutter is `https://app.stokitb2b.com/api` (VERIFIED today). Routes (VERIFIED from `urls.py`): `login`, `logout`, `profile`, `geocode`, `banner`, `category`, `sub_categories`, `getCategory`, `search`, `highlights`, `recommended`, `product-api`, `fav`, `favpage`, `cart_action`, `product-api-cart`, `cart_api_test`, `checkout`, `noti_list`, `notification_action`, `notify`, `order_post`, `orders`, `order_details`, `order_cancel`, `acc/`, `acc/reset`, `saveCheck`, `targets`, `coabout`, `advancePay-api`, `crd_rel`, `contactus`.

| ID | Test | Expected |
|---|---|---|
| AT-FLT-01 | For every route, compare response **keys**, nesting, and ordering of arrays against PHP-recorded samples or the existing `legacy_api/tests_contract.py` | identical keys; no renamed or dropped fields |
| AT-FLT-02 | Data types per field (string vs number vs null vs "0"/"1" strings), decimals as strings or numbers exactly as PHP returned | identical types |
| AT-FLT-03 | Status codes for success, validation error, not found, unauthorised, per route | same as PHP behaviour recorded in the contract |
| AT-FLT-04 | Ownership: a customer cannot read or cancel another customer's orders, cart, favourites, profile (`orders`, `order_details`, `order_cancel`, `fav`, `favpage`, `cart_action`, `profile`) | 403/404 or empty per contract; never another user's data |
| AT-FLT-05 | Authentication parity: which routes need a token; behaviour of `logout` | as PHP |
| AT-FLT-06 | Image URLs in every payload (`banner`, `category`, `product-api`, `highlights`, `recommended`, `search`, `cart`, `order_details`) | absolute URLs built from `LEGACY_BASE_URL`; resolve to HTTP 200 images; same scheme/host Flutter expects |
| AT-FLT-07 | Cart → checkout → order → cancel round trip with a synthetic customer | totals, discounts (including `admin_cart_discount_settings`), stock and status history correct |
| AT-FLT-08 | Password reset (`acc/`, `acc/reset`) | token flow and expiry as PHP; no token leakage; email transport is stubbed |
| AT-FLT-09 | Unicode and special characters in search, address and city | round-trips unchanged |
| AT-FLT-10 | Large result sets and pagination parameters | same defaults as PHP |
| AT-FLT-11 | Admin changes (status, price, stock, banner) become visible to Flutter endpoints | consistent |

### 4.8 Browser-driven acceptance (requires approved automation tool)

| ID | Flow | Acceptance |
|---|---|---|
| AT-BRW-01 | Login form validation (empty, wrong, right) per role | messages shown; correct landing; role-appropriate sidebar |
| AT-BRW-02 | Session persistence on reload; logout; back button after logout | session cleared; protected pages inaccessible |
| AT-BRW-03 | Expired token during use | redirected to login without data loss warnings or loops |
| AT-BRW-04 | Full CRUD per page in section 4.3 with real clicks and dialogs | create, edit, delete appear in the list and in the database |
| AT-BRW-05 | Console and network panel during every flow | 0 errors; no 5xx; no credentials in URLs or logs |
| AT-BRW-06 | Image upload through the UI, then display | image renders |
| AT-BRW-07 | Responsive layout and keyboard navigation (basic) | usable at tablet and phone widths |
| AT-BRW-08 | Cross-role UI: hidden or disabled controls match section 3 | consistent with API denial |

## 5. Safe execution sequence

**Stage 0 — read-only (no approval beyond this task; already allowed)**
1. Re-read this plan, `permissions.py`, `order_pages.py`, `offers.py` (to close AT-PERM-30).
2. Confirm which servers are running; do not restart them.

**Stage 1 — approvals required from the owner (none granted yet)**
1. Create an isolated disposable PostgreSQL test database (for example `stokit_accept_test_<date>`); never use `stokit_postgres_dev` for synthetic CRUD.
2. Approve provisioning of schema and migrations **in that database only** (the validated candidate DDL plus Django migrations).
3. Approve creation of synthetic fixtures: one account per role, and minimal catalogue, customer, order, warehouse data.
4. Approve a browser automation tool and the test-execution scope (which sections of this plan).

**Stage 2 — execute in this order after approval** (each stage must pass before the next)
1. Backend automated suite against the disposable DB (full run; record counts).
2. Section 4.1 authentication.
3. Section 4.2 permission grid.
4. Section 4.3 and 4.4 API CRUD per resource, then uploads.
5. Section 4.5 rollback and 4.6 concurrency.
6. Section 4.7 Flutter contract.
7. Section 4.8 browser flows.
8. Frontend tests, build, lint.

**Stage 3 — wrap-up.** Record results, then ask separately for approval to drop the disposable database and fixtures.

**Do not:** run anything against `stokit_postgres_dev`, import historical data, create accounts there, or modify PHP/Flutter sources.

## 6. Results template

Copy one row per executed test.

| ID | Date/time | Env (DB, build) | Role | Request/UI action | Expected | Actual (status, key fields) | Result (PASS / FAIL / BLOCKED) | Evidence path | Defect ref | Notes |
|---|---|---|---|---|---|---|---|---|---|---|

Summary block per run: tests planned, executed, passed, failed, blocked; backend suite count; frontend suite count; open defects; policy decisions pending; sign-off name and date.

Acceptance rule: all P0 rows PASS, all P1 rows PASS or have an owner-accepted waiver, and every "decision" row has a recorded owner decision.

NOT EXECUTED: every test in this document.
