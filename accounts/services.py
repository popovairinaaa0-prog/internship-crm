"""Сервисы для accounts: онбординг менеджеров."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import ManagerInviteToken

logger = logging.getLogger(__name__)


def create_manager_invite_link(user) -> str:
    """Создаёт одноразовый invite-токен для менеджера и возвращает t.me-ссылку."""
    token = ManagerInviteToken.objects.create(user=user)
    bot_username = getattr(settings, "MANAGERS_BOT_USERNAME", "") or "your_managers_bot"
    return f"https://t.me/{bot_username}?start={token.token}"


def consume_manager_invite_token(token: str, chat_id: int):
    """Активирует invite-токен и привязывает chat_id к User.

    Возвращает User или None при невалидном/просроченном/уже использованном
    токене, либо если chat_id занят другим менеджером.
    """
    try:
        invite = ManagerInviteToken.objects.select_related("user").get(token=token)
    except ManagerInviteToken.DoesNotExist:
        logger.info("consume_manager_invite: token not found")
        return None

    if not invite.is_valid():
        logger.info("consume_manager_invite: token invalid")
        return None

    User = get_user_model()
    other = User.objects.filter(telegram_chat_id=chat_id).exclude(pk=invite.user_id).first()
    if other is not None:
        logger.info(
            "consume_manager_invite: chat_id %s already bound to user %s",
            chat_id,
            other.pk,
        )
        return None

    user = invite.user
    user.telegram_chat_id = chat_id
    user.save(update_fields=["telegram_chat_id"])

    invite.used_at = timezone.now()
    invite.save(update_fields=["used_at"])

    logger.info("consume_manager_invite: user %s bound to chat_id %s", user.pk, chat_id)
    return user
