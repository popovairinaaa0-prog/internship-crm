from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from .models import ManagerInviteToken, User
from .services import create_manager_invite_link


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Telegram", {"fields": ("telegram_chat_id",)}),
    )
    list_display = ("username", "first_name", "last_name", "email", "telegram_chat_id", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email")
    actions = ["generate_manager_invite_links"]

    @admin.action(description="Сгенерировать ссылку для служебного бота")
    def generate_manager_invite_links(self, request, queryset):
        ids = list(queryset.values_list("pk", flat=True))
        if not ids:
            self.message_user(
                request, "Не выбрано ни одного пользователя.", level=messages.WARNING
            )
            return None
        url = reverse("admin:accounts_user_invite_links") + "?" + urlencode(
            {"ids": ",".join(map(str, ids))}
        )
        return HttpResponseRedirect(url)

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                "invite-links/",
                self.admin_site.admin_view(self._invite_links_view),
                name="accounts_user_invite_links",
            ),
        ] + urls

    def _invite_links_view(self, request):
        raw_ids = request.GET.get("ids", "")
        pks = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
        users = list(User.objects.filter(pk__in=pks))
        items = [{"user": u, "url": create_manager_invite_link(u)} for u in users]
        return render(
            request,
            "admin/accounts/manager_invite_links.html",
            {"items": items, "title": "Ссылки для служебного бота"},
        )


admin.site.register(ManagerInviteToken)
