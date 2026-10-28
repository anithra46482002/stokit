"""Settings. All secrets/credentials come from the environment (.env). There is
deliberately NO SQLite fallback: if the database is unreachable Django reports it."""
import os
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# The environment file defaults to .env.postgres (PostgreSQL is the only supported database).
# Another file can be selected with DJANGO_ENV_FILE (absolute path or relative to this Django
# backend). The legacy .env / .env.test files are no longer read unless selected explicitly.
_env_file_setting = os.environ.get("DJANGO_ENV_FILE")
ENV_FILE = Path(_env_file_setting) if _env_file_setting else (BASE_DIR / ".env.postgres")
if not ENV_FILE.is_absolute():
    ENV_FILE = BASE_DIR / ENV_FILE
# Keep real process environment variables authoritative over local env-file values.
if ENV_FILE.is_file():
    load_dotenv(dotenv_path=ENV_FILE, override=False)


def env(name, default=None, required=False):
    val = os.environ.get(name, default)
    if required and (val is None or val == ""):
        raise ImproperlyConfigured(f"Environment variable {name} is required (see .env.example)")
    return val


def env_bool(name, default="0"):
    return str(env(name, default)).lower() in ("1", "true", "yes", "on")


SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)
DEBUG = env_bool("DJANGO_DEBUG", "0")
# Minimum pre-credit order total required to place an order; preserve the legacy ₹100 default.
STOKIT_MIN_ORDER_VALUE = Decimal(env("STOKIT_MIN_ORDER_VALUE", "0.00"))
if STOKIT_MIN_ORDER_VALUE < 0:
    raise ImproperlyConfigured("STOKIT_MIN_ORDER_VALUE must be zero or greater")
# Explicit opt-in for serving local uploads during local/ngrok API testing.
SERVE_LOCAL_UPLOADS = env_bool("SERVE_LOCAL_UPLOADS", "0")
# Behind ngrok/a reverse proxy the app sees plain HTTP; trust X-Forwarded-Proto ONLY when explicitly enabled so
# absolute image URLs built from the request are https (avoids mixed-content blocking in the browser/app).
if env_bool("TRUST_X_FORWARDED_PROTO", "0"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DJANGO_ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")  # tunnel hosts (ngrok) belong in the env file, not in source
ALLOWED_HOSTS = [host.strip() for host in DJANGO_ALLOWED_HOSTS.split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "legacydb",
    "accounts",
    "legacy_api",
    "adminapi",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
APPEND_SLASH = False  # legacy URLs are exact (/login, /acc/ ...)

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
}]

# PostgreSQL is the ONLY supported database. There is no MySQL/MariaDB branch and no
# fallback: if the configuration is missing or the server is unreachable Django fails
# with a clear error instead of silently using another database.
_POSTGRES_ENGINE = "django.db.backends.postgresql"
_DB_ENGINE = (env("DB_ENGINE", _POSTGRES_ENGINE) or _POSTGRES_ENGINE).strip().lower()
if _DB_ENGINE != _POSTGRES_ENGINE:
    raise ImproperlyConfigured(
        "Unsupported DB_ENGINE. StokIt supports only 'django.db.backends.postgresql'; "
        "remove DB_ENGINE or set it to that value (MySQL/MariaDB is no longer supported)."
    )
_DB_PORT = env("DB_PORT", "5432") or "5432"
if str(_DB_PORT).strip() == "3306":
    raise ImproperlyConfigured(
        "DB_PORT=3306 is the MariaDB/MySQL default port. StokIt uses PostgreSQL only "
        "(normally port 5432); check the environment file selected by DJANGO_ENV_FILE."
    )

DATABASES = {
    "default": {
        "ENGINE": _POSTGRES_ENGINE,
        "NAME": env("DB_NAME", required=True),
        "USER": env("DB_USER", required=True),
        "PASSWORD": env("DB_PASSWORD", required=True),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": str(_DB_PORT).strip(),
        "CONN_MAX_AGE": 60,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "UTC")
USE_TZ = False  # legacy columns are naive DATETIME/TIMESTAMP values

STATIC_URL = "static/"
MEDIA_ROOT = Path(env("MEDIA_ROOT") or (BASE_DIR / "media_legacy"))
LEGACY_BASE_URL = env("LEGACY_BASE_URL", "https://app.stokitb2b.com/admin/manage/")

# Use MAX_ACTIVE_SESSIONS=unlimited (or infinity/0) to disable the concurrent-session cap.
# A positive integer keeps a finite cap for deployments that require it.
_raw_max_active_sessions = str(env("MAX_ACTIVE_SESSIONS", "unlimited")).strip().lower()
MAX_ACTIVE_SESSIONS = None if _raw_max_active_sessions in {"unlimited", "infinity", "inf", "none", "0"} else int(_raw_max_active_sessions)
if MAX_ACTIVE_SESSIONS is not None and MAX_ACTIVE_SESSIONS < 1:
    raise ImproperlyConfigured("MAX_ACTIVE_SESSIONS must be a positive integer or 'unlimited'")
SESSION_INACTIVITY_DAYS = int(env("SESSION_INACTIVITY_DAYS", "30"))  # 0 disables inactivity expiry
SESSION_TOUCH_INTERVAL_SECONDS = int(env("SESSION_TOUCH_INTERVAL_SECONDS", "300"))

# --- React admin API ------------------------------------------------------
ADMIN_TOKEN_MAX_AGE_SECONDS = int(env("ADMIN_TOKEN_MAX_AGE_SECONDS", "28800"))
CORS_ALLOWED_ORIGINS = [o.strip() for o in env("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
CORS_URLS_REGEX = r"^/admin-api/.*$"  # legacy Flutter routes keep their own CORS behaviour

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["adminapi.auth.AdminTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "adminapi.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "UNAUTHENTICATED_USER": None,
}

# Default is the dummy backend: the console backend prints the whole message, including the password-reset
# OTP, to the server log. Set EMAIL_BACKEND explicitly (SMTP in production) to actually deliver reset codes.
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.dummy.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@localhost")
PASSWORD_RESET_OTP_TTL_SECONDS = 600
PASSWORD_RESET_OTP_MAX_ATTEMPTS = 5
# Django's built-in admin is intentionally NOT installed (it would need auth/session/admin tables
# in the legacy database). The administration UI is the React app; /admin and /admin/ redirect to it.
# Empty value => no redirect is registered (e.g. in production, where the SPA is hosted elsewhere).
ADMIN_FRONTEND_URL = env("ADMIN_FRONTEND_URL", "http://127.0.0.1:5173/" if DEBUG else "")