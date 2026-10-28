"""Safe classification and logging of database errors.

Logs the error class, the PostgreSQL SQLSTATE and the first line of the driver message with
credentials scrubbed. It never logs request data, SQL parameters, row values or tracebacks, so the
actual cause of a failure (missing table, permission, authentication, connection) is visible in the
server log without exposing secrets or customer data.
"""
import logging
import re

from django.conf import settings
from django.db import DatabaseError, InterfaceError, OperationalError

logger = logging.getLogger("adminapi.db")

_URI_PASSWORD = re.compile(r"(\w+://[^:/@\s]+:)[^@\s]+@")
_KEY_VALUE_SECRET = re.compile(r"(?i)\b(password|passwd|pwd|secret|token)\s*=\s*\S+")


def scrub(text):
    """Remove the configured database password and obvious credential patterns from text."""
    text = str(text or "")
    password = str((getattr(settings, "DATABASES", {}).get("default") or {}).get("PASSWORD") or "")
    if len(password) >= 3:
        text = text.replace(password, "***")
    text = _URI_PASSWORD.sub(r"\1***@", text)
    return _KEY_VALUE_SECRET.sub(lambda m: m.group(1) + "=***", text)


def sqlstate(exc):
    """SQLSTATE of a (possibly Django-wrapped) driver error, or None."""
    seen = 0
    current = exc
    while current is not None and seen < 4:
        code = getattr(current, "sqlstate", None) or getattr(current, "pgcode", None)
        if code:
            return str(code)
        current = current.__cause__ or current.__context__
        seen += 1
    return None


def classify(exc):
    """Return (category, sqlstate). Categories are stable machine-readable codes."""
    state = sqlstate(exc)
    if state == "42P01":
        category = "table_missing"
    elif state == "42501":
        category = "permission_denied"
    elif state == "3D000":
        category = "database_missing"
    elif state and state.startswith("28"):
        category = "authentication_failed"
    elif (state and state.startswith(("08", "57"))) or (not state and isinstance(exc, (OperationalError, InterfaceError))):
        category = "database_unavailable"
    else:
        category = "database_error"
    return category, state


def log_db_error(context, exc):
    """Log a sanitized database error and return (category, sqlstate)."""
    category, state = classify(exc)
    # Only driver errors carry a message that is safe to log (first line, no DETAIL/values); for any
    # other exception type only the class name is logged so request data cannot leak.
    first_line = "-"
    if isinstance(exc, (DatabaseError, InterfaceError)):
        lines = str(exc).splitlines()
        first_line = scrub(lines[0] if lines else "")[:300]
    logger.error(
        "%s failed: category=%s type=%s sqlstate=%s message=%s",
        context, category, type(exc).__name__, state or "-", first_line,
    )
    return category, state
