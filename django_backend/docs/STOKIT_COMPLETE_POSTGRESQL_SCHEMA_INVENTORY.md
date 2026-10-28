# StokIt Complete PostgreSQL Schema Inventory

Status: REVIEW ONLY — NOT APPROVED FOR EXECUTION

## Source evidence

Source: STOKIT_SOURCE_SCHEMA_INVENTORY.md. It reports 45 source tables, 92 ALTER TABLE statements, 39 INSERT statements, and one trigger. No source rows are to be imported.

## Table scope classification

| Table | Classification | Target status / note |
|---|---|---|
| a_cart | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| admins | PROPOSED_PENDING_EVIDENCE | Existing target table; preserve. |
| advance_pay_allocations | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| advance_pay_offers | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| advance_pay_transactions | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| category_view | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| delivery_boys | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| notifications | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| salesmen | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| users | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| users1 | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| warehouse_delivery_boys | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| warehouse_salesmen | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_api_keys | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_banner | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_brands | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_category | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_checkout | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_cod | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_discount_banners | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_favorites | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_headings | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_headings_new | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_location | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_logo | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_order_items | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_order_status_history | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_product | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_product_images | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_product_warehouse | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_reels | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_slider | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_social_media | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_stock_log | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_subcategory | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_target_achievements | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_target_activity_log | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_target_assignments | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_targets | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_testy | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_vari_product | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_vari_product_images | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_vari_variant | EXCLUDED_PENDING_DEPENDENCY_REVIEW | Excluded pending dependency review. |
| zg_variant | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |
| zg_warehouse | PROPOSED_PENDING_EVIDENCE | Proposed only; evidence/approval required. |

## Explicit excluded-table review

All 16 tables below remain excluded from candidate DDL until their active PHP, API, and frontend dependencies are traced:
- users1 — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_api_keys — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_banner — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_brands — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_cod — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_headings — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_headings_new — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_logo — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_product_warehouse — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_reels — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_social_media — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_target_activity_log — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_testy — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_vari_product — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_vari_product_images — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.
- zg_vari_variant — EXCLUDED_PENDING_DEPENDENCY_REVIEW; verify direct PHP references, API routes, UI calls, FK references, trigger references, and operational owner decision.

## Conversion gaps

- Source column/type/key details are available in the source inventory, but complete PostgreSQL conversion is not approved.
- Do not assume MariaDB collation, ENUM, TINYINT(1), prefix-index, timestamp-update, trigger, JSON, or ID-generation semantics are equivalent.
- Existing target tables admins, admin_cart_discount_settings, and django_migrations must be preserved.
- admins is already present in the target; any definition comparison must be non-destructive and based on the read-only audit.

## Limitations

This inventory classifies all source tables but does not approve any new table. See STOKIT_COMPLETE_SCHEMA_BLOCKERS.md for required evidence and decisions.

## Phase 4 evidence addendum (2026-10-15 21:44:55 +05:30)

### Scan scope and limitations
- Cody workspace verified: C:Users.MSIDownloadsStokIt Backend
- PHP code snapshot scanned: C:Users.MSIDownloadsStokIt_PHP_Backup_20261012Host (153 PHP files). This is a backup snapshot, not confirmed as active PHP source.
- Django scan: 85 Python files in the backend; the reference matrix distinguishes runtime app references from test, migration, and audit-tool references.
- React source scan: 20 JS/JSX/TS/TSX files under admin_frontendsrc.
- Literal table-name matches are evidence of references only; no match is not proof of non-use. API paths can refer indirectly to tables. Existing classifications and approval values remain unchanged.
- Column/key detail below comes from the existing parsed source inventory. The original 134 MB dump was not independently re-parsed in this Phase 4 run.

### Per-table source and code-reference matrix

### a_cart
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (7): id:int(11), cart_id:varchar(50), username:varchar(100), product_id:int(11), variant_id:int(11), qty:int(11), created_at:datetime.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (7): api\cart_action.php; api\cart_api_test.php; api\cart_api_test.-without-vip.php; api\cart_api_test-2.php; api\cart_api_test-suj.php; api\order_post.php; api\product-api-cart.php.
- Django runtime app references (4): adminapi\crud.py; legacy_api\views_cart.py; legacy_api\views_commerce.py; legacy_api\views_orders.py.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### admins
- Classification: PROPOSED_PENDING_EVIDENCE; target status: EXISTING_TARGET_TABLE_PRESERVE; approval: NOT_APPROVED.
- Source columns (11): id:int(11), username:varchar(50), email:varchar(100), fullname:varchar(100), password:varchar(255), phone:varchar(250), address:varchar(250), paymentDate:varchar(255), token:varchar(1000), api_token:varchar(64), last_login:datetime.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (1): admin\manage\login.php.
- Django runtime app references (3): adminapi\order_pages.py; adminapi\tests_auth.py; legacydb\models.py.
- Django test/migration/audit-tool references (3): adminapi\tests_auth.py; legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### advance_pay_allocations
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (17): id:int(11), offer_id:int(11), user_id:int(11), payment_amount:decimal(10,2), bonus_percentage:decimal(5,2), duration_months:int(11), total_credit:decimal(10,2), used_credit:decimal(10,2), remaining_credit:decimal(10,2), start_date:date, end_date:date, status:enum('ACTIVE','EXPIRED','COMPLETED','CANCELLED'), payment_date:date, payment_reference:varchar(255), notes:text, created_at:timestamp, updated_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); INDEX ADD KEY offer_id (offer_id); INDEX ADD KEY user_id (user_id); FOREIGN KEY ADD CONSTRAINT advance_pay_allocations_ibfk_1 FOREIGN KEY (offer_id) REFERENCES advance_pay_offers (id) ON DELETE CASCADE; FOREIGN KEY ADD CONSTRAINT advance_pay_allocations_ibfk_2 FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE.
- PHP backup snapshot references (9): admin\manage\allocate_offer.php; admin\manage\allocated_users.php; admin\manage\allocated_users_back.php; admin\manage\customers.php; admin\manage\delete_offer.php; admin\manage\edit_allocation.php; admin\manage\use_credit.php; admin\manage\view_allocation.php; api\advancePay-api.php.
- Django runtime app references (3): adminapi\bonus_credit.py; legacy_api\views_finance.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### advance_pay_offers
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (10): id:int(11), offer_name:varchar(255), payment_amount:decimal(10,2), bonus_percentage:decimal(5,2), duration_months:int(11), total_credit:decimal(10,2), status:enum('ACTIVE','INACTIVE'), image_path:varchar(255), created_at:timestamp, updated_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (12): admin\manage\add_offer.php; admin\manage\allocate_offer.php; admin\manage\allocated_users.php; admin\manage\allocated_users_back.php; admin\manage\customers.php; admin\manage\delete_offer.php; admin\manage\edit_allocation.php; admin\manage\edit_offer.php; admin\manage\offers_list.php; admin\manage\use_credit.php; admin\manage\view_allocation.php; api\advancePay-api.php.
- Django runtime app references (2): legacy_api\views_finance.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### advance_pay_transactions
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (9): id:int(11), allocation_id:int(11), user_id:int(11), amount:decimal(10,2), transaction_type:enum('CREDIT_USED','CREDIT_ADDED'), reference_id:int(11), reference_type:varchar(50), notes:text, created_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); INDEX ADD KEY allocation_id (allocation_id); INDEX ADD KEY user_id (user_id); FOREIGN KEY ADD CONSTRAINT advance_pay_transactions_ibfk_1 FOREIGN KEY (allocation_id) REFERENCES advance_pay_allocations (id) ON DELETE CASCADE; FOREIGN KEY ADD CONSTRAINT advance_pay_transactions_ibfk_2 FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE.
- PHP backup snapshot references (5): admin\manage\allocate_offer.php; admin\manage\allocated_users.php; admin\manage\allocated_users_back.php; admin\manage\use_credit.php; admin\manage\view_allocation.php.
- Django runtime app references (2): adminapi\bonus_credit.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0003_advancepaytransaction.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### category_view
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (3): id:int(11), user:varchar(255), category_id:int(11).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (2): api\product-api.php; api\recommended.php.
- Django runtime app references (1): legacy_api\views_catalog.py.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### delivery_boys
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (12): id:int(11), username:varchar(50), email:varchar(100), fullname:varchar(100), password:varchar(255), phone:varchar(250), address:varchar(250), paymentDate:varchar(255), token:varchar(1000), api_token:varchar(64), last_login:datetime, created_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); UNIQUE ADD UNIQUE KEY username (username); UNIQUE ADD UNIQUE KEY email (email).
- PHP backup snapshot references (9): admin\manage\delivery.php; admin\manage\delivery_boys.php; admin\manage\O.PHP; admin\manage\order.php; admin\manage\order_details.php; admin\manage\order-before-colour-warehouse-filter.php; admin\manage\req\side_nav.php; admin\manage\theme.php; admin\manage\warehouse_details.php.
- Django runtime app references (2): adminapi\order_pages.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (2): OrderDetailPage.jsx; OrdersPage.jsx.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### notifications
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (9): id:int(11), customer_id:int(11), title:varchar(255), message:text, sent_by:varchar(100), created_at:timestamp, is_read:tinyint(1), read_at:timestamp, recipient_type:varchar(20).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); INDEX ADD KEY customer_id (customer_id); FOREIGN KEY ADD CONSTRAINT notifications_ibfk_1 FOREIGN KEY (customer_id) REFERENCES users (id) ON DELETE CASCADE.
- PHP backup snapshot references (5): admin\manage\notification.php; admin\manage\req\side_nav.php; admin\manage\theme.php; admin\manage\zPolicy.php; api\noti_list.php.
- Django runtime app references (8): accounts\tests_roles.py; adminapi\operations.py; adminapi\permissions.py; adminapi\urls.py; legacy_api\tests_contract.py; legacy_api\tests_postgres_sql.py; legacy_api\views_commerce.py; legacydb\models.py.
- Django test/migration/audit-tool references (5): accounts\tests_roles.py; legacy_api\tests_contract.py; legacy_api\tests_postgres_sql.py; legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (2): App.jsx; NotificationsPage.jsx.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### salesmen
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (14): id:int(11), username:varchar(50), email:varchar(100), fullname:varchar(100), password:varchar(255), phone:varchar(20), address:text, commission_rate:decimal(5,2), hire_date:date, target_sales:decimal(10,2), token:varchar(64), api_token:varchar(64), created_at:timestamp, updated_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); UNIQUE ADD UNIQUE KEY username (username); UNIQUE ADD UNIQUE KEY email (email).
- PHP backup snapshot references (3): admin\manage\req\side_nav.php; admin\manage\salesmen.php; admin\manage\warehouse_details.php.
- Django runtime app references (3): adminapi\crud.py; adminapi\operations.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0002_salesman_target_targetachievement_targetassignment.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (1): App.jsx.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### users
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (31): id:int(11), username:varchar(100), password:varchar(255), email:varchar(255), fullname:varchar(255), shop_name:varchar(255), phone:varchar(20), city:varchar(255), category_id:varchar(125), address:text, status:enum('ACTIVE','INACTIVE','SUSPENDED'), gst:enum('Y','N'), gst_type:enum('REGULAR','COMPOUND'), vip_discount:enum('Y','N'), vip_percentage:decimal(5,2), store_maped:enum('Y','N'), profile_picture:varchar(255), created_at:timestamp, updated_at:timestamp, token:varchar(255), latitude:varchar(125), longitude:varchar(125), gst_number:varchar(20), gst_percentage:decimal(5,2), delivery_charges:decimal(10,2), color_code:varchar(20), warehouse_id:int(11), vip_from_date:date, vip_to_date:date, vip_start_date:date, vip_end_date:date.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); UNIQUE ADD UNIQUE KEY email (email); UNIQUE ADD UNIQUE KEY username (username).
- PHP backup snapshot references (49): admin\manage\acc\index.php; admin\manage\acc\reset.php; admin\manage\addCustomer.php; admin\manage\allocate_offer.php; admin\manage\allocated_users.php; admin\manage\allocated_users_back.php; admin\manage\customers.php; admin\manage\delivery.php; admin\manage\edit_allocation.php; admin\manage\editCustomer.php; admin\manage\get_target_data.php; admin\manage\notification.php; admin\manage\O.PHP; admin\manage\order.php; admin\manage\order_details.php; admin\manage\pass.php; admin\manage\q.php; admin\manage\req\side_nav.php; admin\manage\targets.php; admin\manage\theme.php; admin\manage\use_credit.php; admin\manage\view_allocation.php; admin\manage\warehouse_details.php; admin\manage\welcome.php; admin\manage\welcome-old.php; admin\manage\zPolicy.php; admin\manage\zTerms.php; api\acc\index.php; api\acc\reset.php; api\cart_api_test.php; api\cart_api_test.-without-vip.php; api\cart_api_test-suj.php; api\category.php; api\crd_rel.php; api\geocode.php; api\highlights.php; api\login.php; api\noti_list.php; api\notify.php; api\notify3.php; api\order_cancel.php; api\order_details.php; api\order_details-no-pricing.php; api\order_post.php; api\orders.php; api\profile.php; api\recommended.php; api\targets.php; api\token.php.
- Django runtime app references (13): accounts\models.py; accounts\services.py; adminapi\advance_allocations.py; adminapi\bonus_credit.py; adminapi\operations.py; adminapi\order_pages.py; legacy_api\views_auth.py; legacy_api\views_catalog.py; legacy_api\views_commerce.py; legacy_api\views_finance.py; legacy_api\views_orders.py; legacy_api\views_remaining.py; legacydb\models.py.
- Django test/migration/audit-tool references (9): legacydb\migrations\0001_initial.py; scripts\read_only_audits\dump_integrity_readonly.py; scripts\read_only_audits\fingerprints_readonly.py; scripts\read_only_audits\phase_a_manifest_readonly.py; scripts\read_only_audits\rowcount_reconciliation_readonly.py; scripts\read_only_audits\source_column_diff_readonly.py; scripts\read_only_audits\timestamps_orphans_readonly.py; scripts\read_only_audits\trigger_body_compare_readonly.py; scripts\test_stokit_pg_migration.py.
- React literal table-name references (3): App.jsx; CustomersPage.jsx; NotificationsPage.jsx.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### users1
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (11): id:int(11), username:varchar(50), email:varchar(100), fullname:varchar(100), password:varchar(255), phone:varchar(250), address:varchar(250), paymentDate:varchar(255), token:varchar(1000), api_token:varchar(64), last_login:datetime.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### warehouse_delivery_boys
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (4): id:int(11), warehouse_id:int(11), delivery_boy_id:int(11), created_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); UNIQUE ADD UNIQUE KEY unique_warehouse_delivery_boy (warehouse_id,delivery_boy_id); INDEX ADD KEY warehouse_id (warehouse_id); INDEX ADD KEY delivery_boy_id (delivery_boy_id).
- PHP backup snapshot references (1): admin\manage\warehouse_details.php.
- Django runtime app references (1): adminapi\operations.py.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### warehouse_salesmen
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (4): id:int(11), warehouse_id:int(11), salesman_id:int(11), created_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); UNIQUE ADD UNIQUE KEY unique_warehouse_salesman (warehouse_id,salesman_id); INDEX ADD KEY warehouse_id (warehouse_id); INDEX ADD KEY salesman_id (salesman_id).
- PHP backup snapshot references (1): admin\manage\warehouse_details.php.
- Django runtime app references (1): adminapi\operations.py.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_api_keys
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (12): id:int(11), key_type:enum('captcha','payment'), service_name:varchar(50), key_name:varchar(100), key_value:text, merchant_id:varchar(100), salt_key:varchar(255), payment_mode:enum('test','live'), is_active:tinyint(1), description:text, created_at:timestamp, updated_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); INDEX ADD KEY idx_key_type (key_type); INDEX ADD KEY idx_service (service_name); INDEX ADD KEY idx_active (is_active).
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_banner
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (14): id:int(11), bg_image:varchar(255), timer_days:int(11), timer_hours:int(11), timer_minutes:int(11), timer_seconds:int(11), heading:varchar(255), paragraph:text, button_text:varchar(50), button_link:varchar(255), last_updated:timestamp, view:varchar(255), count:varchar(255), banner_slot:varchar(255).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_brands
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (2): id:int(11), image:varchar(255).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (1): admin\manage\brands.php.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_category
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (4): category_id:int(11), category_name:varchar(255), category_image:varchar(255), category_active:tinyint(1).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (category_id).
- PHP backup snapshot references (1): api\category.php.
- Django runtime app references (3): legacy_api\views_catalog.py; legacy_api\views_remaining.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_checkout
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (18): order_id:int(11), user:varchar(120), full_name:varchar(255), address:varchar(255), city:varchar(100), state:varchar(100), postal_code:varchar(20), country:varchar(100), phone:varchar(20), email:varchar(255), total_amount:decimal(10,2), order_date:datetime, status:varchar(255), delivery_boy_id:int(11), view:varchar(255), payment_method:varchar(255), shipping_charge:varchar(255), cod_charge:decimal(10,2).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (order_id).
- PHP backup snapshot references (14): admin\manage\O.PHP; admin\manage\order.php; admin\manage\order-before-colour-warehouse-filter.php; admin\manage\sales.php; admin\manage\theme.php; admin\manage\warehouse_details.php; admin\manage\welcome.php; admin\manage\welcome-old.php; api\crd_rel.php; api\order_cancel.php; api\order_details.php; api\order_details-no-pricing.php; api\order_post.php; api\orders.php.
- Django runtime app references (4): adminapi\order_pages.py; legacy_api\views_finance.py; legacy_api\views_orders.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_cod
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (8): id:int(11), cod_enabled:enum('Y','N'), charges:decimal(10,2), created_at:timestamp, shipping_type:enum('fixed','price_based'), fixed_shipping_charge:decimal(10,2), min_order_amount:decimal(10,2), shipping_charge_below_min:decimal(10,2).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (1): admin\manage\cod.php.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_discount_banners
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (4): id:int(11), product_id:int(11), image_path:varchar(255), created_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); INDEX ADD KEY product_id (product_id); FOREIGN KEY ADD CONSTRAINT fk_discount_banners_product FOREIGN KEY (product_id) REFERENCES zg_product (product_id) ON DELETE CASCADE.
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (1): legacy_api\views_catalog.py.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_favorites
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (4): id:int(11), user_id:varchar(125), product_id:int(11), created_at:datetime.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); UNIQUE ADD UNIQUE KEY unique_user_product (user_id,product_id).
- PHP backup snapshot references (3): api\favpage.php; api\highlights.php; api\recommended.php.
- Django runtime app references (3): adminapi\crud.py; legacy_api\views_catalog.py; legacy_api\views_favorites.py.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_headings
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (8): id:int(11), heading1:varchar(255), heading2:varchar(255), heading3:varchar(255), heading4:varchar(255), heading5:varchar(255), heading6:varchar(255), heading7:varchar(225).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_headings_new
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (5): id:int(11), name:varchar(255), button_name:varchar(125), image:varchar(500), updated_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (2): admin\manage\editProduct.php; admin\manage\product.php.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_location
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (2): location_id:int(11), city_name:varchar(100).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (location_id); UNIQUE ADD UNIQUE KEY city_name (city_name).
- PHP backup snapshot references (2): admin\manage\editCustomer.php; admin\manage\warehouse.php.
- Django runtime app references (1): adminapi\operations.py.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_logo
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (6): id:int(11), file:varchar(255), type:enum('logo','favicon'), favico:varchar(255), created_at:timestamp, updated_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); INDEX ADD KEY idx_type (type).
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_order_items
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (10): item_id:int(11), order_id:int(11), product_id:int(11), variant_id:int(11), product_name:varchar(255), variant_name:varchar(255), quantity:int(11), price:decimal(10,2), discount:decimal(10,2), total_price:decimal(10,2).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (item_id); INDEX ADD KEY order_id (order_id).
- PHP backup snapshot references (5): api\crd_rel.php; api\order_details.php; api\order_details-no-pricing.php; api\order_post.php; api\orders.php.
- Django runtime app references (4): adminapi\order_pages.py; legacy_api\views_finance.py; legacy_api\views_orders.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_order_status_history
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (5): id:int(11), order_id:int(11), status:varchar(50), changed_at:datetime, message:text.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); INDEX ADD KEY order_id (order_id).
- PHP backup snapshot references (2): api\order_details.php; api\order_details-no-pricing.php.
- Django runtime app references (3): adminapi\order_pages.py; legacy_api\views_orders.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_product
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (41): product_id:int(11), code:varchar(250), stock:varchar(250), product_name:varchar(255), color:varchar(255), product_price:decimal(10,2), mrp:decimal(10,2), product_discount:decimal(10,2), product_description:text, product_keywords:varchar(255), subtitle:varchar(255), brand:varchar(100), youtube_link:varchar(255), share_image:varchar(255), product_details:longtext, additional_details:longtext, moq:int(11), set_of:int(11), quantity_selected:int(11), discount_value:decimal(10,2), discount_percent:decimal(5,2), set_contains:longtext, category_id:int(11), subcategory_id:int(11), top:int(11), hand:int(11), top2:int(11), hand2:int(11), heading5_tag:int(11), heading6_tag:int(11), heading7_tag:int(11), added:varchar(255), view:varchar(255), highlight:tinyint(1), gst_applicable:varchar(1), gst_percentage:decimal(5,2), gst_price:decimal(10,2), has_disc:int(1), warehouse_id:int(11), no_discount_banner:enum('Y','N'), disable_variants:enum('Y','N').
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (product_id); INDEX ADD KEY idx_moq (moq); INDEX ADD KEY idx_brand (brand); INDEX ADD KEY idx_youtube (youtube_link(100)); INDEX ADD KEY subcategory_id (subcategory_id).
- PHP backup snapshot references (5): admin\manage\sub_categories.php; api\favpage.php; api\getCategory.php; api\order_post.php; api\product-api.php.
- Django runtime app references (5): legacy_api\views_catalog.py; legacy_api\views_commerce.py; legacy_api\views_favorites.py; legacy_api\views_orders.py; legacydb\models.py.
- Django test/migration/audit-tool references (3): legacydb\migrations\0001_initial.py; scripts\read_only_audits\dump_integrity_readonly.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_product_images
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (4): image_id:int(11), product_id:int(11), image_path:varchar(255), main:varchar(255).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (image_id).
- PHP backup snapshot references (5): api\favpage.php; api\getCategory.php; api\order_details.php; api\order_details-no-pricing.php; api\orders.php.
- Django runtime app references (6): adminapi\order_pages.py; legacy_api\views_catalog.py; legacy_api\views_commerce.py; legacy_api\views_favorites.py; legacy_api\views_orders.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_product_warehouse
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (3): id:int(11), product_id:int(11), warehouse_id:int(11).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); UNIQUE ADD UNIQUE KEY unique_mapping (product_id,warehouse_id); INDEX ADD KEY warehouse_id (warehouse_id); FOREIGN KEY ADD CONSTRAINT zg_product_warehouse_ibfk_1 FOREIGN KEY (product_id) REFERENCES zg_product (product_id) ON DELETE CASCADE; FOREIGN KEY ADD CONSTRAINT zg_product_warehouse_ibfk_2 FOREIGN KEY (warehouse_id) REFERENCES zg_warehouse (warehouse_id) ON DELETE CASCADE.
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_reels
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (5): id:int(11), url:varchar(500), embed_code:text, thumbnail_url:varchar(500), created_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (1): admin\manage\reels.php.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_slider
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (7): slider_id:int(11), image_path:varchar(255), text_content:text, styled_text:varchar(255), styled_color:varchar(50), back:varchar(255), text_content2:varchar(255).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (slider_id).
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (2): legacy_api\views_catalog.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_social_media
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (5): id:int(11), facebook:varchar(255), instagram:varchar(255), youtube:varchar(255), linkedin:varchar(255).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (1): admin\manage\navbar.php.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_stock_log
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (6): id:int(11), variant_id:int(11), adjustment:int(11), reason:text, admin:varchar(100), created_at:datetime.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); INDEX ADD KEY variant_id (variant_id).
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (1): legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_subcategory
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (5): subcategory_id:int(11), subcategory_name:varchar(255), category_id:int(11), subcategory_image:varchar(500), subcategory_active:tinyint(1).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (subcategory_id); INDEX ADD KEY category_id (category_id); FOREIGN KEY ADD CONSTRAINT fk_zg_subcategory_category FOREIGN KEY (category_id) REFERENCES zg_category (category_id) ON DELETE CASCADE.
- PHP backup snapshot references (2): admin\manage\editProduct.php; api\getCategory.php.
- Django runtime app references (2): legacy_api\views_catalog.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_target_achievements
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (12): achievement_id:int(11), target_id:int(11), user_id:int(11), total_spent:decimal(10,2), order_count:int(11), progress_percentage:decimal(5,2), is_achieved:tinyint(1), achieved_date:date, last_order_date:date, last_order_id:int(11), created_at:timestamp, updated_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (achievement_id); UNIQUE ADD UNIQUE KEY unique_user_target (target_id,user_id); INDEX ADD KEY idx_user_id (user_id); INDEX ADD KEY idx_target_id (target_id); INDEX ADD KEY idx_achieved (is_achieved).
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (2): legacy_api\views_remaining.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0002_salesman_target_targetachievement_targetassignment.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_target_activity_log
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (7): log_id:int(11), target_id:int(11), user_id:int(11), action:enum('CREATED','UPDATED','DELETED','ASSIGNED','UNASSIGNED','ACHIEVED','RECALCULATED'), details:text, ip_address:varchar(45), created_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (log_id); INDEX ADD KEY idx_target (target_id); INDEX ADD KEY idx_user (user_id); INDEX ADD KEY idx_action (action).
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_target_assignments
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (9): assignment_id:int(11), target_id:int(11), user_id:int(11), achieved_amount:decimal(10,2), order_count:int(11), status:enum('PENDING','ACHIEVED','FAILED'), achieved_date:date, created_at:timestamp, updated_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (assignment_id); UNIQUE ADD UNIQUE KEY unique_assignment (target_id,user_id); INDEX ADD KEY idx_user (user_id); INDEX ADD KEY idx_status (status); INDEX ADD KEY idx_achieved (achieved_date).
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (3): adminapi\crud.py; legacy_api\views_remaining.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0002_salesman_target_targetachievement_targetassignment.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_targets
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (13): target_id:int(11), target_name:varchar(255), category_id:int(11), target_amount:decimal(10,2), reward_description:text, reward_image:varchar(255), scheme_benefits:text, start_date:date, end_date:date, status:enum('ACTIVE','INACTIVE','COMPLETED'), created_by:int(11), created_at:timestamp, updated_at:timestamp.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (target_id); INDEX ADD KEY idx_category (category_id); INDEX ADD KEY idx_status (status); INDEX ADD KEY idx_dates (start_date,end_date).
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (3): adminapi\operations.py; legacy_api\views_remaining.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0002_salesman_target_targetachievement_targetassignment.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_testy
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (5): id:int(11), image:varchar(255), text1:varchar(255), text2:varchar(255), text3:text.
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id).
- PHP backup snapshot references (1): admin\manage\testmo.php.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_vari_product
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (12): id:int(11), var_id:int(11), ver_name:varchar(255), product_name:varchar(255), product_price:decimal(10,2), product_discount:decimal(5,2), product_description:text, product_keywords:varchar(255), product_id:int(11), top:int(11), hand:int(11), added:varchar(255).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (id); INDEX ADD KEY hal_product_ibfk_1 (product_id).
- PHP backup snapshot references (0): none found in backup snapshot.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_vari_product_images
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (5): image_id:int(11), product_id:int(11), var_id:varchar(255), image_path:varchar(255), main:varchar(255).
- Source key/index/FK definitions: no parsed key definitions.
- PHP backup snapshot references (1): admin\manage\col.php.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_vari_variant
- Classification: EXCLUDED_PENDING_DEPENDENCY_REVIEW; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (5): variant_id:int(11), variant_name:varchar(255), variant_price:decimal(10,2), product_id:int(11), disc:varchar(255).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (variant_id); INDEX ADD KEY product_id (product_id).
- PHP backup snapshot references (1): admin\manage\edit_col.php.
- Django runtime app references (0): none found in runtime app source.
- Django test/migration/audit-tool references (1): scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_variant
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (11): variant_id:int(11), variant_name:varchar(255), variant_price:decimal(10,2), mrp:decimal(10,2), product_id:int(11), disc:varchar(255), quantity:int(11), gst:enum('Y','N'), gst_price:decimal(10,2), category_id:int(11), subcategory_id:int(11).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (variant_id); INDEX ADD KEY product_id (product_id); INDEX ADD KEY subcategory_id (subcategory_id).
- PHP backup snapshot references (1): api\order_post.php.
- Django runtime app references (4): legacy_api\views_catalog.py; legacy_api\views_commerce.py; legacy_api\views_orders.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### zg_warehouse
- Classification: PROPOSED_PENDING_EVIDENCE; target status: NOT_CONFIRMED_IN_TARGET; approval: NOT_APPROVED.
- Source columns (8): warehouse_id:int(11), warehouse_name:varchar(100), address:varchar(255), pincode:varchar(10), state:varchar(50), place:varchar(50), latitude:decimal(10,8), longitude:decimal(11,8).
- Source key/index/FK definitions: PRIMARY KEY ADD PRIMARY KEY (warehouse_id).
- PHP backup snapshot references (5): admin\manage\editProduct.php; admin\manage\O.PHP; admin\manage\product.php; api\highlights.php; api\recommended.php.
- Django runtime app references (4): adminapi\operations.py; adminapi\order_pages.py; legacy_api\views_catalog.py; legacydb\models.py.
- Django test/migration/audit-tool references (2): legacydb\migrations\0001_initial.py; scripts\read_only_audits\phase_a_manifest_readonly.py.
- React literal table-name references (0): none found; API-mediated dependency may be indirect.
- Scope and conversion decision: UNRESOLVED; source dump presence or a code reference alone does not authorize table creation.

### Live PostgreSQL baseline — read-only, verified in Phase 4
- Identity: stokit_postgres_dev, user postgres, schema public, PostgreSQL 18.6, server 127.0.0.1:5432.
- Public base tables: exactly 3 — admins, admin_cart_discount_settings, django_migrations.
- Exact row counts: admins=0; admin_cart_discount_settings=0; django_migrations=1.
- Migration record: adminapi / 0001_cart_discount_settings / 2026-10-15 15:44:38.022359+05:30.
- Tuple scan: 39 INSERT statements and 3,224 tuples in both original and sanitized dumps, under standard backslash escaping and NO_BACKSLASH_ESCAPES emulation. The earlier 3,219 count was not reproduced; its origin remains unknown.
- Constraints/indexes: all three tables have a primary key on id; no username/email unique constraint was found on admins. admin_cart_discount_settings.id has CHECK id >= 0; no other business indexes were found on these three tables.
- Read-only inspection used psql -X -w -v ON_ERROR_STOP=1, catalog SELECTs, exact COUNT queries, and BEGIN READ ONLY followed by ROLLBACK. No DDL/DML was executed.

## Master completion pass (2026-10-16)

### PHP provenance and excluded-table dependencies (Workstream B)
Verified facts: backup root `C:\Users\.MSI\Downloads\StokIt_PHP_Backup_20261012\Host`; 153 PHP files; no `.git`, no manifest/checksum/deploy files (only .htaccess); all file mtimes are within 10 seconds on 2026-10-09 (extraction time). No `.git` at the workspace roots or C:\Project\stokit. The `stokit_php` workspace path resolves to an empty location. Provenance of the active deployment: BLOCKED.

CORRECTION to earlier text in these reports: the previous literal-name scan found only 8 referenced tables because the PHP code builds names as `{$qt}_table` with `$qt = 'zg'` (admin/manage/config.php). After resolving that prefix (scripts/read_only_audits/excluded_table_dependency_audit_readonly.py, output docs/STOKIT_EXCLUDED_TABLE_DEPENDENCY_MATRIX.json) 14 of 16 excluded tables have SQL references in the backup; only users1 and zg_target_activity_log have none. Operation labels are keyword-heuristic (nearest SQL keyword before the name); comment-only lines are labeled separately. All hits are under admin/manage/; none are in the backup's api/ files. No excluded table is referenced by Django runtime code, tests aside, or by React. 350 dynamic-name candidate lines exist (interpolated variables); only the `$qt`/`$table_prefix` pattern was resolved, so other dynamically built names are not ruled out. A static backup scan is not proof that any table is unused or used in production.

| Table | PHP backup references (operation counts) | Source path : function | Inferred business purpose | Dump rows (approx) / FKs / triggers | Django runtime / React refs | Risk of continued exclusion |
|---|---|---|---|---|---|---|
| `users1` | none (hits 0, 0 via $qt prefix) | - | Unknown (no code reference found); name suggests a legacy user copy [inference] | ~2 / none / 0 | 0 / 0 | Low |
| `zg_api_keys` | DELETE x1, INSERT x2, SELECT/read x2, UPDATE x3 (hits 8, 8 via $qt prefix) | admin/manage/keys.php:getAllKeys<br>admin/manage/keys.php:getGroupedKeys<br>admin/manage/keys.php:getKeyById | Admin management of service/payment API keys (key_type, service_name, key_value, merchant_id, salt_key) [inferred from SQL columns] | ~0 / none / 0 | 0 / 0 | High if the PHP admin is live: payment-key management has no Django equivalent |
| `zg_banner` | DELETE x1, INSERT x1, SELECT/read x10, UPDATE x3 (hits 15, 15 via $qt prefix) | admin/manage/ban_timer.php:getAvailableSlot<br>admin/manage/ban_timer.php:hasActiveBanner<br>admin/manage/ban_timer.php:updatePreviewTimer<br>admin/manage/login.php:(top-level script) | Admin-login-page banner and countdown (ban_timer.php, login.php) [inferred]; distinct from the Django banner model (zg_slider) | ~1 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_brands` | DELETE x1, INSERT x1, SELECT/read x3 (hits 5, 0 via $qt prefix) | admin/manage/brands.php:(top-level script) | Brand list management (brands.php) [inferred] | ~3 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_cod` | INSERT x1, SELECT/read x2, UPDATE x1 (hits 4, 0 via $qt prefix) | admin/manage/cod.php:(top-level script) | Cash-on-delivery settings (cod.php) [inferred] | ~1 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_headings` | SELECT/read x1, UPDATE x1 (hits 2, 2 via $qt prefix) | admin/manage/heading4.php:(top-level script) | Storefront/app heading text (heading4.php) [inferred] | ~1 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_headings_new` | INSERT x1, SELECT/read x6, UPDATE x3, comment-only x2 (hits 12, 8 via $qt prefix) | admin/manage/editProduct.php:(top-level script)<br>admin/manage/headings.php:(top-level script)<br>admin/manage/product.php:(top-level script) | Product-page headings (headings.php, product.php, editProduct.php) [inferred] | ~7 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_logo` | DELETE x2, INSERT x1, SELECT/read x5, UPDATE x1 (hits 9, 9 via $qt prefix) | admin/manage/logo.php:(top-level script) | Site logo and favicon files (logo.php) [inferred] | ~2 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_product_warehouse` | DELETE x2, INSERT x1, SELECT/read x4, comment-only x1 (hits 8, 8 via $qt prefix) | admin/manage/editProduct.php:(top-level script)<br>admin/manage/editProduct.php:handleBannerUpload<br>admin/manage/product.php:(top-level script)<br>admin/manage/warehouse_details.php:(top-level script) | Product-to-warehouse assignment; FKs to zg_product and zg_warehouse; INNER JOIN in the PHP product list [inferred] | ~9 / `product_id` -> zg_product; `warehouse_id` -> zg_warehouse / 0 | 0 / 0 | High if used: FK-linked assignment data; PHP product list joins it; no Django equivalent |
| `zg_reels` | DELETE x1, INSERT x1, SELECT/read x2, UPDATE x1 (hits 5, 0 via $qt prefix) | admin/manage/reels.php:getInstagramEmbedCode | Reels/video content management (reels.php) [inferred] | ~1 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_social_media` | SELECT/read x2, UPDATE x1 (hits 3, 2 via $qt prefix) | admin/manage/navbar.php:(top-level script)<br>admin/manage/social.php:(top-level script) | Social links (social.php, navbar.php) [inferred] | ~1 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_target_activity_log` | none (hits 0, 0 via $qt prefix) | - | Unknown (no code reference found); name suggests a target activity audit log [inference] | ~0 / none / 0 | 0 / 0 | Low |
| `zg_testy` | DELETE x1, INSERT x2, SELECT/read x4, UPDATE x2, comment-only x1 (hits 10, 1 via $qt prefix) | admin/manage/testmo.php:(top-level script) | Testimonials (testmo.php) [inferred] | ~4 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_vari_product` | DELETE x1, INSERT x1, SELECT/read x3, UPDATE x2 (hits 7, 7 via $qt prefix) | admin/manage/add_col.php:compressImage<br>admin/manage/col.php:(top-level script)<br>admin/manage/edit_col.php:(top-level script)<br>admin/manage/edit_col.php:compressImage<br>admin/manage/edit_col_.php:(top-level script)<br>admin/manage/edit_col_.php:compressImage | Variant-collection ('col') products (add_col.php, col.php, edit_col*.php) [inferred] | ~0 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_vari_product_images` | DELETE x3, INSERT x3, SELECT/read x6, UPDATE x4 (hits 16, 15 via $qt prefix) | admin/manage/add_col.php:compressImage<br>admin/manage/col.php:(top-level script)<br>admin/manage/edit_col.php:(top-level script)<br>admin/manage/edit_col.php:compressImage<br>admin/manage/edit_col_.php:(top-level script)<br>admin/manage/edit_col_.php:compressImage | Images for variant-collection products [inferred] | ~0 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |
| `zg_vari_variant` | DELETE x2, INSERT x1, SELECT/read x1, comment-only x1 (hits 5, 4 via $qt prefix) | admin/manage/col.php:(top-level script)<br>admin/manage/edit_col.php:(top-level script)<br>admin/manage/edit_col.php:compressImage | Variants of variant-collection products; only a delete comment plus SQL found [inferred] | ~0 / none / 0 | 0 / 0 | Medium if the PHP admin page is live; not reachable from Django/React or the Flutter-facing api/ files |

Evidence required to change any classification: authoritative deployed source or access logs showing which admin/manage pages are actually used, plus an owner scope decision. Exclusions were preserved; nothing was created, restored or populated.
