"""Связка студент ↔ компания (один эпизод стажировки)."""

from __future__ import annotations

from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class PlacementStatus(models.TextChoices):
    SENT_TO_COMPANY = "SENT_TO_COMPANY", "Передали резюме"
    IN_PROGRESS = "IN_PROGRESS", "Проходит стажировку"
    COMPLETED = "COMPLETED", "Успешно завершил"
    REJECTED_BY_COMPANY = "REJECTED_BY_COMPANY", "Отказ компании"
    REJECTED_BY_STUDENT = "REJECTED_BY_STUDENT", "Отказ студента"


ACTIVE_STATUSES = (PlacementStatus.SENT_TO_COMPANY, PlacementStatus.IN_PROGRESS)


class PlacementQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status__in=ACTIVE_STATUSES)

    def stale(self, days: int | None = None):
        """Активные связки, у которых статус не менялся дольше порога."""
        threshold = days if days is not None else getattr(
            settings, "PLACEMENT_STALE_CRITICAL_DAYS", 14
        )
        cutoff = timezone.now() - timedelta(days=threshold)
        return self.active().filter(status_changed_at__lte=cutoff)

    def overdue_internships(self):
        """IN_PROGRESS, у которых started_at + planned_duration_days < сегодня."""
        today = timezone.localdate()
        qs = self.filter(
            status=PlacementStatus.IN_PROGRESS,
            started_at__isnull=False,
            planned_duration_days__isnull=False,
        )
        # planned end = started_at + planned_duration_days; считаем в Python через annotate невозможно
        # (timedelta из IntegerField), поэтому фильтруем через RawSQL-like выражение:
        return qs.extra(
            where=["started_at + (planned_duration_days || ' days')::interval < %s"],
            params=[today],
        )


class Placement(models.Model):
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="placements",
        verbose_name="Студент",
    )
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.PROTECT,
        related_name="placements",
        verbose_name="Компания",
    )
    direction = models.ForeignKey(
        "students.Direction",
        on_delete=models.PROTECT,
        related_name="placements",
        verbose_name="Направление",
    )
    status = models.CharField(
        "Статус",
        max_length=30,
        choices=PlacementStatus.choices,
        default=PlacementStatus.SENT_TO_COMPANY,
    )
    sent_at = models.DateField("Дата передачи резюме", default=date.today)
    started_at = models.DateField("Дата начала стажировки", null=True, blank=True)
    planned_duration_days = models.PositiveSmallIntegerField(
        "Плановая длительность (дней)",
        null=True,
        blank=True,
        help_text="Если пусто — алерт «превысил срок» не считаем.",
    )
    status_changed_at = models.DateTimeField(
        "Дата изменения статуса",
        default=timezone.now,
        editable=False,
        help_text="Обновляется только через сервис change_placement_status.",
    )
    comment = models.TextField("Комментарий", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_placements",
        verbose_name="Кто создал",
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    objects = PlacementQuerySet.as_manager()

    class Meta:
        verbose_name = "Связка студент ↔ компания"
        verbose_name_plural = "Связки студент ↔ компания"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["status_changed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} → {self.company} ({self.get_status_display()})"
