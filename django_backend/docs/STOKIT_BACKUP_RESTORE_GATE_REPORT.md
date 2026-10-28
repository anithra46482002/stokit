# StokIt PostgreSQL Backup and Restore Gate

Generated: 2026-10-15T21:05:01.7401024+05:30

## Result
**PASS** — custom-format backup created, archive listing checked, restored into an isolated database, and table counts/migration records compared.

## Target
- Database: stokit_postgres_dev
- Endpoint: 127.0.0.1:5432/public
- Backup path: C:\Users\.MSI\Downloads\StokIt Backend\django_backend\backups\stokit_postgres_dev_pre_phase2_20261015_210457.dump
- Backup size: 5117 bytes
- Archive listing entries: 26
- Isolated restore database: stokit_phase2_restore_verify_20261015_210457
- Source/restored table-count rows: 3 / 3
- Migration records: 1 / 1
- Inventory match: True

## Safety
- Target database was inspected and backed up; no target DDL/DML was executed.
- No Django migrations applied, no accounts created, no historical SQL dump imported.
- Isolated restore database is retained for inspection.
- Credentials are not included.
