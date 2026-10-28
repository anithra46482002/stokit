import hashlib
import hmac
import secrets
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from accounts.hashers import hash_password
from accounts.models import PasswordResetOTP
from legacydb.models import LegacyUser
from .common import as_dict, jr, json_body, legacy_view

GENERIC = {"success": True, "message": "If the account is eligible, reset instructions will be sent."}

def _otp_digest(user_id, otp):
    material = f"stokit-reset:{user_id}:{otp}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), material, hashlib.sha256).hexdigest()

def _scalar_text(value):
    """Stripped text of a JSON string/integer; '' for null, bool, list, object, float or NUL-containing text."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return ""
    text = str(value).strip()
    return "" if "\x00" in text else text


def _identity(data):
    """First usable identity among email, username (null/empty/non-scalar values are skipped)."""
    return _scalar_text(data.get("email")) or _scalar_text(data.get("username"))


@legacy_view(auth=False)
def request_reset(request):
    if request.method != "POST":
        return jr({"success": False, "message": "Only POST allowed"}, 405)
    data = as_dict(json_body(request))
    identity = _identity(data)
    if not identity:
        return jr(GENERIC)
    user = LegacyUser.objects.filter(email=identity).first() or LegacyUser.objects.filter(username=identity).first()
    if not user:
        return jr(GENERIC)
    now = timezone.now()
    with transaction.atomic():
        locked_user = LegacyUser.objects.select_for_update().filter(pk=user.pk).first()
        if not locked_user:
            return jr(GENERIC)
        recent = PasswordResetOTP.objects.filter(
            user_id=locked_user.pk, created_at__gte=now-timedelta(hours=1)
        ).count()
        if recent >= 3:
            return jr(GENERIC)
        otp = f"{secrets.randbelow(1_000_000):06d}"
        PasswordResetOTP.objects.filter(user_id=locked_user.pk, consumed_at__isnull=True).update(consumed_at=now)
        PasswordResetOTP.objects.create(
            user_id=locked_user.pk, otp_hash=_otp_digest(locked_user.pk, otp),
            created_at=now, expires_at=now+timedelta(seconds=settings.PASSWORD_RESET_OTP_TTL_SECONDS)
        )
    # Do not log or return the OTP. Production must configure an actual mail backend.
    send_mail("StokIt password reset code", f"Your reset code is {otp}. It expires in 10 minutes.",
        settings.DEFAULT_FROM_EMAIL, [locked_user.email], fail_silently=True)
    return jr(GENERIC)

@legacy_view(auth=False)
def reset_password(request):
    if request.method != "POST":
        return jr({"success": False, "message": "Only POST allowed"}, 405)
    data = as_dict(json_body(request))
    identity = _identity(data)
    otp = _scalar_text(data.get("otp"))
    password = data.get("new_password")
    if password is None:
        password = data.get("password")
    if not isinstance(password, str):  # a list/number/bool must never be stringified into a password
        password = ""
    if not identity or len(otp) != 6 or not otp.isdigit() or len(password) < 10:
        return jr({"success": False, "message": "Invalid reset request"}, 400)
    user = LegacyUser.objects.filter(email=identity).first() or LegacyUser.objects.filter(username=identity).first()
    if not user:
        return jr({"success": False, "message": "Invalid or expired reset code"}, 400)
    now = timezone.now()
    with transaction.atomic():
        record = PasswordResetOTP.objects.select_for_update().filter(user_id=user.pk, consumed_at__isnull=True).order_by("-created_at").first()
        if not record or record.expires_at <= now or record.attempts >= settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS:
            return jr({"success": False, "message": "Invalid or expired reset code"}, 400)
        expected = _otp_digest(user.pk, otp)
        if not hmac.compare_digest(record.otp_hash, expected):
            record.attempts += 1
            if record.attempts >= settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS:
                record.consumed_at = now
            record.save(update_fields=["attempts", "consumed_at"])
            return jr({"success": False, "message": "Invalid or expired reset code"}, 400)
        # Consume before changing password in the same transaction: OTP cannot be reused.
        record.consumed_at = now
        record.verified_at = now
        record.save(update_fields=["consumed_at", "verified_at"])
        LegacyUser.objects.filter(pk=user.pk).update(password=hash_password(password))
    return jr({"success": True, "message": "Password reset successful"})
