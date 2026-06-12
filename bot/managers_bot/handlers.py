"""Хендлеры служебного бота: онбординг менеджеров и callback ручных отметок."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.api_client import CrmApiClient, CrmApiError

logger = logging.getLogger(__name__)

router = Router(name="managers_bot")


WELCOME_BOUND_TEMPLATE = (
    "Привет, {name}! Аккаунт привязан. Теперь сюда будут приходить уведомления "
    "о студентах, которым нужно написать вручную."
)

NO_TOKEN_MESSAGE = (
    "Привет! Для привязки попроси админа прислать тебе персональную ссылку."
)

INVALID_TOKEN_MESSAGE = (
    "Ссылка устарела или некорректна. Попроси админа выдать новую."
)

INTERNAL_ERROR_MESSAGE = (
    "Что-то пошло не так на стороне сервиса. Попробуй позже."
)

NOT_BOUND_DM = (
    "Прежде чем отмечать контакт, привяжи аккаунт. Попроси админа прислать тебе "
    "персональную ссылку."
)


def _build_client() -> CrmApiClient:
    return CrmApiClient()


# --- /start с токеном --------------------------------------------------


@router.message(CommandStart(deep_link=True))
async def handle_start_with_token(message: Message, command: CommandObject) -> None:
    token = (command.args or "").strip()
    if not token:
        await message.answer(NO_TOKEN_MESSAGE)
        return

    chat_id = message.chat.id
    try:
        result = await asyncio.to_thread(_call_consume_manager_invite, token, chat_id)
    except CrmApiError as exc:
        logger.warning("manager consume_invite failed: %s", exc)
        await message.answer(INTERNAL_ERROR_MESSAGE)
        return

    if not result.get("ok"):
        await message.answer(INVALID_TOKEN_MESSAGE)
        return

    name = result.get("name") or "коллега"
    await message.answer(WELCOME_BOUND_TEMPLATE.format(name=name))


@router.message(CommandStart())
async def handle_start_without_token(message: Message) -> None:
    await message.answer(NO_TOKEN_MESSAGE)


# --- Callback: manual_contact:<student_id>:<job_id> -------------------


@router.callback_query(F.data.startswith("manual_contact:"))
async def handle_manual_contact_callback(callback: CallbackQuery) -> None:
    try:
        _, student_id_str, job_id_str = callback.data.split(":", 2)
        student_id = int(student_id_str)
        job_id: int | None = int(job_id_str) if job_id_str != "null" else None
    except (ValueError, AttributeError):
        await callback.answer("Неверный формат данных.", show_alert=True)
        return

    manager_telegram_id = callback.from_user.id

    try:
        result = await asyncio.to_thread(
            _call_register_manual_contact, student_id, job_id, manager_telegram_id
        )
    except CrmApiError as exc:
        logger.warning("manual_contact failed: %s", exc)
        await callback.answer("Сервис недоступен, попробуй позже.", show_alert=True)
        return

    if not result.get("ok"):
        if result.get("error") == "not_bound":
            # Шлём личку, в групповом чате ничего не меняем
            try:
                await callback.bot.send_message(manager_telegram_id, NOT_BOUND_DM)
            except Exception as exc:  # noqa: BLE001 — лучше не ронять весь callback
                logger.info("can't DM unbound manager %s: %s", manager_telegram_id, exc)
            await callback.answer(
                "Сначала привяжи аккаунт (см. личку с ботом).", show_alert=True
            )
        else:
            await callback.answer(
                f"Ошибка: {result.get('error', 'unknown')}", show_alert=True
            )
        return

    # Перерисовываем только нужную строку клавиатуры
    created = result.get("created", False)
    manager_name = result.get("manager_name", "менеджер")
    await _update_keyboard_row(callback, student_id, job_id, created, manager_name)
    await callback.answer(
        "Отмечено" if created else "Отметка снята"
    )


async def _update_keyboard_row(
    callback: CallbackQuery,
    student_id: int,
    job_id: int | None,
    created: bool,
    manager_name: str,
) -> None:
    """Меняет только одну строку клавиатуры — соответствующую этому студенту."""
    msg = callback.message
    if msg is None or msg.reply_markup is None:
        return

    target_callback = f"manual_contact:{student_id}:{job_id if job_id is not None else 'null'}"
    today = datetime.now().strftime("%d.%m")

    new_rows: list[list[InlineKeyboardButton]] = []
    for row in msg.reply_markup.inline_keyboard:
        new_row = []
        for btn in row:
            cb = btn.callback_data or ""
            if cb == target_callback:
                if created:
                    new_row.append(
                        InlineKeyboardButton(
                            text=f"✓ {manager_name} написал(а), {today}",
                            callback_data=cb,
                        )
                    )
                else:
                    # Возвращаем исходную кнопку «✓ Написал(а) {ФИО}»
                    # ФИО извлекаем из старого текста, если можем; иначе — generic
                    original = btn.text
                    if original.startswith("✓ "):
                        # это уже плашка-отметка, надо восстановить кнопку
                        # Берём имя студента из ничего — нет в callback'е, оставим generic.
                        new_row.append(
                            InlineKeyboardButton(text="✓ Написал(а)", callback_data=cb)
                        )
                    else:
                        new_row.append(btn)
            else:
                new_row.append(btn)
        new_rows.append(new_row)

    try:
        await msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=new_rows))
    except Exception as exc:  # noqa: BLE001
        logger.info("edit_reply_markup failed: %s", exc)


# --- helpers ------------------------------------------------------------


def _call_consume_manager_invite(token: str, chat_id: int) -> dict:
    with _build_client() as client:
        return client.consume_manager_invite(token=token, chat_id=chat_id)


def _call_register_manual_contact(
    student_id: int, job_id: int | None, manager_telegram_id: int
) -> dict:
    with _build_client() as client:
        return client.register_manual_contact(
            student_id=student_id,
            broadcast_job_id=job_id,
            manager_telegram_id=manager_telegram_id,
        )
