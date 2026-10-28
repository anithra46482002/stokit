"""Session allocation / validation for Flutter customer logins."""
import hashlib
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from legacydb.models import LegacyUser

from .models import UserDeviceSession


class SessionLimitReached(Exception):
    """User already has MAX_ACTIVE_SESSIONS active sessions."""


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_hex(32)  # 64 hex chars, same shape as the PHP tokens


def parse_bearer(header_value: str) -> str:
    """Same parsing as PHP token.php: /Bearer\\s+(.+)/i, trimmed; '' when absent."""
    if not header_value:
        return ""
    m = re.search(r"Bearer\s+(.+)", header_value, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def expire_stale_sessions(user_id, now):
    """Mark sessions that are past expiry / inactivity as revoked ('expired') so they stop counting."""
    stale = Q(revoked_at__isnull=True) & Q(expires_at__lte=now)
    days = settings.SESSION_INACTIVITY_DAYS
    if days and days > 0:
        stale |= Q(revoked_at__isnull=True) & Q(last_activity_at__lte=now - timedelta(days=days))
    return UserDeviceSession.objects.filter(user_id=user_id).filter(stale).update(
        revoked_at=now, revoked_reason="expired"
    )


def create_session(user_id, user_agent="", ip=None):
    """Create a session or raise SessionLimitReached. Returns the RAW token (never stored).

    Concurrency: the user's row in `users` is locked with SELECT ... FOR UPDATE inside the
    transaction, so concurrent logins for the SAME account are serialised by InnoDB and
    cannot both pass the count check. Different accounts do not block each other.
    """
    with transaction.atomic():
        LegacyUser.objects.select_for_update().only("id").get(pk=user_id)
        now = timezone.now()
        expire_stale_sessions(user_id, now)
        active = UserDeviceSession.objects.active(now).filter(user_id=user_id).count()
        # None means unlimited; a positive integer enforces the configured cap.
        if settings.MAX_ACTIVE_SESSIONS is not None and active >= settings.MAX_ACTIVE_SESSIONS:
            raise SessionLimitReached()
        raw = new_token()
        UserDeviceSession.objects.create(
            user_id=user_id,
            token_hash=hash_token(raw),
            created_at=now,
            last_activity_at=now,
            user_agent=(user_agent or "")[:255],
            ip_address=ip or None,
        )
    return raw


def authenticate_token(raw_token):
    """Return (session, user_dict) for an active session token, else None."""
    if not raw_token:
        return None
    now = timezone.now()
    session = UserDeviceSession.objects.active(now).filter(token_hash=hash_token(raw_token)).first()
    if session is None:
        return None
    user = (
        LegacyUser.objects.filter(pk=session.user_id)
        .values("id", "username", "email", "fullname", "phone", "address")
        .first()
    )
    if user is None:  # account deleted -> session is dead
        return None
    if (now - session.last_activity_at).total_seconds() >= settings.SESSION_TOUCH_INTERVAL_SECONDS:
        # Single conditional UPDATE: safe under concurrency, never extends a revoked session.
        UserDeviceSession.objects.filter(pk=session.pk, revoked_at__isnull=True).update(last_activity_at=now)
    return session, user


def revoke_session(session_id, reason="revoked"):
    return UserDeviceSession.objects.filter(pk=session_id, revoked_at__isnull=True).update(
        revoked_at=timezone.now(), revoked_reason=reason
    )


def revoke_all_for_user(user_id, reason="revoked_all"):
    return UserDeviceSession.objects.filter(user_id=user_id, revoked_at__isnull=True).update(
        revoked_at=timezone.now(), revoked_reason=reason
    )
