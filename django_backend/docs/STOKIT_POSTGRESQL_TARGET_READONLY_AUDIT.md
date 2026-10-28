# StokIt PostgreSQL Target ? Read-Only Audit

Generated: 2026-10-15T20:40:43+05:30

**Mode:** read-only metadata and row-count inspection. No DDL/DML, migrations, account creation, or import was performed.

## Connection

- Database: `stokit_postgres_dev`
- Role: `postgres`
- Schema: `public`
- Server: `127.0.0.1/32:5432`
- PostgreSQL version: `PostgreSQL 18.6 on x86_64-windows, compiled by msvc-19.44.35229, 64-bit`

## Tables

| Table | Rows | Columns | Constraints | Indexes |
|---|---:|---:|---:|---:|
| `admin_cart_discount_settings` | 0 | 5 | 7 | 1 |
| `admins` | 0 | 11 | 9 | 1 |
| `django_migrations` | 1 | 4 | 5 | 1 |

## Column and constraint detail

### `admin_cart_discount_settings`

| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| `id` | `smallint` | no | `?` |
| `enabled` | `boolean` | no | `?` |
| `minimum_subtotal` | `numeric` | no | `?` |
| `fixed_discount_amount` | `numeric` | no | `?` |
| `updated_at` | `timestamp with time zone` | no | `?` |

Constraints:
- `admin_cart_discount_settings_enabled_not_null` (n): `NOT NULL enabled`
- `admin_cart_discount_settings_fixed_discount_amount_not_null` (n): `NOT NULL fixed_discount_amount`
- `admin_cart_discount_settings_id_check` (c): `CHECK ((id >= 0))`
- `admin_cart_discount_settings_id_not_null` (n): `NOT NULL id`
- `admin_cart_discount_settings_minimum_subtotal_not_null` (n): `NOT NULL minimum_subtotal`
- `admin_cart_discount_settings_pkey` (p): `PRIMARY KEY (id)`
- `admin_cart_discount_settings_updated_at_not_null` (n): `NOT NULL updated_at`

Indexes:
- `admin_cart_discount_settings_pkey`: `CREATE UNIQUE INDEX admin_cart_discount_settings_pkey ON public.admin_cart_discount_settings USING btree (id)`

### `admins`

| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| `id` | `integer` | no | `0` |
| `username` | `character varying` | no | `?` |
| `email` | `character varying` | no | `?` |
| `fullname` | `character varying` | yes | `?` |
| `password` | `character varying` | no | `?` |
| `phone` | `character varying` | no | `?` |
| `address` | `character varying` | no | `?` |
| `paymentDate` | `character varying` | no | `?` |
| `token` | `character varying` | no | `?` |
| `api_token` | `character varying` | yes | `?` |
| `last_login` | `timestamp without time zone` | yes | `?` |

Constraints:
- `admins_address_not_null` (n): `NOT NULL address`
- `admins_email_not_null` (n): `NOT NULL email`
- `admins_id_not_null` (n): `NOT NULL id`
- `admins_password_not_null` (n): `NOT NULL password`
- `admins_paymentDate_not_null` (n): `NOT NULL "paymentDate"`
- `admins_phone_not_null` (n): `NOT NULL phone`
- `admins_pkey` (p): `PRIMARY KEY (id)`
- `admins_token_not_null` (n): `NOT NULL token`
- `admins_username_not_null` (n): `NOT NULL username`

Indexes:
- `admins_pkey`: `CREATE UNIQUE INDEX admins_pkey ON public.admins USING btree (id)`

### `django_migrations`

| Column | PostgreSQL type | Nullable | Default |
|---|---|---|---|
| `id` | `integer` | no | `?` |
| `app` | `character varying` | no | `?` |
| `name` | `character varying` | no | `?` |
| `applied` | `timestamp with time zone` | no | `?` |

Constraints:
- `django_migrations_app_not_null` (n): `NOT NULL app`
- `django_migrations_applied_not_null` (n): `NOT NULL applied`
- `django_migrations_id_not_null` (n): `NOT NULL id`
- `django_migrations_name_not_null` (n): `NOT NULL name`
- `django_migrations_pkey` (p): `PRIMARY KEY (id)`

Indexes:
- `django_migrations_pkey`: `CREATE UNIQUE INDEX django_migrations_pkey ON public.django_migrations USING btree (id)`

## Existing migration records

| App | Migration | Applied |
|---|---|---|
| `adminapi` | `0001_cart_discount_settings` | 2026-10-15T10:14:38.022359 |

## Interpretation

- This is the current live target state only; it does not prove that the candidate application schema is complete.
- Preserve all current tables and migration records. Do not drop/recreate the existing `admins`, `admin_cart_discount_settings`, or `django_migrations` tables.
- Current application migrations remain pending except for the existing cart-discount migration record. Do not apply them until schema reconciliation and a verified recovery plan are complete.
- The fresh-database policy excludes historical business-row imports.
