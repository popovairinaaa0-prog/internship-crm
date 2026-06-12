"""Кастомный User + инвайт-токен для привязки менеджера к служебному боту."""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    telegram_chat_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        verbose_name="Telegram chat ID",
        help_text="Заполняется автоматически при привязке через служебный бот.",
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self) -> str:
        return self.get_full_name() or self.username


def _default_manager_invite_token() -> str:
    return "mgr_" + secrets.token_urlsafe(24)


def _default_manager_invite_expires_at():
    return timezone.now() + timedelta(days=30)


class ManagerInviteToken(models.Model):
    """Одноразовый токен для привязки telegram_chat_id к менеджеру."""

    token = models.CharField(
        "Токен",
        max_length=40,
        unique=True,
        default=_default_manager_invite_token,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="manager_invite_tokens",
        verbose_name="Пользователь",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    used_at = models.DateTimeField("Использован", null=True, blank=True)
    expires_at = models.DateTimeField("Истекает", default=_default_manager_invite_expires_at)

    class Meta:
        verbose_name = "Инвайт-токен менеджера"
        verbose_name_plural = "Инвайт-токены менеджеров"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.token[:12]}… → {self.user}"

    def is_valid(self) -> bool:
        return self.used_at is None and timezone.now() < self.expires_at
