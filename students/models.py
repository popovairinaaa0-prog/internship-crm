"""Модели студентов: справочник направлений, карточка студента, инвайт-токены."""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils import timezone


class Direction(models.Model):
    """Справочник направлений обучения (Python, QA, ...)."""

    name = models.CharField("Название", max_length=100, unique=True)
    slug = models.SlugField("Слаг", unique=True)
    is_active = models.BooleanField("Активно", default=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Направление"
        verbose_name_plural = "Направления"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class StudentStatus(models.TextChoices):
    STUDYING = "STUDYING", "Обучается"
    WAITING = "WAITING", "Ожидает стажировку"
    IN_PROGRESS = "IN_PROGRESS", "Проходит стажировку"
    COMPLETED = "COMPLETED", "Прошёл стажировку"
    DROPPED = "DROPPED", "Отчислен"


class Student(models.Model):
    """Карточка студента."""

    full_name = models.CharField("ФИО", max_length=200)
    telegram_username = models.CharField("Telegram username", max_length=64, blank=True)
    telegram_chat_id = models.BigIntegerField(
        "Telegram chat ID",
        null=True,
        blank=True,
        unique=True,
        help_text="Заполняется ботом после /start с инвайт-токеном.",
    )
    phone = models.CharField("Телефон", max_length=32, blank=True)
    email = models.EmailField("Email", blank=True)
    directions = models.ManyToManyField(
        Direction,
        related_name="students",
        verbose_name="Направления",
        blank=True,
    )
    guide_url = models.URLField("Ссылка на гид / курс", blank=True)
    marketplace_url = models.URLField("Ссылка на маркетплейс", blank=True)
    extra_links = models.JSONField("Дополнительные ссылки", default=list, blank=True)
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=StudentStatus.choices,
        default=StudentStatus.STUDYING,
    )
    next_contact_at = models.DateField("Следующий контакт", null=True, blank=True)
    notes = models.TextField("Заметки", blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    comments = GenericRelation(
        "notifications.Comment",
        related_query_name="student",
    )
    attachments = GenericRelation(
        "notifications.Attachment",
        related_query_name="student",
    )

    class Meta:
        verbose_name = "Студент"
        verbose_name_plural = "Студенты"
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["next_contact_at"]),
            models.Index(fields=["telegram_chat_id"]),
        ]

    def __str__(self) -> str:
        return self.full_name


def _default_invite_token() -> str:
    return secrets.token_urlsafe(30)


def _default_invite_expires_at():
    return timezone.now() + timedelta(days=30)


class TelegramInviteToken(models.Model):
    """Одноразовый токен для привязки chat_id к студенту."""

    token = models.CharField("Токен", max_length=40, unique=True, default=_default_invite_token)
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="invite_tokens",
        verbose_name="Студент",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    used_at = models.DateTimeField("Использован", null=True, blank=True)
    expires_at = models.DateTimeField("Истекает", default=_default_invite_expires_at)

    class Meta:
        verbose_name = "Инвайт-токен студента"
        verbose_name_plural = "Инвайт-токены студентов"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.token[:8]}… → {self.student}"

    def is_valid(self) -> bool:
        return self.used_at is None and timezone.now() < self.expires_at
