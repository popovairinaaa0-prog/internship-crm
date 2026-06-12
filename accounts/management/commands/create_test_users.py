"""Создаёт тестовых пользователей admin и vip для dev-окружения."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError


TEST_USERS = [
    {
        "username": "admin",
        "email": "admin@local.dev",
        "password": "admin",
        "group": "admins",
        "is_superuser": True,
        "is_staff": True,
    },
    {
        "username": "vip",
        "email": "vip@local.dev",
        "password": "vip",
        "group": "vip_managers",
        "is_superuser": False,
        "is_staff": True,
    },
]


class Command(BaseCommand):
    help = "Создаёт тестовых пользователей admin/admin и vip/vip. Только для DEBUG=True."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Команда работает только при DEBUG=True. "
                "Не запускайте её на проде — она создаёт пользователей с тривиальными паролями."
            )

        User = get_user_model()

        for spec in TEST_USERS:
            group, _ = Group.objects.get_or_create(name=spec["group"])

            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={"email": spec["email"]},
            )
            if created:
                user.set_password(spec["password"])
                self.stdout.write(self.style.SUCCESS(f"Создан: {spec['username']}"))
            else:
                self.stdout.write(f"Уже существует: {spec['username']} — обновляю флаги")

            user.is_superuser = spec["is_superuser"]
            user.is_staff = spec["is_staff"]
            user.email = spec["email"]
            user.save()
            user.groups.add(group)
