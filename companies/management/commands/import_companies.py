"""Импорт компаний из CSV."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from companies.imports import import_companies


class Command(BaseCommand):
    help = "Импортирует компании из CSV. Идемпотентный."

    def add_arguments(self, parser):
        parser.add_argument("csv", type=Path, help="Путь к CSV-файлу.")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--update", action="store_true")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        path: Path = options["csv"]
        if not path.exists():
            raise CommandError(f"Файл не найден: {path}")

        report = import_companies(
            path,
            dry_run=options["dry_run"],
            update=options["update"],
            limit=options["limit"],
        )
        self.stdout.write(report.format(dry_run=options["dry_run"]))
