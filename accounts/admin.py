from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import ManagerInviteToken, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Telegram", {"fields": ("telegram_chat_id",)}),
    )
    list_display = ("username", "first_name", "last_name", "email", "telegram_chat_id", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email")


admin.site.register(ManagerInviteToken)
