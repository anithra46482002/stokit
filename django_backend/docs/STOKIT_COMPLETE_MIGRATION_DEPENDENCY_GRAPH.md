# StokIt Complete Migration Dependency Graph

Status: REVIEW ONLY; no migrations executed.

## Verified migration evidence
- legacydb migrations 0001–0003 exist; mappings are unmanaged (managed=False) and do not create, alter, or drop legacy tables.
- accounts.0001_initial depends on legacydb.__first__; creates accounts_passwordresetotp, accounts_devicetoken, and accounts_userdevicesession. Legacy-user foreign keys use db_constraint=False.
- accounts.0002_adminroleassignment_checkoutpayload depends on accounts.0001_initial; creates accounts_adminroleassignment and accounts_checkoutpayload, including uniq_admin_role_principal.
- adminapi.0001_cart_discount_settings has no dependencies and is recorded as applied in the target; preserve its table and migration record.
- auth and contenttypes migrations were reported pending in Phase 2. Exact dependency order must be freshly exported before implementation.

## Known dependency graph
legacydb.__first__ -> accounts.0001_initial -> accounts.0002_adminroleassignment_checkoutpayload
adminapi.0001_cart_discount_settings -> existing admin_cart_discount_settings table (already recorded applied; do not reapply).
Django auth/contenttypes -> pending; exact graph edges are not asserted here without a fresh graph export.

A migration record is not proof that an unmanaged legacy table exists. managed=False mappings do not create tables. Runtime access depends on the mapped table and compatible columns. Check relation, index, constraint, sequence, and FK name collisions before implementation. Do not use fake migrations or rewrite migration history. Preserve admins, admin_cart_discount_settings, and django_migrations.

## Phase 4 read-only evidence (2026-10-15 21:45:11 +05:30)

- Live PostgreSQL identity freshly verified: database stokit_postgres_dev, user postgres, schema public, PostgreSQL 18.6, endpoint 127.0.0.1:5432.
- public contains exactly three base tables: admins, admin_cart_discount_settings, and django_migrations. Exact counts are 0, 0, and 1 respectively. The only recorded migration is adminapi.0001_cart_discount_settings, applied at 2026-10-15 15:44:38.022359+05:30.
- Runtime migration files confirm: accounts.0001_initial depends on legacydb.__first__; accounts.0002_adminroleassignment_checkoutpayload depends on accounts.0001_initial; adminapi.0001_cart_discount_settings has no dependencies. Preserve the existing cart-discount table and migration record.
- React authSession.js accepts roles SUPER_ADMIN, ADMIN, SALESMAN, WAREHOUSE_STAFF, and DELIVERY_BOY. This is a frontend contract, not approval for bootstrap/account creation.
- legacydb/models.py maps legacy tables with managed=False; physical legacy tables are still required for runtime SQL paths. Accounts migrations define accounts_passwordresetotp, accounts_devicetoken, accounts_userdevicesession, accounts_adminroleassignment, and accounts_checkoutpayload; these were not present in the live public table inventory.
- Live admins.id is integer default 0, not identity/serial; username and email have no unique constraints. No account or role assignment was created.
- PHP reference evidence is from a backup snapshot only. Active PHP source is not confirmed, so source-of-truth/dependency review remains open.
