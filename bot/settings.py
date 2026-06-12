"""Конфигурация ботов. Читается из .env, без зависимости от Django settings.

Бот — отдельный процесс, в нём незачем грузить Django ORM и весь импорт-граф.
Все нужные значения берутся напрямую из переменных окружения.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Не задана переменная окружения {name}.")
    return value


STUDENT_BOT_TOKEN = os.environ.get("STUDENT_BOT_TOKEN", "").strip()
MANAGERS_BOT_TOKEN = os.environ.get("MANAGERS_BOT_TOKEN", "").strip()
MANAGERS_CHAT_ID = os.environ.get("MANAGERS_CHAT_ID", "").strip()
BOT_API_TOKEN = os.environ.get("BOT_API_TOKEN", "").strip()
CRM_API_BASE_URL = os.environ.get("CRM_API_BASE_URL", "http://localhost:8000").rstrip("/")


def ensure_student_bot() -> str:
    if not STUDENT_BOT_TOKEN:
        raise RuntimeError("STUDENT_BOT_TOKEN пустой — нечего запускать.")
    if not BOT_API_TOKEN:
        raise RuntimeError("BOT_API_TOKEN пустой — бот не сможет авторизоваться в Django.")
    return STUDENT_BOT_TOKEN
