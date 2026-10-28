# StokIt Credit Release Audit — Allocation 4
**Audit date:** 2026-10-27  
**Workspace:** `C:\Users\.MSI\Downloads\StokIt Backend`  
**Scope:** Read-only investigation of allocation 4 / user ID 2; no financial records changed.

## Executive finding

The configured Django database returned allocation 4 for user ID 2 as ACTIVE, starting 2026-10-23, with payment amount ₹40,000, bonus percentage 12%, 12 months, monthly credit ₹4,800, total credit ₹57,600, stored used credit ₹0 and stored remaining credit ₹57,600. The database contains **zero** rows in `advance_pay_transactions` for allocation ID 4 or user ID 2, while **12 orders** are associated with that customer's user/email mapping.

The original runtime issue was a stale Django process using `--noreload`; after explicit authorization it was replaced by PID 18036 at 17:20:24 on 2026-10-27, after the relevant source files were modified. Startup and Django system checks pass. This establishes that the new process starts from the current workspace, but API-level credit verification remains blocked because no authorized customer or admin session/credential was available to Cody.

Authenticated verification remains incomplete: unauthenticated GET requests returned HTTP 401 for both requested endpoints. No authentication bypass was attempted, no token was found or printed, and no customer/admin session was substituted.

## Runtime and source evidence

- Django system check: `python manage.py check` — **passed**, no issues.
- Original listener before authorized restart: `127.0.0.1:8000`, PID 28704, Python 3.14, command line included `runserver ... --noreload`.
- Original process start: 2026-10-27 14:44:25; replacement listener PID 18036 started at 17:20:24.
- Current source modification times: `django_backend/legacy_api/views_orders.py` — 15:20:46; `django_backend/legacydb/monthly_credit.py` — 15:37:11.
- Current source path: `order_post()` calls `apply_order_credit(user.get("id"), order_id, order_total_before_credit...)` at line 238. The shared helper delegates to `monthly_credit.commit_order_credit(..., record_zero=True)` inside the same `transaction.atomic()` block.
- The canonical ledger reference type in source is `ORDER_BONUS`, not `ORDER`. The database query found no transaction rows for allocation 4 or user 2 at all, so this is not merely a report filter mismatch.
- The live process's loaded Python module/version could not be inspected safely from outside the process; its start-time/file-time comparison is strong evidence of stale loaded code, not direct proof of the exact in-memory bytecode.

## Read-only database findings

Database identity: `stokit_postgres_dev`, schema `public`, PostgreSQL 18.6. This is the database currently configured for the local Django process. Queries were read-only.

### Allocation 4

| Field | Observed value |
|---|---|
| Allocation ID / user ID / offer ID | 4 / 2 / 2 |
| Offer | `special` (from task context; offer row not needed for this audit) |
| Status | ACTIVE |
| Start / end | 2026-10-23 / 2027-10-23 |
| Payment amount / bonus | ₹40,000 / 12% |
| Duration | 12 months |
| Monthly credit (calculated) | ₹4,800 |
| Total credit | ₹57,600 |
| Stored used / remaining | ₹0 / ₹57,600 |
| Ledger rows for allocation 4 or user 2 | 0 |

### Orders associated with user ID 2

The header `zg_checkout.total_amount` is recorded below as the stored order-header amount. Source inspection shows the credit calculation uses a pre-credit amount that includes applicable GST, delivery and VIP discount; therefore this header field must **not** be treated as the definitive credit-eligible purchase amount.

| Order ID | Order date/time (DB local time) | Status | Stored header amount | Allocation date eligible? | Matching ledger row |
|---:|---|---|---:|---|---|
| 947229 | 2026-10-22 07:17:11 | Cancelled | ₹6,010.00 | No — before start | No |
| 783443 | 2026-10-23 05:33:01 | Cancelled | ₹3,000.00 | Date eligible; cancellation policy needs review | No |
| 305461 | 2026-10-23 05:48:02 | Placed | ₹18,070.00 | Yes | No |
| 712282 | 2026-10-23 09:01:49 | Placed | ₹2,708.00 | Yes | No |
| 880624 | 2026-10-26 10:07:47 | Placed | ₹80.00 | Yes | No |
| 136002 | 2026-10-27 08:58:38 | delivered | ₹1,000.00 | Yes | No |
| 161287 | 2026-10-27 09:19:43 | Placed | ₹800.00 | Yes | No |
| 113372 | 2026-10-27 09:37:52 | Placed | ₹800.00 | Yes | No |
| 628034 | 2026-10-27 09:52:15 | Placed | ₹800.00 | Yes | No |
| 239471 | 2026-10-27 09:52:47 | Placed | ₹800.00 | Yes | No |
| 318963 | 2026-10-27 10:15:16 | Placed | ₹400.00 | Yes | No |
| 997028 | 2026-10-27 10:17:46 | Placed | ₹800.00 | Yes | No |

**Counts:** 12 associated orders total; 1 before allocation start; 11 on/after the start date; 2 cancelled overall; 10 non-cancelled orders; 0 matching credit ledger rows. These are order-history classifications, not a claim that all eligible orders should receive a deduction.

## Historical reconciliation assessment — no writes performed

- **Before start:** Order 947229 predates 2026-10-23 and is not eligible for allocation 4. Proposed allocation-4 deduction: ₹0.
- **Cancelled:** Order 783443 was placed on the allocation start date and is now cancelled. Whether its original placement should retain a deduction or cancellation should restore credit is a business-rule question; no historical transaction exists to prove what occurred. Do not assign an amount until this policy is confirmed.
- **Eligible-date orders without ledger rows:** Orders 305461, 712282, 880624, 136002, 161287, 113372, 628034, 239471, 318963 and 997028 are dated within the allocation window and have no matching ledger rows. Their exact historical credit deduction cannot safely be reconstructed from `zg_checkout.total_amount` alone because the source calculates credit against the pre-credit total (including GST/delivery/VIP treatment), and the shared monthly allowance is consumed sequentially. Missing ledger entries are not proof that all ₹4,800 was consumed, nor that each order should be charged.
- **Proposed reconciliation amount:** **Undetermined pending business review and a verified historical calculation**. No rows were inserted, updated, or deleted. No stored allocation balances were changed.

## Files changed

- No application source files changed during this audit.
- This report is a new documentation artifact: `docs/STOKIT_CREDIT_RELEASE_ALLOCATION_4_AUDIT_2026-10-27.md`.

## Verification and limitations

- `python manage.py check`: passed after restart.
- Earlier full backend suite: 575 tests passed, 2 skipped; earlier frontend tests: 114 passed; frontend build passed with a large-chunk warning. These prior results do not verify current API data or historical records.
- Latest focused command: `python manage.py test adminapi.tests_credit_placement adminapi.tests_credit_carry_forward adminapi.tests_monthly_credit adminapi.tests_advance_allocation_ledger --verbosity 1` — **80 tests run, OK, 2 skipped**.
- No live order, test purchase, migration, schema change, or financial record change was performed. The local Django server restart was performed only after explicit user authorization.
- The original stale process PID 28704 was stopped with explicit authorization. The replacement Django development server is listening on 127.0.0.1:8000 as PID 18036, started at 17:20:24 on 2026-10-27, after both relevant source modifications. Startup logs report Django system checks passed and no stderr output.

## Required approvals / next safe steps

1. Restart approval was received and the local Django server was restarted; new PID 18036 is active on 127.0.0.1:8000.
2. Read-only unauthenticated probes returned HTTP 401 for `/api/crd_rel` and `/admin-api/advance-allocations`. Supply/use separately authorized customer and admin sessions to complete the respective GET checks; do not share or log tokens.
3. Use a dedicated authorized test customer only in an explicitly approved isolated environment for end-to-end order/ledger verification. Do not use this customer or production records for test purchases.
4. Decide and document the cancellation/refund credit rule before determining a historical adjustment.
5. Review the order-level calculations with authorized business/finance personnel. Execute any historical ledger reconciliation only after separate explicit financial approval.


## Post-restart verification — 2026-10-27 17:20 local

- Restart: completed after explicit user authorization; old PID 28704 stopped, new listener PID 18036. No React restart.
- New server startup: Django 6.0.9, settings `config.settings`; startup output reports `System check identified no issues (0 silenced)`. Startup stderr log was empty. Logs are in the user's local `%TEMP%` directory and were not added to the workspace.
- Port checks: Django `127.0.0.1:8000` listening on PID 18036; React port 5173 still listening on PID 5576.
- HTTP probes: Django root returned 404 (no root route expected from this probe); `GET /api/crd_rel` returned 401 without credentials; `GET /admin-api/advance-allocations` returned 401 without credentials; React root returned 200. The two API routes are reachable, but authenticated customer credit values and admin allocation list have **not** been verified. No token was obtained, printed, or substituted.
- Django system check passed after restart. Focused credit tests: 80 tests run, OK, 2 skipped.
- No order was created; no migration/schema/database change or historical financial record mutation was performed.
- The 8 established TCP connections observed on port 8000 after a 25-second wait were local client connections; they were not individually attributable to active HTTP requests. Restart proceeded only after explicit authorization.


## Requested read-only verification after restart — 2026-10-27

### Customer credit API — BLOCKED by missing authorized session

- Request attempted without credentials: `GET http://127.0.0.1:8000/api/crd_rel` → **HTTP 401 Unauthorized**. This confirms the endpoint is reachable, not that its payload is correct.
- Needed to complete: an already-authenticated customer session for the affected customer, or a customer bearer credential supplied through a secure local mechanism accessible to Cody. Do not paste tokens into chat or logs. No token was found/printed, and no authentication bypass or credential reset was attempted.
- Therefore allocation 4's API fields (`monthly_credit_release`, `total_credit`, `monthly_used_credit`, `monthly_remaining_credit`, `used_credit`, `remaining_credit`, and per-order `credit_applied`) have **not** been independently verified from the live customer response. Existing read-only DB audit values are recorded above, but are not a substitute for the API response.

### Admin allocation API — BLOCKED by missing separate admin session

- Request attempted without credentials: `GET http://127.0.0.1:8000/admin-api/advance-allocations` → **HTTP 401 Unauthorized**. This confirms the route is reachable, not that allocation 4 appears in the authenticated response.
- Needed to complete: a separately authenticated admin session with the `advance_payments` resource permission, or an authorized admin bearer credential available locally. Customer credentials must not be used here. No bypass was attempted.
- Source inspection confirms `AdvanceAllocationAdminView.get()` computes lifetime `used_credit` from valid ledger `CREDIT_USED` rows (excluding manual adjustment usage), computes `remaining_credit` from total credit less usage plus/minus manual balance adjustments, and exposes `stored_*` values plus `ledger_matches_stored` to reveal cache drift. Runtime values were not verified due to the 401.

### Ledger/order classification from existing read-only database audit

- Allocation 4: ACTIVE, start 2026-10-23; calculated monthly allowance ₹4,800; total lifetime credit ₹57,600; stored used ₹0 and stored remaining ₹57,600. Existing query found zero `advance_pay_transactions` rows for allocation 4 or user ID 2.
- Order 947229 (2026-10-22, Cancelled, header ₹6,010): **before allocation start date**; not eligible for allocation 4. No ledger row.
- Order 783443 (2026-10-23, Cancelled, header ₹3,000): **cancelled; business-rule review required**. No ledger row. Cancellation/refund policy is not implemented by the current credit tests; no retroactive adjustment is authorized.
- Orders 305461 (Placed, 2026-10-23, header ₹18,070), 712282 (Placed, 2026-10-23, header ₹2,708), 880624 (Placed, 2026-10-26, header ₹80), 136002 (delivered, 2026-10-27, header ₹1,000), 161287 (Placed, ₹800), 113372 (Placed, ₹800), 628034 (Placed, ₹800), 239471 (Placed, ₹800), 318963 (Placed, ₹400), and 997028 (Placed, ₹800): **eligible by date, but missing ledger row** according to the existing read-only audit. These header amounts are not verified final credit-eligible totals; source rules calculate purchase value from order items, discounts, stored GST snapshot where available, delivery, and VIP discount. Per-order final eligible totals were not established in this verification.
- No order had a matching positive or explicit zero-value ledger row in the earlier audit; thus no order can be classified as “zero-credit order with explicit zero-value ledger record” based on available results. The missing ledger rows do not prove that every order should consume credit.
- Transaction type/reference type/reference ID/allocation ID: no transaction rows existed in the earlier read-only query for allocation 4 or user ID 2, so there are no row values to report. Current source uses `CREDIT_USED` plus `ORDER_BONUS` for order ledger entries and uses the order ID as `reference_id`.
- No historical entries or allocation balances were changed. Historical reconciliation amounts remain undetermined pending verified order-level calculations and cancellation policy review.

### Idempotency — source and test evidence

- Source `legacydb/monthly_credit.py` (`commit_order_credit`) locks the customer and allocation before reading usage, searches for an existing `CREDIT_USED` row keyed by order reference type and order ID, and returns the existing deduction as a duplicate instead of inserting a second row. Order placement uses `record_zero=True` so a zero-credit order receives a zero-value marker row and cannot be charged later on repeated confirmation. The placement integration wraps order creation and credit application in a transaction.
- Existing tests explicitly cover duplicate order submissions, duplicate confirmations, repeated summary reads, zero-credit marker behavior, rollback after a failure, and cancellation not changing the credit ledger. The focused suite above passed. PostgreSQL concurrency tests are skipped/unverified; no concurrency or rollback tests were run against the protected development database.

### Current blocker and exact next requirement

Provide access to an already-authorized customer session for `/api/crd_rel` and a separately authorized admin session for `/admin-api/advance-allocations` through Cody's existing local browser/session or a secure local credential mechanism. If neither exists, this API verification must remain blocked. No restart, order creation, migration, schema change, database write, or historical financial adjustment was performed in this verification.


## Follow-up: authenticated session availability inspection — 2026-10-27

- Checked Cody's available browser integration command against the running admin frontend at `http://127.0.0.1:5173/`. Cody's Playwright browser command is not available in this environment (`playwright-cli not found on PATH`). Therefore Cody cannot inspect an already-authenticated browser profile or reuse its session here. No new browser, login, or account session was created.
- Source inspection confirms the admin frontend uses `sessionStorage` keys for its admin session and sends a bearer token through its API interceptor. The token value was not read, printed, copied, or logged. Admin login route in the existing UI is `/login`; allocation list route/API is `/admin-api/advance-allocations`, and the API requires the `advance_payments` resource permission.
- Customer route `/api/crd_rel` uses the legacy bearer-auth wrapper. No accessible authenticated customer browser/device session was exposed to Cody. No token was obtained from local storage, environment files, or browser data.
- **Manual action needed:** (1) Open `http://127.0.0.1:5173/login` in the user's normal browser and sign in with an existing authorized admin account that has `advance_payments` permission; then open the Advance Allocations page and inspect allocation ID 4. (2) Open the existing StokIt customer app/session already signed in as the affected customer and open its Credit Release view to confirm the customer response. Keep both sessions on their correct roles; do not share tokens or cookies. (3) To let Cody finish the raw GET/API-to-ledger comparison, make those already-authorized sessions available through a supported Cody browser/session integration; this environment's Playwright CLI is unavailable, so merely signing in to a separate ordinary browser does not make its session accessible to Cody. If that integration cannot be provided, share only the non-secret response fields / screenshots from the authenticated pages, with tokens, cookies, and personal secrets redacted.
- No server was restarted or stopped; Django PID 18036 and React PID 5576 remain listening. No API authentication was bypassed, no credentials were requested or reset, and no database writes were performed. Authenticated API verification remains **BLOCKED**, not complete.
