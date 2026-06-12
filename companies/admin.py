"""Админка компаний."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from accounts.admin_mixins import VipReadonlyMixin
from notifications.models import Comment
from placements.models import ACTIVE_STATUSES, Placement, PlacementStatus

from .models import Company, HiringStatus


_HIRING_PILL_MAP = {
    HiringStatus.OPEN: "green",
    HiringStatus.PAUSED: "amber",
    HiringStatus.CLOSED: "gray",
}


class HasStalePlacementsFilter(admin.SimpleListFilter):
    title = "Зависшие связки"
    parameter_name = "has_stale"

    def lookups(self, request, model_admin):
        return (("yes", "Есть зависшие"), ("no", "Без зависших"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(_stale_count__gt=0)
        if self.value() == "no":
            return queryset.filter(_stale_count=0)
        return queryset


class PlacementForCompanyInline(admin.TabularInline):
    model = Placement
    fk_name = "company"
    extra = 0
    fields = ("student", "direction", "status", "sent_at", "started_at", "comment")
    autocomplete_fields = ("student", "direction")
    show_change_link = True
    verbose_name = "Связка"
    verbose_name_plural = "Отправленные студенты"


class CommentInline(GenericTabularInline):
    model = Comment
    extra = 0
    fields = ("author", "text", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("author",)
    verbose_name = "Комментарий"
    verbose_name_plural = "Комментарии"


@admin.register(Company)
class CompanyAdmin(VipReadonlyMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "directions_list",
        "hiring_pill",
        "active_count",
        "stale_count_display",
        "next_contact_at",
    )
    list_filter = ("hiring_status", "directions", HasStalePlacementsFilter)
    search_fields = ("name", "contacts")
    filter_horizontal = ("directions",)
    inlines = [PlacementForCompanyInline, CommentInline]
    save_on_top = True

    class Media:
        css = {"all": ("admin/css/admin_custom.css",)}

    def get_queryset(self, request):
        qs = super().get_queryset(request).prefetch_related("directions")
        threshold_days = getattr(settings, "PLACEMENT_STALE_CRITICAL_DAYS", 14)
        cutoff = timezone.now() - timedelta(days=threshold_days)
        qs = qs.annotate(
            _active_count=Count(
                "placements",
                filter=Q(placements__status__in=ACTIVE_STATUSES),
                distinct=True,
            ),
            _stale_count=Count(
                "placements",
                filter=Q(
                    placements__status=PlacementStatus.SENT_TO_COMPANY,
                    placements__status_changed_at__lte=cutoff,
                ),
                distinct=True,
            ),
        )
        if not request.GET.get("o"):
            qs = qs.order_by("-_stale_count", "name")
        return qs

    @admin.display(description="Направления")
    def directions_list(self, obj):
        names = [d.name for d in obj.directions.all()]
        return ", ".join(names) if names else "—"

    @admin.display(description="Статус найма")
    def hiring_pill(self, obj):
        css = _HIRING_PILL_MAP.get(obj.hiring_status, "gray")
        label = dict(HiringStatus.choices).get(obj.hiring_status, obj.hiring_status)
        return format_html('<span class="status-pill status-pill--{}">{}</span>', css, label)

    @admin.display(description="Активных", ordering="_active_count")
    def active_count(self, obj):
        return obj._active_count

    @admin.display(description="Зависших", ordering="_stale_count")
    def stale_count_display(self, obj):
        if obj._stale_count == 0:
            return "—"
        return format_html(
            '<span class="status-pill status-pill--red">{}</span>', obj._stale_count
        )
