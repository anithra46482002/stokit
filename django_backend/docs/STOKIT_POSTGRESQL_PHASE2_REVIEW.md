# StokIt PostgreSQL Phase 2 Review

Generated: 2026-10-15T21:08:02.8137730+05:30

## Status
**PARTIAL — safety artifacts prepared; application database initialization remains blocked.**

## Verified work
- Cody workspace connected and project read-only inspection completed.
- Target remains stokit_postgres_dev on local PostgreSQL 127.0.0.1:5432/public.
- Custom-format backup created at: C:\Users\.MSI\Downloads\StokIt Backend\django_backend\backups\stokit_postgres_dev_pre_phase2_20261015_210457.dump
- Backup archive listed and restored to isolated database: stokit_phase2_restore_verify_20261015_210457
- Backup/restore inventory matched: three tables, exact row counts, one migration record.
- Review-only Django-managed DDL candidate generated from 19 pending migrations; 12 CREATE TABLE objects, 16 distinct index names, 8 ALTER TABLE targets.
- Candidate DDL passed PostgreSQL parsing and semantic execution in a BEGIN/ROLLBACK transaction on the isolated restore database.
- After rollback, isolated restore still has 3 public tables.
- Target table row counts after checks: admin_cart_discount_settings|0; admins|0; django_migrations|1
- Target migration records: adminapi.0001_cart_discount_settings
- Django system check passed; 17 migration-guard unit tests passed.

## Artifacts
- STOKIT_POSTGRESQL_PHASE2_DDL_CANDIDATE.sql — review-only; not approved for target execution.
- STOKIT_POSTGRESQL_PHASE2_CHANGE_MANIFEST.json — migration/object inventory and remaining blockers.
- STOKIT_POSTGRESQL_PHASE2_DDL_VALIDATION_ROLLBACK.sql — validation transaction source, intended only for the isolated restore database.
- STOKIT_POSTGRESQL_PHASE2_DDL_VALIDATION_REPORT.md — PostgreSQL validation result.
- STOKIT_BACKUP_RESTORE_GATE_REPORT.md — backup/restore evidence.
- STOKIT_SCHEMA_DECISIONS_BLOCKERS.md — updated S15/S16 status.

## Important scope limitation
The candidate covers only Django-managed accounts, auth, and contenttypes tables. It does not convert the 29 candidate legacy business tables from the MariaDB dump. Those tables require approved scope, type/collation/index/trigger/timezone decisions, and source dependency review. This candidate is not a complete production-ready StokIt schema and must not be applied directly.

## Remaining blockers
- S01: approve exact table scope and dependency review for excluded tables.
- S02: decide legacy admins ID allocation and username/email uniqueness.
- S03: approve role bootstrap policy for first React SUPER_ADMIN.
- S04-S12: resolve source collation, prefix index, ENUM, boolean, timestamp, trigger, checkout ID, JSON, and timezone semantics.
- S13: confirm auth/contenttypes scope and migration dependencies for requested Django superuser.
- S14: reconcile migration history with the existing adminapi migration without faking or rewriting history.
- S17: independently explain the previously reported tuple-count discrepancy.
- S18: reconcile dependencies for excluded legacy tables.

## Safety outcome
- No migrations applied to stokit_postgres_dev.
- No Django superuser or React admin created.
- No legacy SQL dump data imported.
- No PHP or Flutter source files modified.
- Existing target tables and migration history preserved.
- The isolated restore database is retained and must not be mistaken for the application database.
