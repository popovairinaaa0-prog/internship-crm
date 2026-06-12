"""Админка уведомлений: шаблоны, правила автопушей, рассылки, лог."""

from __future__ import annotations

from django.contrib import admin

from .models import (
    Attachment,
    BroadcastDelivery,
    BroadcastJob,
    Comment,
    ManualContact,
    MessageAudience,
    MessageTemplate,
    PushRule,
    PushSent,
)


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "audience", "is_active", "updated_at")
    list_filter = ("audience", "is_active")
    search_fields = ("name", "code", "text")
    list_editable = ("is_active",)
    readonly_fields = ("created_at", "updated_at")

    class Media:
        css = {"all": ("admin/css/admin_custom.css",)}


@admin.register(PushRule)
class PushRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "audience_display",
        "trigger_type",
        "target_status",
        "days_threshold",
        "recurring_every_days",
        "template",
        "is_active",
    )
    list_filter = ("trigger_type", "is_active", "template__audience")
    search_fields = ("name", "template__name")
    list_editable = ("is_active",)
    autocomplete_fields = ("template",)
    list_select_related = ("template",)
    change_list_template = "admin/notifications/pushrule/change_list.html"

    class Media:
        css = {"all": ("admin/css/admin_custom.css",)}

    @admin.display(description="Аудитория", ordering="template__audience")
    def audience_display(self, obj: PushRule):
        return obj.template.get_audience_display() if obj.template_id else "—"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        qs = self.get_queryset(request)
        extra_context["audience_counts"] = {
            MessageAudience.MANAGER.label: qs.filter(
                template__audience=MessageAudience.MANAGER
            ).count(),
            MessageAudience.STUDENT.label: qs.filter(
                template__audience=MessageAudience.STUDENT
            ).count(),
        }
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(BroadcastJob)
class BroadcastJobAdmin(admin.ModelAdmin):
    """Рассылки создаются через свой view (этап 7). Здесь — только просмотр."""

    list_display = (
        "id",
        "created_by",
        "status",
        "recipients_count",
        "created_at",
        "started_at",
        "finished_at",
    )
    list_filter = ("status",)
    search_fields = ("message_text",)
    readonly_fields = (
        "created_by",
        "message_text",
        "status",
        "created_at",
        "started_at",
        "finished_at",
    )
    filter_horizontal = ("recipients",)

    def has_add_permission(self, request):
        return False

    @admin.display(description="Получателей")
    def recipients_count(self, obj):
        return obj.recipients.count()


@admin.register(BroadcastDelivery)
class BroadcastDeliveryAdmin(admin.ModelAdmin):
    list_display = ("job", "student", "status", "sent_at")
    list_filter = ("status",)
    search_fields = ("student__full_name",)
    readonly_fields = ("job", "student", "status", "error_text", "sent_at")

    def has_add_permission(self, request):
        return False


@admin.register(ManualContact)
class ManualContactAdmin(admin.ModelAdmin):
    list_display = ("student", "manager", "broadcast_job", "contacted_at")
    list_filter = ("manager",)
    search_fields = ("student__full_name", "note")
    autocomplete_fields = ("student", "manager", "broadcast_job")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "content_type", "object_id", "author", "created_at")
    list_filter = ("content_type",)
    search_fields = ("text",)
    autocomplete_fields = ("author",)


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "content_type", "object_id", "uploaded_by", "created_at")
    list_filter = ("content_type",)
    search_fields = ("original_name",)
    autocomplete_fields = ("uploaded_by",)


@admin.register(PushSent)
class PushSentAdmin(admin.ModelAdmin):
    list_display = ("rule", "sent_at", "recipient_chat_id", "response_callback")
    list_filter = ("rule",)
    readonly_fields = (
        "rule",
        "placement",
        "company",
        "student",
        "sent_at",
        "recipient_chat_id",
        "response_callback",
        "response_at",
    )

    def has_add_permission(self, request):
        return False
