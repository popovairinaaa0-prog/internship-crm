"""Уведомления: комментарии, файлы, рассылки, ручные отметки, автопуши."""

from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


# --- Полиморфные комментарии и файлы ---------------------------------------


class Comment(models.Model):
    """Комментарий, привязанный к произвольной модели (Student или Company)."""

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="Тип объекта",
    )
    object_id = models.PositiveBigIntegerField("ID объекта")
    target = GenericForeignKey("content_type", "object_id")

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="comments",
        verbose_name="Автор",
    )
    text = models.TextField("Текст")
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Comment #{self.pk} by {self.author_id}"


class Attachment(models.Model):
    """Файл, привязанный к произвольной модели."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    file = models.FileField("Файл", upload_to="attachments/%Y/%m/")
    original_name = models.CharField("Имя файла", max_length=255)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_attachments",
        verbose_name="Загрузил",
    )
    created_at = models.DateTimeField("Загружен", auto_now_add=True)

    class Meta:
        verbose_name = "Файл"
        verbose_name_plural = "Файлы"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self) -> str:
        return self.original_name


# --- Рассылки --------------------------------------------------------------


class BroadcastStatus(models.TextChoices):
    PENDING = "PENDING", "Ожидает"
    RUNNING = "RUNNING", "Отправляется"
    DONE = "DONE", "Завершена"
    FAILED = "FAILED", "Ошибка"


class BroadcastJob(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="broadcast_jobs",
        verbose_name="Создал",
    )
    message_text = models.TextField("Текст сообщения")
    recipients = models.ManyToManyField(
        "students.Student",
        related_name="broadcast_jobs",
        verbose_name="Получатели",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=BroadcastStatus.choices,
        default=BroadcastStatus.PENDING,
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    started_at = models.DateTimeField("Начало", null=True, blank=True)
    finished_at = models.DateTimeField("Завершение", null=True, blank=True)

    class Meta:
        verbose_name = "Рассылка"
        verbose_name_plural = "Рассылки"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Рассылка #{self.pk} ({self.get_status_display()})"


class DeliveryStatus(models.TextChoices):
    PENDING = "PENDING", "Ожидает"
    SENT = "SENT", "Отправлено"
    BLOCKED = "BLOCKED", "Заблокировал бота"
    NO_CHAT_ID = "NO_CHAT_ID", "Не подписан на бота"
    FAILED = "FAILED", "Ошибка"


class BroadcastDelivery(models.Model):
    job = models.ForeignKey(
        BroadcastJob,
        on_delete=models.CASCADE,
        related_name="deliveries",
        verbose_name="Рассылка",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="broadcast_deliveries",
        verbose_name="Студент",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
    )
    error_text = models.TextField("Ошибка", blank=True)
    sent_at = models.DateTimeField("Отправлено", null=True, blank=True)

    class Meta:
        verbose_name = "Доставка"
        verbose_name_plural = "Доставки"
        indexes = [
            models.Index(fields=["job", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} ({self.get_status_display()})"


class ManualContact(models.Model):
    """Отметка «менеджер написал студенту вручную»."""

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="manual_contacts",
        verbose_name="Студент",
    )
    broadcast_job = models.ForeignKey(
        BroadcastJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manual_contacts",
        verbose_name="Контекст рассылки",
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="manual_contacts",
        verbose_name="Менеджер",
    )
    contacted_at = models.DateTimeField("Дата контакта", auto_now_add=True)
    note = models.TextField("Заметка", blank=True)

    class Meta:
        verbose_name = "Ручной контакт"
        verbose_name_plural = "Ручные контакты"
        ordering = ["-contacted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "broadcast_job", "manager"],
                name="uniq_manual_contact",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.manager} → {self.student} @ {self.contacted_at:%Y-%m-%d}"


# --- Шаблоны сообщений и правила автопушей ---------------------------------


class MessageAudience(models.TextChoices):
    MANAGER = "MANAGER", "Менеджер"
    STUDENT = "STUDENT", "Студент"


class MessageTemplate(models.Model):
    code = models.SlugField("Код", unique=True, max_length=100)
    name = models.CharField("Название", max_length=200)
    audience = models.CharField(
        "Аудитория",
        max_length=20,
        choices=MessageAudience.choices,
    )
    text = models.TextField(
        "Текст",
        help_text="Поддерживает подстановки {student_name}, {company_name}, {days}, {direction}.",
    )
    inline_buttons = models.JSONField(
        "Inline-кнопки",
        default=list,
        blank=True,
        help_text="Список вида [{\"label\": \"Всё ок\", \"callback\": \"survey_ok\"}].",
    )
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Шаблон сообщения"
        verbose_name_plural = "Шаблоны сообщений"
        ordering = ["audience", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_audience_display()})"


class TriggerType(models.TextChoices):
    PLACEMENT_STATUS_STALE = "PLACEMENT_STATUS_STALE", "Связка зависла в статусе"
    PLACEMENT_DURATION_EXCEEDED = "PLACEMENT_DURATION_EXCEEDED", "Превышен срок стажировки"
    COMPANY_PAUSED_STALE = "COMPANY_PAUSED_STALE", "Компания долго на паузе"
    STUDENT_STATUS_PERIODIC = "STUDENT_STATUS_PERIODIC", "Периодический опросник студента"


class PushRule(models.Model):
    name = models.CharField("Название", max_length=200)
    trigger_type = models.CharField(
        "Тип триггера",
        max_length=30,
        choices=TriggerType.choices,
    )
    target_status = models.CharField(
        "Целевой статус",
        max_length=30,
        blank=True,
        help_text="Зависит от типа триггера. Может быть пустым.",
    )
    days_threshold = models.PositiveSmallIntegerField(
        "Порог (дней)",
        help_text="Через сколько дней с момента события срабатывает правило.",
    )
    recurring_every_days = models.PositiveSmallIntegerField(
        "Повторять каждые N дней",
        null=True,
        blank=True,
        help_text="Если пусто — правило одноразовое для объекта.",
    )
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.PROTECT,
        related_name="push_rules",
        verbose_name="Шаблон",
    )
    is_active = models.BooleanField("Активно", default=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Правило автопуша"
        verbose_name_plural = "Правила автопушей"
        ordering = ["trigger_type", "name"]

    def __str__(self) -> str:
        return self.name


class PushSent(models.Model):
    """Лог отправленных автопушей — чтобы не отправлять дважды."""

    rule = models.ForeignKey(
        PushRule,
        on_delete=models.CASCADE,
        related_name="sent_pushes",
        verbose_name="Правило",
    )
    placement = models.ForeignKey(
        "placements.Placement",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="push_sent",
        verbose_name="Связка",
    )
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="push_sent",
        verbose_name="Компания",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="push_sent",
        verbose_name="Студент",
    )
    sent_at = models.DateTimeField("Отправлено", auto_now_add=True)
    recipient_chat_id = models.BigIntegerField("Куда уходило")
    response_callback = models.CharField("Ответ (callback)", max_length=50, blank=True)
    response_at = models.DateTimeField("Время ответа", null=True, blank=True)

    class Meta:
        verbose_name = "Отправленный автопуш"
        verbose_name_plural = "Отправленные автопуши"
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["sent_at"]),
            models.Index(fields=["rule", "sent_at"]),
            models.Index(fields=["rule", "placement"]),
            models.Index(fields=["rule", "company"]),
            models.Index(fields=["rule", "student"]),
        ]
        # Уникальность для одноразовых правил проверяется в run_push_rules_tick
        # (Django не разрешает UniqueConstraint с условием по joined-полю FK).

    def __str__(self) -> str:
        return f"PushSent #{self.pk} ({self.rule_id})"
