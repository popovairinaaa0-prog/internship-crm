"""Тонкая обёртка над httpx для походов в Django API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from . import settings as bot_settings

logger = logging.getLogger(__name__)


class CrmApiError(Exception):
    pass


class CrmApiClient:
    """Синхронный клиент. aiogram-хендлеры вызывают его через to_thread.

    Делать асинхронный httpx.AsyncClient можно, но синхронный проще
    тестировать и держать в голове, а количество запросов в нашем
    объёме (~500 студентов) совсем не критично.
    """

    def __init__(
        self,
        base_url: str | None = None,
        bot_api_token: str | None = None,
        timeout: float = 10.0,
    ):
        self._base = (base_url or bot_settings.CRM_API_BASE_URL).rstrip("/")
        self._token = bot_api_token or bot_settings.BOT_API_TOKEN
        self._client = httpx.Client(
            base_url=self._base,
            headers={"X-Bot-Token": self._token},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CrmApiClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- Endpoints ----------------------------------------------------

    def consume_invite(self, token: str, chat_id: int) -> dict[str, Any]:
        """POST /api/students/consume-invite/. Возвращает JSON от сервера."""
        return self._post("/api/students/consume-invite/", {"token": token, "chat_id": chat_id})

    def consume_manager_invite(self, token: str, chat_id: int) -> dict[str, Any]:
        """POST /api/managers/consume-invite/ для служебного бота."""
        return self._post("/api/managers/consume-invite/", {"token": token, "chat_id": chat_id})

    def register_manual_contact(
        self,
        student_id: int,
        broadcast_job_id: int | None,
        manager_telegram_id: int,
    ) -> dict[str, Any]:
        """POST /api/manual-contacts/ — toggle ручной отметки."""
        return self._post(
            "/api/manual-contacts/",
            {
                "student_id": student_id,
                "broadcast_job_id": broadcast_job_id,
                "manager_telegram_id": manager_telegram_id,
            },
        )

    # --- low level ---------------------------------------------------

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._client.post(path, json=payload)
        except httpx.RequestError as exc:
            logger.warning("api %s: сеть упала: %s", path, exc)
            raise CrmApiError(f"network error: {exc}") from exc

        if resp.status_code == 401:
            raise CrmApiError("unauthorized — проверь BOT_API_TOKEN")
        if resp.status_code >= 500:
            raise CrmApiError(f"server error: HTTP {resp.status_code}")
        return resp.json()
