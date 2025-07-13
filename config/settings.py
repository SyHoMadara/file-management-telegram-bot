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

LOCAL_MIDELWARE = []

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
# MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "172.19.1.2:9000")
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
MINIO_EXTERNAL_ENDPOINT = "91.99.172.197:8880"
MINIO_EXTERNAL_ENDPOINT_USE_HTTPS = False


STORAGES = {
    "default": {
        "BACKEND": "django_minio_backend.models.MinioBackend",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DB_SQLILTE_DIR =BASE_DIR / "data" / "db"
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

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {name} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGDIR / "app.log",
            "maxBytes": 1024 * 1024 * 5,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": True,
        },
        "django": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "minio_storage": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "apps.telegram_bot.apps.TelegramBotConfig": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Internationalization

LANGUAGE_CODE = os.environ.get("DJANGO_LANGUAGE_CODE", "en-us")

TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Tehran")

USE_I18N = True

USE_TZ = True


# Default primary key field type

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
