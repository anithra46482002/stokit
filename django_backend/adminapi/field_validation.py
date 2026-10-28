"""Shared syntax validators for admin email and Indian mobile fields.

Mobile validation accepts formatted Indian 10-digit numbers and optional +91/leading 0.
Stored values are trimmed but not rewritten, preserving legacy API/data representations.
"""
import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

def clean_text(value):
    """str(value).strip() for real values; JSON null becomes "" (never the literal string 'None')."""
    return "" if value is None else str(value).strip()


_MOBILE_ALLOWED = re.compile(r"^[+0-9()\s-]+$")

def normalize_indian_mobile(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    if not _MOBILE_ALLOWED.fullmatch(raw):
        return None
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("91") and (raw.startswith("+91") or len(digits) == 12):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if re.fullmatch(r"[6-9]\d{9}", digits) else None

def clean_email(value, required=True):
    email = str(value or "").strip()
    if not email:
        if required:
            return "", "Email address is required."
        return "", ""
    if len(email) > 254 or ".." in email:
        return email, "Enter a valid email address, such as name@gmail.com."
    try:
        validate_email(email)
    except ValidationError:
        return email, "Enter a valid email address, such as name@gmail.com."
    local = email.rsplit("@", 1)[0]
    if len(local) > 64 or local.startswith(".") or local.endswith("."):
        return email, "Enter a valid email address, such as name@gmail.com."
    return email, ""

def clean_indian_mobile(value, required=False):
    raw = str(value or "").strip()
    if not raw:
        return ("", "Mobile number is required.") if required else ("", "")
    if normalize_indian_mobile(raw) is None:
        return raw, "Enter a valid 10-digit Indian mobile number, optionally with +91."
    # Preserve the caller's formatted representation for compatibility with legacy records.
    return raw, ""