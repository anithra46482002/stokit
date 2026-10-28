# StokIt Cart Discount, Target Scheme and Image Upload — Isolated Integration Test Plan

**Date:** 2026-10-16 | **Status:** PREPARED; execution BLOCKED pending approvals | **Project:** PARTIAL

## Isolation prerequisites

Use only a disposable PostgreSQL test database and temporary media directory; never target stokit_postgres_dev. Legacy model mappings use managed=False, so the standard Django test DB may not create required legacy tables. Approve and prepare a minimal fixture schema, prove the connection cannot reach the main target, and use synthetic rows only. Approval is required for test DB create/drop and fixture DDL, fixture DML/rollback, temporary media writes/reads/cleanup, authorized account or synthetic-principal strategy, and business discount policy. No accounts or cleanup until approved.

## Acceptance matrix — every item below remains BLOCKED until actually run

| ID | Test | Required assertion | Status |
|---|---|---|---|
| TS-INT-01 | POST /admin-api/targets with an isolated category ID | 201; response and re-fetched row retain numeric category ID | BLOCKED — no isolated DB run |
| TS-INT-02 | PATCH existing isolated target with another valid category | 200; re-fetch proves category/name persisted | BLOCKED — no isolated DB run |
| TS-INT-03 | POST/PATCH target with nonexistent category | Validation error; no row mutation | BLOCKED — no isolated DB run |
| TS-INT-04 | Browser category list has >100 categories | Select page 2+ option; network payload uses category ID, not label | BLOCKED — no authenticated browser test |
| IMG-INT-01 | POST valid image to /admin-api/uploads using temporary MEDIA_ROOT | 201; returned path matches an existing stored file | BLOCKED — unit tests only |
| IMG-INT-02 | Request returned image URL through configured media route | 200, correct bytes/content type; separately inspect production media route | BLOCKED — serving not tested |
| IMG-INT-03 | Upload image, POST target, re-fetch; then PATCH to second image | Stored path and reward_image_url match; browser preview updates | BLOCKED — upload-to-target E2E not run |
| IMG-INT-04 | Missing, bad-signature, SVG, >5 MiB upload and unauthorized role | Reject invalid file without writing; unauthorized role gets 403 | BLOCKED — unit tests only |
| CART-INT-01 | Non-VIP, eligible subtotal below threshold | No cart promotion | BLOCKED — API integration not run |
| CART-INT-02 | Eligible subtotal exactly at threshold | Matches owner-approved >= or > rule | BLOCKED — policy pending |
| CART-INT-03 | Eligible subtotal above threshold | Exact approved discount and reconciled line/order totals | BLOCKED — policy pending |
| CART-INT-04 | VIP flag Y and positive percentage | No stacking; VIP discount counted once | BLOCKED — API integration not run |
| CART-INT-05 | Test has_disc, discount_percent, discount_value, product_discount and line_discount separately | Each discounted line excluded even if other fields are zero | BLOCKED — DB/API integration not run |
| CART-INT-06 | Mixed discounted and discount-free cart | Discounted lines unchanged; only eligible lines qualify; totals reconcile | BLOCKED — DB/API integration not run |
| CART-INT-07 | Fixed discount greater than eligible subtotal | If fixed policy approved, cap at eligible subtotal and never create negative total | BLOCKED — policy pending |
| CART-INT-08 | Half-cent amounts, multiple lines, GST/delivery/VIP | Approved rounding point/method applied consistently | BLOCKED — policy pending |
| CART-INT-09 | Client submits forged subtotal/discount | Server derives amounts from fixture DB, ignores client totals | BLOCKED — API integration not run |
| CART-INT-10 | Authenticated GET /api/cart_api_test | Nested response keys/types remain compatible; policy cases pass | BLOCKED — API integration not run |

## Existing regression evidence (not integration evidence)

- React npm test: PASS 27/27; covers category ID vs label, ID normalization and client image type/size validation.
- Focused Django tests: PASS 47/47; covers target validation, upload validation/temp storage, pure discount helpers and legacy response builder.
- Django check: PASS. migrate --check: PASS, no migration applied.
- No authenticated DB-backed target create/update, HTTP media-serving request, or DB-backed cart request was run.

## Execution protocol after approval

1. Verify unique disposable DB identity and prove it is not stokit_postgres_dev.
2. Provision only approved minimal fixture schema and synthetic category/customer/product/variant/cart records; do not import production rows.
3. Use transaction rollback or approved disposable DB lifecycle.
4. Use temporary MEDIA_ROOT and verify served bytes before approved cleanup.
5. Capture sanitized request/status/response, DB assertions, media assertions and browser console/network evidence.
6. Mark only executed rows PASS/FAIL; all others stay BLOCKED.
7. Re-run frontend tests/lint/build and focused Django regressions. Do not claim acceptance without authenticated integration evidence and owner policy sign-off.