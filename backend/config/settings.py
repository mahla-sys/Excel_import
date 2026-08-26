"""
Django settings for the School Data Intake Portal.

All environment-specific values are read from the environment so the same
image can run locally and in production. Never commit a real .env file.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
# In production, fail loudly if a critical setting is missing instead of
# silently falling back to insecure defaults (which would expose stack
# traces and allow cookie/secret forgery if a .env failed to load).
SECRET_KEY = _env("SECRET_KEY", "")
DEBUG = _env_bool("DEBUG", False)
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
SECURE = _env_bool("DJANGO_SECURE", False)

if not SECRET_KEY:
    if DEBUG:
        # Local development only — never used in production.
        SECRET_KEY = "dev-only-insecure-key-change-me-please-32bytes-minimum-0123456789"
    else:
        # Fail loudly: starting without a SECRET_KEY in production would
        # mean every session cookie and JWT is signed with an empty key,
        # allowing trivial forgery. Better to refuse to boot.
        import sys

        if "pytest" in sys.modules or "test" in sys.argv:
            # Test suite runs with a deterministic key.
            SECRET_KEY = "test-only-key-not-for-production-0123456789"
        else:
            raise RuntimeError(
                "SECRET_KEY is not set. Refusing to start in production mode "
                "(DEBUG=0). Set a strong SECRET_KEY in the environment."
            )

# Auth model (custom)
AUTH_USER_MODEL = "accounts.PortalUser"

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # Local
    "apps.core",
    "apps.audit",
    "apps.accounts",
    "apps.schools",
    "apps.intake",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "config.middleware.CsrfProtectMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.AuditContextMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
if _env("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _env("POSTGRES_DB"),
            "USER": _env("POSTGRES_USER"),
            "PASSWORD": _env("POSTGRES_PASSWORD"),
            "HOST": _env("POSTGRES_HOST", "db"),
            "PORT": _env("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# I18N / L10N
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "fa-ir"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / media / private storage
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# PRIVATE_STORAGE_ROOT is OUTSIDE MEDIA_ROOT and is never served directly.
PRIVATE_STORAGE_ROOT = Path(
    _env("PRIVATE_STORAGE_ROOT", str(BASE_DIR / "private_files"))
)
PRIVATE_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

# Don't 301-redirect URLs that lack a trailing slash; export routes like
# /export/errors don't end with a slash and must respond directly.
APPEND_SLASH = False

# Upload limits
MAX_UPLOAD_SIZE_MB = int(_env("MAX_UPLOAD_SIZE_MB", "10"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
MAX_UPLOAD_ROWS = int(_env("MAX_UPLOAD_ROWS", "5000"))
ALLOWED_UPLOAD_EXTENSIONS = {".xlsx"}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DRF / JWT
# ---------------------------------------------------------------------------
ACCESS_COOKIE_NAME = _env("ACCESS_COOKIE_NAME", "access_token")
REFRESH_COOKIE_NAME = _env("REFRESH_COOKIE_NAME", "refresh_token")
CSRF_COOKIE_NAME = _env("CSRF_COOKIE_NAME", "csrf_token")
COOKIE_SECURE = _env_bool("COOKIE_SECURE", not DEBUG)
COOKIE_SAMESITE = _env("COOKIE_SAMESITE", "Lax")
COOKIE_DOMAIN = _env("COOKIE_DOMAIN") or None

JWT_ACCESS_LIFETIME = timedelta(minutes=int(_env("JWT_ACCESS_LIFETIME_MIN", "30")))
JWT_REFRESH_LIFETIME = timedelta(days=int(_env("JWT_REFRESH_LIFETIME_DAYS", "7")))

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": JWT_ACCESS_LIFETIME,
    "REFRESH_TOKEN_LIFETIME": JWT_REFRESH_LIFETIME,
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    # We read the token from a cookie, but keep the header name for compat.
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.CookieJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/min",
        "user": "300/min",
        # Aggressive per-IP limit on /auth/login/.
        "login": "10/min",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "School Data Intake Portal API",
    "DESCRIPTION": "ورود، استانداردسازی و اعتبارسنجی داده‌ی ثبت‌نام مدارس",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------------------------------------------------------------------
# CORS (needed for Vite dev server; in docker same-origin via nginx)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = _env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8080"
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# ---------------------------------------------------------------------------
# Production hardening
# ---------------------------------------------------------------------------
if SECURE:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------------
# Logging (structured, but never log sensitive data)
# ---------------------------------------------------------------------------
LOG_LEVEL = _env("LOG_LEVEL", "INFO")
LOG_PRETTY = _env_bool("LOG_PRETTY", DEBUG)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "django.security": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "apps": {"level": LOG_LEVEL, "handlers": ["console"], "propagate": False},
    },
}
