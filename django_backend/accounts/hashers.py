"""Verify / create password hashes compatible with PHP password_hash()/password_verify().

Existing accounts use bcrypt ($2y$) and Argon2id ($argon2id$). Both are accepted; new
hashes are Argon2id, which PHP's password_verify() also accepts (so the legacy PHP admin
keeps working during a parallel run).
"""
import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_argon = PasswordHasher()


def verify_php_password(password: str, stored: str) -> bool:
    if not password or not stored:
        return False
    try:
        if stored.startswith("$argon2"):
            return _argon.verify(stored, password)
        if stored[:4] in ("$2y$", "$2a$", "$2b$", "$2x$"):
            # PHP bcrypt ignores bytes after 72; bcrypt>=5 raises, so truncate like PHP.
            raw = password.encode("utf-8")[:72]
            return bcrypt.checkpw(raw, ("$2b$" + stored[4:]).encode("ascii"))
    except (VerificationError, InvalidHashError, ValueError):
        return False
    return False


def hash_password(password: str) -> str:
    return _argon.hash(password)  # "$argon2id$..."
