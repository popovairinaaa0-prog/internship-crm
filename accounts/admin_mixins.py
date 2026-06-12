"""Помощники для админок: единая проверка роли VIP-менеджера."""

from __future__ import annotations


VIP_GROUP_NAME = "vip_managers"
ADMINS_GROUP_NAME = "admins"


def is_vip(user) -> bool:
    """True, если пользователь — VIP-менеджер (и НЕ суперюзер)."""
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return False
    return user.groups.filter(name=VIP_GROUP_NAME).exists()


class VipReadonlyMixin:
    """Запрещает удаление для пользователей из группы vip_managers.

    Применяется в ModelAdmin'ах, где VIP должен видеть данные, но не имеет
    права удалять. Изменение полей не блокируем здесь — Django сам поставит
    форму в read-only режим, если у пользователя нет change-права.
    """

    def has_delete_permission(self, request, obj=None):
        if is_vip(request.user):
            return False
        return super().has_delete_permission(request, obj)
