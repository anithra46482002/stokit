# StokIt Schema Validation Status

Generated: 2026-10-15T20:44:36+05:30

## Results

- **Source DDL structural comparison: PASS.** The original and sanitized dumps each have 45 `CREATE TABLE`, 92 `ALTER TABLE`, 39 `INSERT`, and one `CREATE TRIGGER` statement. Table-name sets match; whitespace-normalized `CREATE TABLE` and `ALTER TABLE` definition fingerprints match.
- **Target read-only audit: PASS.** Connected to `stokit_postgres_dev/public` on local PostgreSQL. Existing tables and counts are recorded in `STOKIT_POSTGRESQL_TARGET_READONLY_AUDIT.md`.
- **Tuple audit: PARTIAL.** The sanitized dump scanner reports 3,224 tuples under both escape modes, and the original standard-escape scan reports 3,224. The original no-backslash scan timed out. A previously reported 3,219-versus-3,224 discrepancy is not reproduced by the completed scans but is not independently explained.
- **PostgreSQL grammar validation: PARTIAL.** PostgreSQL validated the generated Django-managed candidate in a BEGIN/ROLLBACK transaction on the isolated restore database. Legacy business-schema conversion DDL remains ungenerated and unvalidated.
- **Semantic conversion validation: BLOCKED.** See `STOKIT_SCHEMA_DECISIONS_BLOCKERS.md`.
- **Recovery validation: PASS.** Custom-format target backup restored to an isolated database; exact public table names, row counts, and migration records matched. See STOKIT_BACKUP_RESTORE_GATE_REPORT.md.

## Explicit safety outcome

No DDL/DML was executed against the application target. Candidate DDL was executed only in a rollback transaction against the isolated restore database.

**Decision:** the source schema inventory is structurally reconciled, but the target schema is **not yet approved for implementation**. Regenerate a review-only PostgreSQL DDL candidate from approved scope/decisions, validate it with a real PostgreSQL parser, review the operation manifest, and complete the backup/restore gate before any database write.
