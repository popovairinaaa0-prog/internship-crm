"""Админка студентов и направлений."""

from __future__ import annotations

from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.contenttypes.admin import GenericTabularInline
from django.db.models import Count, F, ProtectedError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from notifications.models import Comment
from placements.models import Placement

from .models import Direction, Student, StudentStatus, TelegramInviteToken


# --- Кастомный фильтр по дате контакта ----------------------------------


class ContactDueFilter(admin.SimpleListFilter):
    title = "Контакт"
    parameter_name = "contact_due"

    def lookups(self, request, model_admin):
        return (
            ("overdue", "Просрочен"),
            ("today", "Сегодня"),
            ("soon", "Скоро"),
            ("none", "Без даты"),
        )

    def queryset(self, request, queryset):
        today = timezone.localdate()
        match self.value():
            case "overdue":
                return queryset.filter(next_contact_at__lt=today)
            case "today":
                return queryset.filter(next_contact_at=today)
            case "soon":
                return queryset.filter(next_contact_at__gt=today)
            case "none":
                return queryset.filter(next_contact_at__isnull=True)
            case _:
                return queryset


# --- Inlines ------------------------------------------------------------


class PlacementForStudentInline(admin.TabularInline):
    model = Placement
    fk_name = "student"
    extra = 0
    fields = ("company", "direction", "status", "sent_at", "started_at", "comment")
    autocomplete_fields = ("company", "direction")
    show_change_link = True
    verbose_name = "Связка"
    verbose_name_plural = "История стажировок"


class CommentInline(GenericTabularInline):
    model = Comment
    extra = 0
    fields = ("author", "text", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("author",)
    verbose_name = "Комментарий"
    verbose_name_plural = "Комментарии"


# --- Хелперы плашек -----------------------------------------------------

_STUDENT_PILL_MAP = {
    StudentStatus.STUDYING: "purple",
    StudentStatus.WAITING: "amber",
    StudentStatus.IN_PROGRESS: "teal",
    StudentStatus.COMPLETED: "gray",
    StudentStatus.DROPPED: "gray-light",
}


def _student_status_pill(status: str) -> str:
    css = _STUDENT_PILL_MAP.get(status, "gray")
    label = dict(StudentStatus.choices).get(status, status)
    return format_html('<span class="status-pill status-pill--{}">{}</span>', css, label)


# --- StudentAdmin -------------------------------------------------------


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "telegram_indicator",
        "directions_list",
        "status_pill",
        "next_contact_display",
    )
    list_filter = ("status", "directions", ContactDueFilter)
    search_fields = ("full_name", "telegram_username", "email", "phone")
    list_per_page = 20
    list_select_related = False
    filter_horizontal = ("directions",)
    inlines = [PlacementForStudentInline, CommentInline]
    actions = ["send_broadcast_to_selected"]
    save_on_top = True

    class Media:
        css = {"all": ("admin/css/admin_custom.css",)}

    # --- queryset с сортировкой по дате контакта NULLS LAST ---------------

    def get_queryset(self, request):
        qs = super().get_queryset(request).prefetch_related("directions")
        # По умолчанию: сначала самые срочные контакты, пустые — в конец
        if not request.GET.get("o"):
            qs = qs.order_by(F("next_contact_at").asc(nulls_last=True), "full_name")
        return qs

    # --- колонки списка --------------------------------------------------

    @admin.display(description="Telegram")
    def telegram_indicator(self, obj: Student):
        if obj.telegram_chat_id:
            return format_html(
                '<span class="tg-yes">✓ @{}</span>',
                obj.telegram_username or "—",
            )
        if obj.telegram_username:
            return format_html('<span class="tg-no">@{}</span>', obj.telegram_username)
        return mark_safe('<span class="tg-no">—</span>')

    @admin.display(description="Направления")
    def directions_list(self, obj: Student):
        names = [d.name for d in obj.directions.all()]
        return ", ".join(names) if names else "—"

    @admin.display(description="Статус")
    def status_pill(self, obj: Student):
        return _student_status_pill(obj.status)

    @admin.display(description="Контакт", ordering="next_contact_at")
    def next_contact_display(self, obj: Student):
        today = timezone.localdate()
        if obj.next_contact_at is None:
            return mark_safe('<span class="contact-date--none">—</span>')
        if obj.next_contact_at < today:
            css = "overdue"
        elif obj.next_contact_at == today:
            css = "today"
        else:
            css = "soon"
        return format_html(
            '<span class="contact-date--{}">{}</span>',
            css,
            obj.next_contact_at.strftime("%d.%m.%Y"),
        )

    # --- секции в changelist (Просрочено / Сегодня / Скоро / Без даты) ---

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        # Показываем секции только при сортировке по next_contact_at и без явного o=
        if not request.GET.get("o"):
            today = timezone.localdate()
            counts_qs = self.get_queryset(request)
            extra_context["section_counts"] = {
                "overdue": counts_qs.filter(next_contact_at__lt=today).count(),
                "today": counts_qs.filter(next_contact_at=today).count(),
                "soon": counts_qs.filter(next_contact_at__gt=today).count(),
                "none": counts_qs.filter(next_contact_at__isnull=True).count(),
            }
            extra_context["show_contact_sections"] = True
        return super().changelist_view(request, extra_context=extra_context)

    # --- action: отправить рассылку выбранным ---------------------------

    @admin.action(description="Отправить рассылку выбранным")
    def send_broadcast_to_selected(self, request, queryset):
        ids = list(queryset.values_list("pk", flat=True))
        if not ids:
            self.message_user(
                request, "Не выбрано ни одного студента.", level=messages.WARNING
            )
            return None
        url = reverse("notifications:broadcast_new") + "?" + urlencode(
            {"ids": ",".join(map(str, ids))}
        )
        return HttpResponseRedirect(url)


# --- DirectionAdmin -----------------------------------------------------


@admin.action(description="Скрыть выбранные")
def hide_directions(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f"Скрыто направлений: {updated}.")


@admin.action(description="Показать выбранные")
def show_directions(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f"Показано направлений: {updated}.")


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "students_count", "companies_count")
    list_editable = ("is_active",)
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    actions = [hide_directions, show_directions]

    class Media:
        css = {"all": ("admin/css/admin_custom.css",)}

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _students_count=Count("students", distinct=True),
                _companies_count=Count("companies", distinct=True),
            )
        )

    @admin.display(description="Студентов", ordering="_students_count")
    def students_count(self, obj):
        return obj._students_count

    @admin.display(description="Компаний", ordering="_companies_count")
    def companies_count(self, obj):
        return obj._companies_count

    def delete_model(self, request, obj):
        try:
            super().delete_model(request, obj)
        except ProtectedError:
            self.message_user(
                request,
                f"Нельзя удалить «{obj.name}» — на это направление ссылаются "
                "студенты, компании или связки. Скройте направление вместо удаления.",
                level=messages.ERROR,
            )

    def delete_queryset(self, request, queryset):
        try:
            super().delete_queryset(request, queryset)
        except ProtectedError:
            self.message_user(
                request,
                "Часть направлений нельзя удалить — на них ссылаются объекты. "
                "Используйте действие «Скрыть».",
                level=messages.ERROR,
            )


admin.site.register(TelegramInviteToken)
