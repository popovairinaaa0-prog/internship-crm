"""Админка связок student↔company."""

from __future__ import annotations

from datetime import timedelta

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from unfold.admin import ModelAdmin

from accounts.admin_mixins import VipReadonlyMixin, is_vip

from .models import Placement, PlacementStatus
from .services import change_placement_status


_PLACEMENT_PILL_MAP = {
    PlacementStatus.SENT_TO_COMPANY: "blue",
    PlacementStatus.IN_PROGRESS: "teal",
    PlacementStatus.COMPLETED: "green",
    PlacementStatus.REJECTED_BY_COMPANY: "red",
    PlacementStatus.REJECTED_BY_STUDENT: "gray-border",
}


@admin.register(Placement)
class PlacementAdmin(VipReadonlyMixin, ModelAdmin):
    list_display = (
        "student",
        "company",
        "direction",
        "status",
        "days_since_change",
        "overdue_days",
        "sent_at",
    )
    list_editable = ("status",)
    list_filter = ("status", "direction", "company")
    search_fields = ("student__full_name", "company__name", "comment")
    autocomplete_fields = ("student", "company", "direction")
    readonly_fields = (
        "status_changed_at",
        "days_since_change",
        "overdue_days",
        "created_at",
        "updated_at",
    )
    # Для VIP-менеджера всё кроме `status` становится readonly — VIP может
    # только двигать статус связки, остальное только смотрит.
    _VIP_EXTRA_READONLY = (
        "student",
        "company",
        "direction",
        "sent_at",
        "started_at",
        "planned_duration_days",
        "comment",
        "created_by",
    )
    save_on_top = True
    list_select_related = ("student", "company", "direction")

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        if is_vip(request.user):
            fields = fields + self._VIP_EXTRA_READONLY
        return fields

    class Media:
        css = {"all": ("admin/css/admin_custom.css",)}

    fieldsets = (
        (None, {
            "fields": (
                "student",
                "company",
                "direction",
                "status",
                "sent_at",
                "started_at",
                "planned_duration_days",
                "comment",
                "created_by",
            ),
        }),
        ("Служебное", {
            "fields": (
                "status_changed_at",
                "days_since_change",
                "overdue_days",
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",),
        }),
    )

    # --- колонки списка --------------------------------------------------

    @admin.display(description="Статус")
    def status_pill(self, obj: Placement):
        css = _PLACEMENT_PILL_MAP.get(obj.status, "gray")
        label = obj.get_status_display()
        return format_html('<span class="status-pill status-pill--{}">{}</span>', css, label)

    @admin.display(description="Дней без движения")
    def days_since_change(self, obj: Placement):
        if obj.status_changed_at is None:
            return "—"
        delta = timezone.now() - obj.status_changed_at
        return delta.days

    @admin.display(description="Превышен срок")
    def overdue_days(self, obj: Placement):
        if (
            obj.status != PlacementStatus.IN_PROGRESS
            or obj.started_at is None
            or obj.planned_duration_days is None
        ):
            return "—"
        planned_end = obj.started_at + timedelta(days=obj.planned_duration_days)
        diff = (timezone.localdate() - planned_end).days
        if diff <= 0:
            return "—"
        return format_html(
            '<span class="status-pill status-pill--red">+{} дн.</span>', diff
        )

    # --- save_model: смена статуса только через сервис -------------------

    def save_model(self, request, obj: Placement, form, change):
        if not change:
            # Создание — стандартный путь
            if obj.created_by_id is None:
                obj.created_by = request.user
            super().save_model(request, obj, form, change)
            return

        # Редактирование — проверяем, менялся ли status
        old = Placement.objects.get(pk=obj.pk)
        new_status = form.cleaned_data.get("status", obj.status)

        if old.status != new_status:
            # Сначала сохраняем все остальные изменения, кроме status и status_changed_at
            obj.status = old.status  # вернём, чтобы сервис сам поменял
            super().save_model(request, obj, form, change)
            # Затем вызываем сервис — он корректно проставит status_changed_at
            change_placement_status(
                obj,
                new_status,
                user=request.user,
                started_at=form.cleaned_data.get("started_at"),
                planned_duration_days=form.cleaned_data.get("planned_duration_days"),
            )
        else:
            super().save_model(request, obj, form, change)
