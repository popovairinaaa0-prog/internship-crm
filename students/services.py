"""Сервисы для приложения students."""

from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone

from .models import Student, TelegramInviteToken

logger = logging.getLogger(__name__)


def create_invite_link(student: Student) -> str:
    """Создаёт одноразовый invite-токен и возвращает t.me-ссылку."""
    token = TelegramInviteToken.objects.create(student=student)
    bot_username = getattr(settings, "STUDENT_BOT_USERNAME", "") or "your_internship_bot"
    return f"https://t.me/{bot_username}?start={token.token}"


def consume_invite_token(token: str, chat_id: int) -> Student | None:
    """Активирует invite-токен и привязывает chat_id к студенту.

    Возвращает Student при успехе, None — если токен не найден, просрочен,
    уже использован или chat_id уже занят другим студентом.
    """
    try:
        invite = TelegramInviteToken.objects.select_related("student").get(token=token)
    except TelegramInviteToken.DoesNotExist:
        logger.info("consume_invite: token %s not found", token[:8])
        return None

    if not invite.is_valid():
        logger.info("consume_invite: token %s invalid (used or expired)", token[:8])
        return None

    # chat_id может быть уже занят другим студентом — отдельно проверяем
    other = Student.objects.filter(telegram_chat_id=chat_id).exclude(pk=invite.student_id).first()
    if other is not None:
        logger.info(
            "consume_invite: chat_id %s already bound to student %s", chat_id, other.pk
        )
        return None

    student = invite.student
    student.telegram_chat_id = chat_id
    student.save(update_fields=["telegram_chat_id", "updated_at"])

    invite.used_at = timezone.now()
    invite.save(update_fields=["used_at"])

    logger.info("consume_invite: student %s bound to chat_id %s", student.pk, chat_id)
    return student
