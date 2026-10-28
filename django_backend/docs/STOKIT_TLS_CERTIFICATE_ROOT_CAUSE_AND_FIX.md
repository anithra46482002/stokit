# StokIt TLS certificate verification — diagnosis report

**Status: PARTIAL — the affected Flutter/Dio client is not verified.** No TLS verification bypass was introduced.

## Workspace and scope
- Cody workspace `stokit` resolves to `C:\Users\.MSI\Downloads\StokIt Backend`.
- Backend inspected: `django_backend/config/settings.py`, `django_backend/config/urls.py`, and existing deployment/API audit docs.
- Flutter source was not inspected or changed because the established project scope is backend-only.

## Observed error
The mobile screenshot reports `CERTIFICATE_VERIFY_FAILED: self signed certificate in certificate chain` from Dio/Flutter during TLS handshake. This occurs before HTTP authentication and is not a username/password error.

## Read-only endpoint evidence
On 2026-10-19, from the Windows environment running Cody: `curl.exe --noproxy \*\ -sS -o NUL -w \GET_status=%{http_code}