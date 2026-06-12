"""Админка уведомлений: шаблоны, правила автопушей, рассылки, лог."""

from __future__ import annotations

from django.contrib import admin

from unfold.admin import ModelAdmin

from accounts.admin_mixins import VipReadonlyMixin, is_vip

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
class MessageTemplateAdmin(VipReadonlyMixin, ModelAdmin):
    list_display = ("name", "code", "audience", "is_active", "updated_at")
    list_filter = ("audience", "is_active")
    search_fields = ("name", "code", "text")
    list_editable = ("is_active",)
    readonly_fields = ("created_at", "updated_at")

    class Media:
        css = {"all": ("admin/css/admin_custom.css",)}


@admin.register(PushRule)
class PushRuleAdmin(VipReadonlyMixin, ModelAdmin):
    list_display = (
        "name",
        "audience_display",
        "description_for_admin",
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

    @admin.display(description="Когда срабатывает")
    def description_for_admin(self, obj: PushRule):
        trigger_label = obj.get_trigger_type_display()
        parts = [trigger_label]
        if obj.target_status:
            parts.append(f"target: «{obj.target_status}»")
        parts.append(f"≥ {obj.days_threshold} дн")
        if obj.recurring_every_days:
            parts.append(f"повтор каждые {obj.recurring_every_days} дн")
        else:
            parts.append("одноразово")
        shape = " · ".join(parts)
        tmpl_code = obj.template.code if obj.template_id else "—"
        return f"{shape} → шаблон «{tmpl_code}»"

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
class BroadcastJobAdmin(VipReadonlyMixin, ModelAdmin):
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
class BroadcastDeliveryAdmin(VipReadonlyMixin, ModelAdmin):
    list_display = ("job", "student", "status", "sent_at")
    list_filter = ("status",)
    search_fields = ("student__full_name",)
    readonly_fields = ("job", "student", "status", "error_text", "sent_at")

    def has_add_permission(self, request):
        return False


@admin.register(ManualContact)
class ManualContactAdmin(VipReadonlyMixin, ModelAdmin):
    list_display = ("student", "manager", "broadcast_job", "contacted_at")
    list_filter = ("manager",)
    search_fields = ("student__full_name", "note")
    autocomplete_fields = ("student", "manager", "broadcast_job")


@admin.register(Comment)
class CommentAdmin(VipReadonlyMixin, ModelAdmin):
    list_display = ("id", "content_type", "object_id", "author", "created_at")
    list_filter = ("content_type",)
    search_fields = ("text",)
    autocomplete_fields = ("author",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if is_vip(request.user):
            qs = qs.filter(author=request.user)
        return qs

    def has_change_permission(self, request, obj=None):
        ok = super().has_change_permission(request, obj)
        if not ok:
            return False
        if obj is not None and is_vip(request.user) and obj.author_id != request.user.id:
            return False
        return True

    def save_model(self, request, obj, form, change):
        # При создании через админку проставляем автором текущего пользователя,
        # если он не указан явно. Это упрощает VIP-сценарий: их комментарии
        # автоматически становятся «своими».
        if not change and obj.author_id is None:
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(Attachment)
class AttachmentAdmin(VipReadonlyMixin, ModelAdmin):
    list_display = ("original_name", "content_type", "object_id", "uploaded_by", "created_at")
    list_filter = ("content_type",)
    search_fields = ("original_name",)
    autocomplete_fields = ("uploaded_by",)


@admin.register(PushSent)
class PushSentAdmin(VipReadonlyMixin, ModelAdmin):
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
