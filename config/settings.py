import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "your-default-secret")
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = (
    os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if os.environ.get("DJANGO_ALLOWED_HOSTS")
    else []
)


# Application definition
THERD_PARTY_APPS = [
    "minio_storage",
    "celery",
    "django_celery_beat",
    "django_celery_results",
    "django_minio_backend.apps.DjangoMinioBackendConfig",
]

LOCLA_APPS = [
    "apps.file_manager",
    "apps.account",
    "apps.telegram_bot.apps.TelegramBotConfig",
]

DEFAULT_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

INSTALLED_APPS = THERD_PARTY_APPS + DEFAULT_APPS + LOCLA_APPS

LOCAL_MIDELWARE = [
    "django.middleware.locale.LocaleMiddleware",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",  # Add this for i18n support
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
] + LOCAL_MIDELWARE

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_USER_MODEL = "account.User"

# # Database

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "")
MINIO_USE_HTTPS = os.environ.get("MINIO_USE_HTTPS", "False") == "True"
MINIO_CONSISTENCY_CHECK_ON_START = False if DEBUG else True
MINIO_PRIVATE_BUCKETS = [
    "django-backend-dev-private",
]
MINIO_PUBLIC_BUCKETS = [
    "django-backend-dev-public",
]
MINIO_POLICY_HOOKS: list[tuple[str, dict]] = []
MINIO_MEDIA_FILES_BUCKET = "media"
MINIO_STATIC_FILES_BUCKET = "static"
MINIO_PRIVATE_BUCKETS.append(MINIO_MEDIA_FILES_BUCKET)
MINIO_PRIVATE_BUCKETS.append(MINIO_STATIC_FILES_BUCKET)
MINIO_BUCKET_CHECK_ON_SAVE = True

# External URL for MinIO accessible through nginx
MINIO_EXTERNAL_ENDPOINT = os.environ.get("MINIO_EXTERNAL_ENDPOINT", "")
MINIO_EXTERNAL_ENDPOINT_USE_HTTPS = False


STORAGES = {
    "default": {
        "BACKEND": "apps.file_manager.storage.DispositionMinioBackend",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


DB_SQLILTE_DIR = BASE_DIR / "data" / "db"
DB_SQLILTE_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "db" / "db.sqlite3",
    },
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Logs
LOGDIR = BASE_DIR / "data" / "logs"
LOGDIR.mkdir(parents=True, exist_ok=True)

# Ensure the log file can be created
LOG_FILE = LOGDIR / "app.log"
try:
    LOG_FILE.touch(exist_ok=True)
except (PermissionError, OSError):
    # Fallback to a simpler logging setup if file creation fails
    LOG_FILE = None

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {name} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {name} {asctime} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "minio_storage": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps.telegram_bot": {
            "handlers": ["console"],
            "level": "INFO",  # Changed to DEBUG for better bot logging
            "propagate": False,
        },
        "pyrogram": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Add file handler only if we can create the log file
if LOG_FILE:
    LOGGING["handlers"]["file"] = {
        "level": "DEBUG",
        "class": "logging.handlers.RotatingFileHandler",
        "filename": str(LOG_FILE),
        "maxBytes": 1024 * 1024 * 5,
        "backupCount": 5,
        "formatter": "verbose",
    }
    # Add file handler to all loggers
    for logger_config in LOGGING["loggers"].values():
        if "file" not in logger_config["handlers"]:
            logger_config["handlers"].append("file")
    LOGGING["root"]["handlers"].append("file")

# Internationalization

LANGUAGE_CODE = os.environ.get("DJANGO_LANGUAGE_CODE", "en-us")

LANGUAGES = [
    ("en", "English"),
    ("fa", "Persian"),
    # Add more languages as needed
]

LOCALE_PATHS = [
    BASE_DIR / "apps" / "telegram_bot" / "locale",
]

TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Tehran")

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Add these for better Pyrogram support
PYROGRAM_SESSION_DIR = BASE_DIR / "data" / "pyrogram"
PYROGRAM_SESSION_DIR.mkdir(parents=True, exist_ok=True)

# Default primary key field type

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
