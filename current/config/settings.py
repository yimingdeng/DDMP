import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

env_file = os.getenv("DJANGO_ENV_FILE", str(BASE_DIR / ".env"))
load_dotenv(env_file)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


ENVIRONMENT = os.getenv("DJANGO_ENV", "development").strip().lower()
DEBUG = env_bool("DJANGO_DEBUG", ENVIRONMENT == "development")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if ENVIRONMENT == "production":
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in production.")
    SECRET_KEY = "insecure-sprint1-development-key-change-me"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core.apps.CoreConfig",
    "varieties.apps.VarietiesConfig",
    "sites.apps.SitesConfig",
    "media_assets.apps.MediaAssetsConfig",
    "inquiries.apps.InquiriesConfig",
    "campaigns.apps.CampaignsConfig",
    "analytics.apps.AnalyticsConfig",
    "collection.apps.CollectionConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "inquiries.middleware.CampaignSourceMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "analytics.middleware.PublicVisitMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "core.middleware.MobilePreviewFrameOptionsMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_configuration",
                "inquiries.context_processors.contact_service",
                "collection.context_processors.collection_role",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

database_url = os.getenv("DATABASE_URL", "").strip()
if database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            database_url,
            conn_max_age=60,
            conn_health_checks=True,
        )
    }
elif ENVIRONMENT == "production":
    raise ImproperlyConfigured("DATABASE_URL is required in production.")
else:
    local_dir = BASE_DIR / ".local"
    local_dir.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": local_dir / "db.sqlite3"}
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(os.getenv("STATIC_ROOT", str(BASE_DIR / ".local" / "static")))
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / ".local" / "media")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "collection:login"
LOGIN_REDIRECT_URL = "collection:dashboard"
LOGOUT_REDIRECT_URL = "collection:login"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", ENVIRONMENT == "production")
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", ENVIRONMENT == "production")
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", ENVIRONMENT == "production")
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

WECHAT_OFFICIAL_ACCOUNT_APP_ID = os.getenv("WECHAT_OFFICIAL_ACCOUNT_APP_ID", "").strip()
WECHAT_OFFICIAL_ACCOUNT_APP_SECRET = os.getenv("WECHAT_OFFICIAL_ACCOUNT_APP_SECRET", "").strip()
WECHAT_JS_SDK_ENABLED = env_bool(
    "WECHAT_JS_SDK_ENABLED",
    bool(WECHAT_OFFICIAL_ACCOUNT_APP_ID and WECHAT_OFFICIAL_ACCOUNT_APP_SECRET),
)
WECHAT_JS_API_DEBUG = env_bool("WECHAT_JS_API_DEBUG", False)

LOG_DIR = Path(os.getenv("LOG_DIR", str(BASE_DIR / ".local" / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name} request_id={request_id} {message}",
            "style": "{",
            "defaults": {"request_id": "-"},
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "application.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "standard",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
    },
}
