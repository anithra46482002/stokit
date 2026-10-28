# StokIt Source Schema Inventory

Generated: 2026-10-15T20:40:13+05:30

**Safety:** read-only inspection of SQL dump structure. No INSERT values are emitted, no historical rows are imported, and no PostgreSQL schema changes are made.

## Dump comparison

| Metric | Original | Sanitized |
|---|---:|---:|
| File bytes | 134426410 | 208686 |
| CREATE TABLE statements | 45 | 45 |
| ALTER TABLE statements | 92 | 92 |
| INSERT statements | 39 | 39 |
| Standalone CREATE INDEX statements | 0 | 0 |
| CREATE TRIGGER statements | 1 | 1 |

Table-name sets match: **True**.
Original-only names: None.
Sanitized-only names: None.

## Tables and columns

| Table | Columns | PK/unique/index/FK definitions (CREATE + ALTER) | Engine |
|---|---:|---:|---|
| `a_cart` | 7 | 1 | InnoDB |
| `admins` | 11 | 1 | InnoDB |
| `advance_pay_allocations` | 17 | 5 | InnoDB |
| `advance_pay_offers` | 10 | 1 | InnoDB |
| `advance_pay_transactions` | 9 | 5 | InnoDB |
| `category_view` | 3 | 1 | InnoDB |
| `delivery_boys` | 12 | 3 | InnoDB |
| `notifications` | 9 | 3 | InnoDB |
| `salesmen` | 14 | 3 | InnoDB |
| `users` | 31 | 3 | InnoDB |
| `users1` | 11 | 1 | InnoDB |
| `warehouse_delivery_boys` | 4 | 4 | InnoDB |
| `warehouse_salesmen` | 4 | 4 | InnoDB |
| `zg_api_keys` | 12 | 4 | InnoDB |
| `zg_banner` | 14 | 1 | InnoDB |
| `zg_brands` | 2 | 1 | InnoDB |
| `zg_category` | 4 | 1 | InnoDB |
| `zg_checkout` | 18 | 1 | InnoDB |
| `zg_cod` | 8 | 1 | InnoDB |
| `zg_discount_banners` | 4 | 3 | InnoDB |
| `zg_favorites` | 4 | 2 | InnoDB |
| `zg_headings` | 8 | 1 | InnoDB |
| `zg_headings_new` | 5 | 1 | InnoDB |
| `zg_location` | 2 | 2 | InnoDB |
| `zg_logo` | 6 | 2 | InnoDB |
| `zg_order_items` | 10 | 2 | InnoDB |
| `zg_order_status_history` | 5 | 2 | InnoDB |
| `zg_product` | 41 | 5 | InnoDB |
| `zg_product_images` | 4 | 1 | InnoDB |
| `zg_product_warehouse` | 3 | 5 | InnoDB |
| `zg_reels` | 5 | 1 | InnoDB |
| `zg_slider` | 7 | 1 | InnoDB |
| `zg_social_media` | 5 | 1 | InnoDB |
| `zg_stock_log` | 6 | 2 | InnoDB |
| `zg_subcategory` | 5 | 3 | InnoDB |
| `zg_target_achievements` | 12 | 5 | InnoDB |
| `zg_target_activity_log` | 7 | 4 | InnoDB |
| `zg_target_assignments` | 9 | 5 | InnoDB |
| `zg_targets` | 13 | 4 | InnoDB |
| `zg_testy` | 5 | 1 | InnoDB |
| `zg_vari_product` | 12 | 2 | InnoDB |
| `zg_vari_product_images` | 5 | 0 | InnoDB |
| `zg_vari_variant` | 5 | 2 | InnoDB |
| `zg_variant` | 11 | 3 | InnoDB |
| `zg_warehouse` | 8 | 1 | InnoDB |

### `a_cart`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `cart_id` | `varchar(50)` |
| `username` | `varchar(100)` |
| `product_id` | `int(11)` |
| `variant_id` | `int(11)` |
| `qty` | `int(11)` |
| `created_at` | `datetime` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `admins`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `username` | `varchar(50)` |
| `email` | `varchar(100)` |
| `fullname` | `varchar(100)` |
| `password` | `varchar(255)` |
| `phone` | `varchar(250)` |
| `address` | `varchar(250)` |
| `paymentDate` | `varchar(255)` |
| `token` | `varchar(1000)` |
| `api_token` | `varchar(64)` |
| `last_login` | `datetime` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `advance_pay_allocations`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `offer_id` | `int(11)` |
| `user_id` | `int(11)` |
| `payment_amount` | `decimal(10,2)` |
| `bonus_percentage` | `decimal(5,2)` |
| `duration_months` | `int(11)` |
| `total_credit` | `decimal(10,2)` |
| `used_credit` | `decimal(10,2)` |
| `remaining_credit` | `decimal(10,2)` |
| `start_date` | `date` |
| `end_date` | `date` |
| `status` | `enum('ACTIVE','EXPIRED','COMPLETED','CANCELLED')` |
| `payment_date` | `date` |
| `payment_reference` | `varchar(255)` |
| `notes` | `text` |
| `created_at` | `timestamp` |
| `updated_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **INDEX**: `ADD KEY \`offer_id\` (\`offer_id\`)`
- **INDEX**: `ADD KEY \`user_id\` (\`user_id\`)`
- **FOREIGN KEY**: `ADD CONSTRAINT \`advance_pay_allocations_ibfk_1\` FOREIGN KEY (\`offer_id\`) REFERENCES \`advance_pay_offers\` (\`id\`) ON DELETE CASCADE`
- **FOREIGN KEY**: `ADD CONSTRAINT \`advance_pay_allocations_ibfk_2\` FOREIGN KEY (\`user_id\`) REFERENCES \`users\` (\`id\`) ON DELETE CASCADE`

### `advance_pay_offers`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `offer_name` | `varchar(255)` |
| `payment_amount` | `decimal(10,2)` |
| `bonus_percentage` | `decimal(5,2)` |
| `duration_months` | `int(11)` |
| `total_credit` | `decimal(10,2)` |
| `status` | `enum('ACTIVE','INACTIVE')` |
| `image_path` | `varchar(255)` |
| `created_at` | `timestamp` |
| `updated_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `advance_pay_transactions`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `allocation_id` | `int(11)` |
| `user_id` | `int(11)` |
| `amount` | `decimal(10,2)` |
| `transaction_type` | `enum('CREDIT_USED','CREDIT_ADDED')` |
| `reference_id` | `int(11)` |
| `reference_type` | `varchar(50)` |
| `notes` | `text` |
| `created_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **INDEX**: `ADD KEY \`allocation_id\` (\`allocation_id\`)`
- **INDEX**: `ADD KEY \`user_id\` (\`user_id\`)`
- **FOREIGN KEY**: `ADD CONSTRAINT \`advance_pay_transactions_ibfk_1\` FOREIGN KEY (\`allocation_id\`) REFERENCES \`advance_pay_allocations\` (\`id\`) ON DELETE CASCADE`
- **FOREIGN KEY**: `ADD CONSTRAINT \`advance_pay_transactions_ibfk_2\` FOREIGN KEY (\`user_id\`) REFERENCES \`users\` (\`id\`) ON DELETE CASCADE`

### `category_view`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `user` | `varchar(255)` |
| `category_id` | `int(11)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `delivery_boys`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `username` | `varchar(50)` |
| `email` | `varchar(100)` |
| `fullname` | `varchar(100)` |
| `password` | `varchar(255)` |
| `phone` | `varchar(250)` |
| `address` | `varchar(250)` |
| `paymentDate` | `varchar(255)` |
| `token` | `varchar(1000)` |
| `api_token` | `varchar(64)` |
| `last_login` | `datetime` |
| `created_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`username\` (\`username\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`email\` (\`email\`)`

### `notifications`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `customer_id` | `int(11)` |
| `title` | `varchar(255)` |
| `message` | `text` |
| `sent_by` | `varchar(100)` |
| `created_at` | `timestamp` |
| `is_read` | `tinyint(1)` |
| `read_at` | `timestamp` |
| `recipient_type` | `varchar(20)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **INDEX**: `ADD KEY \`customer_id\` (\`customer_id\`)`
- **FOREIGN KEY**: `ADD CONSTRAINT \`notifications_ibfk_1\` FOREIGN KEY (\`customer_id\`) REFERENCES \`users\` (\`id\`) ON DELETE CASCADE`

### `salesmen`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `username` | `varchar(50)` |
| `email` | `varchar(100)` |
| `fullname` | `varchar(100)` |
| `password` | `varchar(255)` |
| `phone` | `varchar(20)` |
| `address` | `text` |
| `commission_rate` | `decimal(5,2)` |
| `hire_date` | `date` |
| `target_sales` | `decimal(10,2)` |
| `token` | `varchar(64)` |
| `api_token` | `varchar(64)` |
| `created_at` | `timestamp` |
| `updated_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`username\` (\`username\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`email\` (\`email\`)`

### `users`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `username` | `varchar(100)` |
| `password` | `varchar(255)` |
| `email` | `varchar(255)` |
| `fullname` | `varchar(255)` |
| `shop_name` | `varchar(255)` |
| `phone` | `varchar(20)` |
| `city` | `varchar(255)` |
| `category_id` | `varchar(125)` |
| `address` | `text` |
| `status` | `enum('ACTIVE','INACTIVE','SUSPENDED')` |
| `gst` | `enum('Y','N')` |
| `gst_type` | `enum('REGULAR','COMPOUND')` |
| `vip_discount` | `enum('Y','N')` |
| `vip_percentage` | `decimal(5,2)` |
| `store_maped` | `enum('Y','N')` |
| `profile_picture` | `varchar(255)` |
| `created_at` | `timestamp` |
| `updated_at` | `timestamp` |
| `token` | `varchar(255)` |
| `latitude` | `varchar(125)` |
| `longitude` | `varchar(125)` |
| `gst_number` | `varchar(20)` |
| `gst_percentage` | `decimal(5,2)` |
| `delivery_charges` | `decimal(10,2)` |
| `color_code` | `varchar(20)` |
| `warehouse_id` | `int(11)` |
| `vip_from_date` | `date` |
| `vip_to_date` | `date` |
| `vip_start_date` | `date` |
| `vip_end_date` | `date` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`email\` (\`email\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`username\` (\`username\`)`

### `users1`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `username` | `varchar(50)` |
| `email` | `varchar(100)` |
| `fullname` | `varchar(100)` |
| `password` | `varchar(255)` |
| `phone` | `varchar(250)` |
| `address` | `varchar(250)` |
| `paymentDate` | `varchar(255)` |
| `token` | `varchar(1000)` |
| `api_token` | `varchar(64)` |
| `last_login` | `datetime` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `warehouse_delivery_boys`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `warehouse_id` | `int(11)` |
| `delivery_boy_id` | `int(11)` |
| `created_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`unique_warehouse_delivery_boy\` (\`warehouse_id\`,\`delivery_boy_id\`)`
- **INDEX**: `ADD KEY \`warehouse_id\` (\`warehouse_id\`)`
- **INDEX**: `ADD KEY \`delivery_boy_id\` (\`delivery_boy_id\`)`

### `warehouse_salesmen`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `warehouse_id` | `int(11)` |
| `salesman_id` | `int(11)` |
| `created_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`unique_warehouse_salesman\` (\`warehouse_id\`,\`salesman_id\`)`
- **INDEX**: `ADD KEY \`warehouse_id\` (\`warehouse_id\`)`
- **INDEX**: `ADD KEY \`salesman_id\` (\`salesman_id\`)`

### `zg_api_keys`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `key_type` | `enum('captcha','payment')` |
| `service_name` | `varchar(50)` |
| `key_name` | `varchar(100)` |
| `key_value` | `text` |
| `merchant_id` | `varchar(100)` |
| `salt_key` | `varchar(255)` |
| `payment_mode` | `enum('test','live')` |
| `is_active` | `tinyint(1)` |
| `description` | `text` |
| `created_at` | `timestamp` |
| `updated_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **INDEX**: `ADD KEY \`idx_key_type\` (\`key_type\`)`
- **INDEX**: `ADD KEY \`idx_service\` (\`service_name\`)`
- **INDEX**: `ADD KEY \`idx_active\` (\`is_active\`)`

### `zg_banner`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `bg_image` | `varchar(255)` |
| `timer_days` | `int(11)` |
| `timer_hours` | `int(11)` |
| `timer_minutes` | `int(11)` |
| `timer_seconds` | `int(11)` |
| `heading` | `varchar(255)` |
| `paragraph` | `text` |
| `button_text` | `varchar(50)` |
| `button_link` | `varchar(255)` |
| `last_updated` | `timestamp` |
| `view` | `varchar(255)` |
| `count` | `varchar(255)` |
| `banner_slot` | `varchar(255)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `zg_brands`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `image` | `varchar(255)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `zg_category`

| Column | Source type |
|---|---|
| `category_id` | `int(11)` |
| `category_name` | `varchar(255)` |
| `category_image` | `varchar(255)` |
| `category_active` | `tinyint(1)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`category_id\`)`

### `zg_checkout`

| Column | Source type |
|---|---|
| `order_id` | `int(11)` |
| `user` | `varchar(120)` |
| `full_name` | `varchar(255)` |
| `address` | `varchar(255)` |
| `city` | `varchar(100)` |
| `state` | `varchar(100)` |
| `postal_code` | `varchar(20)` |
| `country` | `varchar(100)` |
| `phone` | `varchar(20)` |
| `email` | `varchar(255)` |
| `total_amount` | `decimal(10,2)` |
| `order_date` | `datetime` |
| `status` | `varchar(255)` |
| `delivery_boy_id` | `int(11)` |
| `view` | `varchar(255)` |
| `payment_method` | `varchar(255)` |
| `shipping_charge` | `varchar(255)` |
| `cod_charge` | `decimal(10,2)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`order_id\`)`

### `zg_cod`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `cod_enabled` | `enum('Y','N')` |
| `charges` | `decimal(10,2)` |
| `created_at` | `timestamp` |
| `shipping_type` | `enum('fixed','price_based')` |
| `fixed_shipping_charge` | `decimal(10,2)` |
| `min_order_amount` | `decimal(10,2)` |
| `shipping_charge_below_min` | `decimal(10,2)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `zg_discount_banners`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `product_id` | `int(11)` |
| `image_path` | `varchar(255)` |
| `created_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **INDEX**: `ADD KEY \`product_id\` (\`product_id\`)`
- **FOREIGN KEY**: `ADD CONSTRAINT \`fk_discount_banners_product\` FOREIGN KEY (\`product_id\`) REFERENCES \`zg_product\` (\`product_id\`) ON DELETE CASCADE`

### `zg_favorites`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `user_id` | `varchar(125)` |
| `product_id` | `int(11)` |
| `created_at` | `datetime` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`unique_user_product\` (\`user_id\`,\`product_id\`)`

### `zg_headings`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `heading1` | `varchar(255)` |
| `heading2` | `varchar(255)` |
| `heading3` | `varchar(255)` |
| `heading4` | `varchar(255)` |
| `heading5` | `varchar(255)` |
| `heading6` | `varchar(255)` |
| `heading7` | `varchar(225)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `zg_headings_new`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `name` | `varchar(255)` |
| `button_name` | `varchar(125)` |
| `image` | `varchar(500)` |
| `updated_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `zg_location`

| Column | Source type |
|---|---|
| `location_id` | `int(11)` |
| `city_name` | `varchar(100)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`location_id\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`city_name\` (\`city_name\`)`

### `zg_logo`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `file` | `varchar(255)` |
| `type` | `enum('logo','favicon')` |
| `favico` | `varchar(255)` |
| `created_at` | `timestamp` |
| `updated_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **INDEX**: `ADD KEY \`idx_type\` (\`type\`)`

### `zg_order_items`

| Column | Source type |
|---|---|
| `item_id` | `int(11)` |
| `order_id` | `int(11)` |
| `product_id` | `int(11)` |
| `variant_id` | `int(11)` |
| `product_name` | `varchar(255)` |
| `variant_name` | `varchar(255)` |
| `quantity` | `int(11)` |
| `price` | `decimal(10,2)` |
| `discount` | `decimal(10,2)` |
| `total_price` | `decimal(10,2)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`item_id\`)`
- **INDEX**: `ADD KEY \`order_id\` (\`order_id\`)`

### `zg_order_status_history`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `order_id` | `int(11)` |
| `status` | `varchar(50)` |
| `changed_at` | `datetime` |
| `message` | `text` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **INDEX**: `ADD KEY \`order_id\` (\`order_id\`)`

### `zg_product`

| Column | Source type |
|---|---|
| `product_id` | `int(11)` |
| `code` | `varchar(250)` |
| `stock` | `varchar(250)` |
| `product_name` | `varchar(255)` |
| `color` | `varchar(255)` |
| `product_price` | `decimal(10,2)` |
| `mrp` | `decimal(10,2)` |
| `product_discount` | `decimal(10,2)` |
| `product_description` | `text` |
| `product_keywords` | `varchar(255)` |
| `subtitle` | `varchar(255)` |
| `brand` | `varchar(100)` |
| `youtube_link` | `varchar(255)` |
| `share_image` | `varchar(255)` |
| `product_details` | `longtext` |
| `additional_details` | `longtext` |
| `moq` | `int(11)` |
| `set_of` | `int(11)` |
| `quantity_selected` | `int(11)` |
| `discount_value` | `decimal(10,2)` |
| `discount_percent` | `decimal(5,2)` |
| `set_contains` | `longtext` |
| `category_id` | `int(11)` |
| `subcategory_id` | `int(11)` |
| `top` | `int(11)` |
| `hand` | `int(11)` |
| `top2` | `int(11)` |
| `hand2` | `int(11)` |
| `heading5_tag` | `int(11)` |
| `heading6_tag` | `int(11)` |
| `heading7_tag` | `int(11)` |
| `added` | `varchar(255)` |
| `view` | `varchar(255)` |
| `highlight` | `tinyint(1)` |
| `gst_applicable` | `varchar(1)` |
| `gst_percentage` | `decimal(5,2)` |
| `gst_price` | `decimal(10,2)` |
| `has_disc` | `int(1)` |
| `warehouse_id` | `int(11)` |
| `no_discount_banner` | `enum('Y','N')` |
| `disable_variants` | `enum('Y','N')` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`product_id\`)`
- **INDEX**: `ADD KEY \`idx_moq\` (\`moq\`)`
- **INDEX**: `ADD KEY \`idx_brand\` (\`brand\`)`
- **INDEX**: `ADD KEY \`idx_youtube\` (\`youtube_link\`(100))`
- **INDEX**: `ADD KEY \`subcategory_id\` (\`subcategory_id\`)`

### `zg_product_images`

| Column | Source type |
|---|---|
| `image_id` | `int(11)` |
| `product_id` | `int(11)` |
| `image_path` | `varchar(255)` |
| `main` | `varchar(255)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`image_id\`)`

### `zg_product_warehouse`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `product_id` | `int(11)` |
| `warehouse_id` | `int(11)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`unique_mapping\` (\`product_id\`,\`warehouse_id\`)`
- **INDEX**: `ADD KEY \`warehouse_id\` (\`warehouse_id\`)`
- **FOREIGN KEY**: `ADD CONSTRAINT \`zg_product_warehouse_ibfk_1\` FOREIGN KEY (\`product_id\`) REFERENCES \`zg_product\` (\`product_id\`) ON DELETE CASCADE`
- **FOREIGN KEY**: `ADD CONSTRAINT \`zg_product_warehouse_ibfk_2\` FOREIGN KEY (\`warehouse_id\`) REFERENCES \`zg_warehouse\` (\`warehouse_id\`) ON DELETE CASCADE`

### `zg_reels`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `url` | `varchar(500)` |
| `embed_code` | `text` |
| `thumbnail_url` | `varchar(500)` |
| `created_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `zg_slider`

| Column | Source type |
|---|---|
| `slider_id` | `int(11)` |
| `image_path` | `varchar(255)` |
| `text_content` | `text` |
| `styled_text` | `varchar(255)` |
| `styled_color` | `varchar(50)` |
| `back` | `varchar(255)` |
| `text_content2` | `varchar(255)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`slider_id\`)`

### `zg_social_media`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `facebook` | `varchar(255)` |
| `instagram` | `varchar(255)` |
| `youtube` | `varchar(255)` |
| `linkedin` | `varchar(255)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `zg_stock_log`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `variant_id` | `int(11)` |
| `adjustment` | `int(11)` |
| `reason` | `text` |
| `admin` | `varchar(100)` |
| `created_at` | `datetime` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **INDEX**: `ADD KEY \`variant_id\` (\`variant_id\`)`

### `zg_subcategory`

| Column | Source type |
|---|---|
| `subcategory_id` | `int(11)` |
| `subcategory_name` | `varchar(255)` |
| `category_id` | `int(11)` |
| `subcategory_image` | `varchar(500)` |
| `subcategory_active` | `tinyint(1)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`subcategory_id\`)`
- **INDEX**: `ADD KEY \`category_id\` (\`category_id\`)`
- **FOREIGN KEY**: `ADD CONSTRAINT \`fk_zg_subcategory_category\` FOREIGN KEY (\`category_id\`) REFERENCES \`zg_category\` (\`category_id\`) ON DELETE CASCADE`

### `zg_target_achievements`

| Column | Source type |
|---|---|
| `achievement_id` | `int(11)` |
| `target_id` | `int(11)` |
| `user_id` | `int(11)` |
| `total_spent` | `decimal(10,2)` |
| `order_count` | `int(11)` |
| `progress_percentage` | `decimal(5,2)` |
| `is_achieved` | `tinyint(1)` |
| `achieved_date` | `date` |
| `last_order_date` | `date` |
| `last_order_id` | `int(11)` |
| `created_at` | `timestamp` |
| `updated_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`achievement_id\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`unique_user_target\` (\`target_id\`,\`user_id\`)`
- **INDEX**: `ADD KEY \`idx_user_id\` (\`user_id\`)`
- **INDEX**: `ADD KEY \`idx_target_id\` (\`target_id\`)`
- **INDEX**: `ADD KEY \`idx_achieved\` (\`is_achieved\`)`

### `zg_target_activity_log`

| Column | Source type |
|---|---|
| `log_id` | `int(11)` |
| `target_id` | `int(11)` |
| `user_id` | `int(11)` |
| `action` | `enum('CREATED','UPDATED','DELETED','ASSIGNED','UNASSIGNED','ACHIEVED','RECALCULATED')` |
| `details` | `text` |
| `ip_address` | `varchar(45)` |
| `created_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`log_id\`)`
- **INDEX**: `ADD KEY \`idx_target\` (\`target_id\`)`
- **INDEX**: `ADD KEY \`idx_user\` (\`user_id\`)`
- **INDEX**: `ADD KEY \`idx_action\` (\`action\`)`

### `zg_target_assignments`

| Column | Source type |
|---|---|
| `assignment_id` | `int(11)` |
| `target_id` | `int(11)` |
| `user_id` | `int(11)` |
| `achieved_amount` | `decimal(10,2)` |
| `order_count` | `int(11)` |
| `status` | `enum('PENDING','ACHIEVED','FAILED')` |
| `achieved_date` | `date` |
| `created_at` | `timestamp` |
| `updated_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`assignment_id\`)`
- **UNIQUE**: `ADD UNIQUE KEY \`unique_assignment\` (\`target_id\`,\`user_id\`)`
- **INDEX**: `ADD KEY \`idx_user\` (\`user_id\`)`
- **INDEX**: `ADD KEY \`idx_status\` (\`status\`)`
- **INDEX**: `ADD KEY \`idx_achieved\` (\`achieved_date\`)`

### `zg_targets`

| Column | Source type |
|---|---|
| `target_id` | `int(11)` |
| `target_name` | `varchar(255)` |
| `category_id` | `int(11)` |
| `target_amount` | `decimal(10,2)` |
| `reward_description` | `text` |
| `reward_image` | `varchar(255)` |
| `scheme_benefits` | `text` |
| `start_date` | `date` |
| `end_date` | `date` |
| `status` | `enum('ACTIVE','INACTIVE','COMPLETED')` |
| `created_by` | `int(11)` |
| `created_at` | `timestamp` |
| `updated_at` | `timestamp` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`target_id\`)`
- **INDEX**: `ADD KEY \`idx_category\` (\`category_id\`)`
- **INDEX**: `ADD KEY \`idx_status\` (\`status\`)`
- **INDEX**: `ADD KEY \`idx_dates\` (\`start_date\`,\`end_date\`)`

### `zg_testy`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `image` | `varchar(255)` |
| `text1` | `varchar(255)` |
| `text2` | `varchar(255)` |
| `text3` | `text` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`

### `zg_vari_product`

| Column | Source type |
|---|---|
| `id` | `int(11)` |
| `var_id` | `int(11)` |
| `ver_name` | `varchar(255)` |
| `product_name` | `varchar(255)` |
| `product_price` | `decimal(10,2)` |
| `product_discount` | `decimal(5,2)` |
| `product_description` | `text` |
| `product_keywords` | `varchar(255)` |
| `product_id` | `int(11)` |
| `top` | `int(11)` |
| `hand` | `int(11)` |
| `added` | `varchar(255)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`id\`)`
- **INDEX**: `ADD KEY \`hal_product_ibfk_1\` (\`product_id\`)`

### `zg_vari_product_images`

| Column | Source type |
|---|---|
| `image_id` | `int(11)` |
| `product_id` | `int(11)` |
| `var_id` | `varchar(255)` |
| `image_path` | `varchar(255)` |
| `main` | `varchar(255)` |

### `zg_vari_variant`

| Column | Source type |
|---|---|
| `variant_id` | `int(11)` |
| `variant_name` | `varchar(255)` |
| `variant_price` | `decimal(10,2)` |
| `product_id` | `int(11)` |
| `disc` | `varchar(255)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`variant_id\`)`
- **INDEX**: `ADD KEY \`product_id\` (\`product_id\`)`

### `zg_variant`

| Column | Source type |
|---|---|
| `variant_id` | `int(11)` |
| `variant_name` | `varchar(255)` |
| `variant_price` | `decimal(10,2)` |
| `mrp` | `decimal(10,2)` |
| `product_id` | `int(11)` |
| `disc` | `varchar(255)` |
| `quantity` | `int(11)` |
| `gst` | `enum('Y','N')` |
| `gst_price` | `decimal(10,2)` |
| `category_id` | `int(11)` |
| `subcategory_id` | `int(11)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`variant_id\`)`
- **INDEX**: `ADD KEY \`product_id\` (\`product_id\`)`
- **INDEX**: `ADD KEY \`subcategory_id\` (\`subcategory_id\`)`

### `zg_warehouse`

| Column | Source type |
|---|---|
| `warehouse_id` | `int(11)` |
| `warehouse_name` | `varchar(100)` |
| `address` | `varchar(255)` |
| `pincode` | `varchar(10)` |
| `state` | `varchar(50)` |
| `place` | `varchar(50)` |
| `latitude` | `decimal(10,8)` |
| `longitude` | `decimal(11,8)` |

Key/index/constraint definitions (source form; review required):
- **PRIMARY KEY**: `ADD PRIMARY KEY (\`warehouse_id\`)`

## Conversion gates before any database changes

- Reconcile original and sanitized dump integrity, including the previously observed tuple-count discrepancy.
- Convert MariaDB types, ENUM values, TINYINT(1), collations, prefix indexes, timestamp update behavior, triggers, JSON checks, defaults, and FK ordering.
- Review existing target tables and exclude duplicate CREATE statements; preserve `admins`, `admin_cart_discount_settings`, and `django_migrations`.
- Keep historical business rows excluded. Do not run migrations or create the admin until the DDL is independently parsed and reviewed.
- Current parser environment has `sqlparse` only; a PostgreSQL grammar parser (`pglast`/`sqlglot`) is not installed, so grammar-level validation remains pending.
