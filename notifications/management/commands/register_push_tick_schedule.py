"""Регистрирует периодическую задачу run_push_rules_tick в django-q2.

Запускать один раз после деплоя. Идемпотентно: если запись уже есть,
обновляет интервал согласно settings.PUSH_RULES_TICK_INTERVAL_MINUTES.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django_q.models import Schedule


SCHEDULE_NAME = "push_rules_tick"
FUNC_PATH = "notifications.services.run_push_rules_tick"


class Command(BaseCommand):
    help = "Регистрирует cron-расписание для автопушей в django-q2."

    def handle(self, *args, **options):
        interval_minutes = getattr(settings, "PUSH_RULES_TICK_INTERVAL_MINUTES", 60)

        sched, created = Schedule.objects.update_or_create(
            name=SCHEDULE_NAME,
            defaults={
                "func": FUNC_PATH,
                "schedule_type": Schedule.MINUTES,
                "minutes": int(interval_minutes),
                "repeats": -1,  # бесконечно
            },
        )

        action = "Создано" if created else "Обновлено"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} расписание {sched.name}: каждые {sched.minutes} минут "
                f"→ {sched.func}"
            )
        )
