"""Модель компании-партнёра."""

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils import timezone


class HiringStatus(models.TextChoices):
    OPEN = "OPEN", "Принимают"
    CLOSED = "CLOSED", "Не принимают"
    PAUSED = "PAUSED", "Пауза"


class Company(models.Model):
    name = models.CharField("Название", max_length=200, unique=True)
    website = models.URLField("Сайт", blank=True)
    contacts = models.TextField(
        "Контакты",
        blank=True,
        help_text="Свободный текст: имена, телефоны, telegram.",
    )
    description = models.TextField("Описание", blank=True)
    directions = models.ManyToManyField(
        "students.Direction",
        related_name="companies",
        verbose_name="Направления",
        blank=True,
    )
    hiring_status = models.CharField(
        "Статус найма",
        max_length=20,
        choices=HiringStatus.choices,
        default=HiringStatus.OPEN,
    )
    status_changed_at = models.DateTimeField(
        "Дата изменения статуса найма",
        default=timezone.now,
        editable=False,
        help_text="Обновляется только через сервис change_company_status.",
    )
    next_contact_at = models.DateField("Следующий контакт", null=True, blank=True)
    notes = models.TextField("Заметки", blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    comments = GenericRelation(
        "notifications.Comment",
        related_query_name="company",
    )
    attachments = GenericRelation(
        "notifications.Attachment",
        related_query_name="company",
    )

    class Meta:
        verbose_name = "Компания"
        verbose_name_plural = "Компании"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["hiring_status"]),
            models.Index(fields=["next_contact_at"]),
            models.Index(fields=["status_changed_at"]),
        ]

    def __str__(self) -> str:
        return self.name
