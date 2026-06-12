"""Импорт студентов из CSV."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from students.imports import import_students


class Command(BaseCommand):
    help = "Импортирует студентов из CSV. Идемпотентный."

    def add_arguments(self, parser):
        parser.add_argument("csv", type=Path, help="Путь к CSV-файлу.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Не записывать изменения в БД, только показать сводку.",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Обновлять существующие записи (по умолчанию — пропускать как дубль).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Ограничение по числу обработанных строк.",
        )

    def handle(self, *args, **options):
        path: Path = options["csv"]
        if not path.exists():
            raise CommandError(f"Файл не найден: {path}")

        report = import_students(
            path,
            dry_run=options["dry_run"],
            update=options["update"],
            limit=options["limit"],
        )
        self.stdout.write(report.format(dry_run=options["dry_run"]))
