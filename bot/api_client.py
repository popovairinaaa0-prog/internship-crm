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
        try:
            resp = self._client.post(
                "/api/students/consume-invite/",
                json={"token": token, "chat_id": chat_id},
            )
        except httpx.RequestError as exc:
            logger.warning("consume_invite: сеть упала: %s", exc)
            raise CrmApiError(f"network error: {exc}") from exc

        if resp.status_code == 401:
            raise CrmApiError("unauthorized — проверь BOT_API_TOKEN")
        if resp.status_code >= 500:
            raise CrmApiError(f"server error: HTTP {resp.status_code}")
        return resp.json()
