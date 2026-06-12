"""Хендлеры студенческого бота."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Router
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message

from bot.api_client import CrmApiClient, CrmApiError

logger = logging.getLogger(__name__)

router = Router(name="student_bot")


WELCOME_TEMPLATE = (
    "Привет, {name}! Ты подключился к боту карьерного центра Зерокодера.\n\n"
    "Сюда будут приходить сообщения от твоего менеджера и важные обновления "
    "по стажировке. Если что-то непонятно — пиши менеджеру в личку."
)

NO_TOKEN_MESSAGE = (
    "Чтобы подключиться, попроси менеджера прислать тебе персональную ссылку."
)

INVALID_TOKEN_MESSAGE = "Ссылка устарела или некорректна. Попроси менеджера выдать новую."

INTERNAL_ERROR_MESSAGE = (
    "Что-то пошло не так на стороне сервиса. Попробуй чуть позже — или сообщи менеджеру."
)


def _build_client() -> CrmApiClient:
    """Точка расширения для тестов: подменяем фабрику клиента."""
    return CrmApiClient()


@router.message(CommandStart(deep_link=True))
async def handle_start_with_token(message: Message, command: CommandObject) -> None:
    token = (command.args or "").strip()
    if not token:
        await message.answer(NO_TOKEN_MESSAGE)
        return

    chat_id = message.chat.id
    try:
        result = await asyncio.to_thread(_call_consume_invite, token, chat_id)
    except CrmApiError as exc:
        logger.warning("consume_invite failed: %s", exc)
        await message.answer(INTERNAL_ERROR_MESSAGE)
        return

    if not result.get("ok"):
        await message.answer(INVALID_TOKEN_MESSAGE)
        return

    name = result.get("name") or "друг"
    await message.answer(WELCOME_TEMPLATE.format(name=name))


@router.message(CommandStart())
async def handle_start_without_token(message: Message) -> None:
    await message.answer(NO_TOKEN_MESSAGE)


def _call_consume_invite(token: str, chat_id: int) -> dict:
    with _build_client() as client:
        return client.consume_invite(token=token, chat_id=chat_id)
