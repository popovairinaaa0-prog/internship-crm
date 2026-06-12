"""Django settings for crm project."""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-&rasu6zr8lzef(orwmsy#bo7wd680m90133j$(o#_7cq__yn*$",
)

DEBUG = os.environ.get("DEBUG", "True").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]


INSTALLED_APPS = [
    # Unfold должен идти ДО django.contrib.admin
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "django_q",
    # local
    "accounts",
    "students",
    "companies",
    "placements",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "crm.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "crm.wsgi.application"


# Database: если DATABASE_URL задан — Postgres, иначе fallback на SQLite.
_database_url = os.environ.get("DATABASE_URL", "").strip()
if _database_url:
    DATABASES = {"default": dj_database_url.parse(_database_url, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# django-q2 — фоновые задачи на Postgres-бэкенде (без Redis)
Q_CLUSTER = {
    "name": "crm",
    "workers": 2,
    "timeout": 90,
    "retry": 120,
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",
}


# Telegram-боты
STUDENT_BOT_TOKEN = os.environ.get("STUDENT_BOT_TOKEN", "")
STUDENT_BOT_USERNAME = os.environ.get("STUDENT_BOT_USERNAME", "")
MANAGERS_BOT_TOKEN = os.environ.get("MANAGERS_BOT_TOKEN", "")
MANAGERS_BOT_USERNAME = os.environ.get("MANAGERS_BOT_USERNAME", "")
MANAGERS_CHAT_ID = os.environ.get("MANAGERS_CHAT_ID", "")
BOT_API_TOKEN = os.environ.get("BOT_API_TOKEN", "")
# Куда бот ходит за Django API. В docker-compose переопределяется на http://web:8000.
CRM_API_BASE_URL = os.environ.get("CRM_API_BASE_URL", "http://localhost:8000")


# Настройки автопушей (см. CLAUDE.md → «Настройки автопушей»)
PLACEMENT_STALE_HIGHLIGHT_DAYS = 7
PLACEMENT_STALE_CRITICAL_DAYS = 14
COMPANY_PAUSE_ALERT_DAYS = 30
PUSH_RULES_TICK_INTERVAL_MINUTES = 60


# --- Unfold: современная тема для админки -------------------------------
UNFOLD = {
    "SITE_TITLE": "Internship CRM",
    "SITE_HEADER": "Internship CRM",
    "SITE_SUBHEADER": "Карьерный центр",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "THEME": None,  # позволяем переключать light/dark
    "COLORS": {
        # Мягкий фиолетовый (Tailwind violet) — не уставает глаз.
        "primary": {
            "50": "245 243 255",
            "100": "237 233 254",
            "200": "221 214 254",
            "300": "196 181 253",
            "400": "167 139 250",
            "500": "139 92 246",
            "600": "124 58 237",
            "700": "109 40 217",
            "800": "91 33 182",
            "900": "76 29 149",
            "950": "46 16 101",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Главное",
                "separator": False,
                "items": [
                    {
                        "title": "Дашборд",
                        "icon": "dashboard",
                        "link": "/admin/",
                    },
                    {
                        "title": "Студенты",
                        "icon": "school",
                        "link": "/admin/students/student/",
                    },
                    {
                        "title": "Компании",
                        "icon": "business",
                        "link": "/admin/companies/company/",
                    },
                    {
                        "title": "Стажировки",
                        "icon": "work",
                        "link": "/admin/placements/placement/",
                    },
                    {
                        "title": "Направления",
                        "icon": "category",
                        "link": "/admin/students/direction/",
                    },
                ],
            },
            {
                "title": "Коммуникации",
                "separator": True,
                "items": [
                    {
                        "title": "Рассылки",
                        "icon": "send",
                        "link": "/admin/notifications/broadcastjob/",
                    },
                    {
                        "title": "Шаблоны",
                        "icon": "description",
                        "link": "/admin/notifications/messagetemplate/",
                    },
                    {
                        "title": "Автопуши",
                        "icon": "notifications_active",
                        "link": "/admin/notifications/pushrule/",
                    },
                    {
                        "title": "Ручные контакты",
                        "icon": "check_circle",
                        "link": "/admin/notifications/manualcontact/",
                    },
                ],
            },
            {
                "title": "Администрирование",
                "separator": True,
                "items": [
                    {
                        "title": "Пользователи",
                        "icon": "person",
                        "link": "/admin/accounts/user/",
                    },
                    {
                        "title": "Группы",
                        "icon": "groups",
                        "link": "/admin/auth/group/",
                    },
                ],
            },
        ],
    },
}


# Логирование — пишем в stdout, агрегацию отдаём docker logs / journald.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "{asctime} {levelname} {name} — {message}",
            "style": "{",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["stdout"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["stdout"],
            "level": "WARNING",
            "propagate": False,
        },
        "django_q": {
            "handlers": ["stdout"],
            "level": "INFO",
            "propagate": False,
        },
        # Приложения проекта
        "accounts": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "students": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "companies": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "placements": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "notifications": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "bot": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
    },
    "root": {
        "handlers": ["stdout"],
        "level": "WARNING",
    },
}
