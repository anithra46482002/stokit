# StokIt Phase 2 DDL Candidate Validation

Generated: 2026-10-15T21:07:01.6491148+05:30

**PostgreSQL grammar and semantic validation: PASS for this candidate only.**
- Candidate: STOKIT_POSTGRESQL_PHASE2_DDL_CANDIDATE.sql
- Validation database: stokit_phase2_restore_verify_20261015_210457 (isolated restore copy)
- Method: candidate DDL executed inside BEGIN/ROLLBACK; transaction rolled back.
- CREATE TABLE objects: accounts_adminroleassignment, accounts_checkoutpayload, accounts_devicetoken, accounts_passwordresetotp, accounts_userdevicesession, auth_group, auth_group_permissions, auth_permission, auth_user, auth_user_groups, auth_user_user_permissions, django_content_type
- CREATE INDEX objects: accounts_adminroleassignment_principal_id_51619b8f, accounts_checkoutpayload_user_id_844396af, accounts_devicetoken_user_id_f7979080, accounts_passwordresetotp_user_id_b1de1bbc, accounts_userdevicesession_token_hash_93c1e511_like, accounts_userdevicesession_user_id_cced2c8b, auth_group_name_a6ea08ec_like, auth_group_permissions_group_id_b120cbf9, auth_group_permissions_permission_id_84c5c92e, auth_permission_content_type_id_2f476e4b, auth_user_groups_group_id_97559544, auth_user_groups_user_id_6a12ed8b, auth_user_user_permissions_permission_id_1fbb5f2c, auth_user_user_permissions_user_id_a95ead1b, auth_user_username_6821ab7c_like, uds_user_revoked_idx
- ALTER TABLE targets: accounts_adminroleassignment, auth_group, auth_group_permissions, auth_permission, auth_user, auth_user_groups, auth_user_user_permissions, django_content_type
- No INSERT statements are present.
- Legacy business schema conversion remains incomplete and unvalidated.
