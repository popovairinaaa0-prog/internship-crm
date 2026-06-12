"""Общие хелперы для импорта данных из CSV."""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable


def clean(value: str | None) -> str:
    """Стрипает пробелы и неразрывные пробелы. None → пустая строка."""
    if value is None:
        return ""
    return str(value).replace("\xa0", " ").strip()


def normalize_telegram(value: str | None) -> str:
    """Убирает @ и пробелы из telegram username."""
    v = clean(value).lstrip("@")
    return v


def normalize_phone(value: str | None) -> str:
    """Оставляет цифры и плюс. Пустое → пустая строка."""
    raw = clean(value)
    if not raw:
        return ""
    allowed = "+0123456789"
    return "".join(ch for ch in raw if ch in allowed)


_DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")


def parse_date(value: str | None) -> date | None:
    raw = clean(value)
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def split_list(value: str | None) -> list[str]:
    """Делит строку через запятую/точку с запятой, удаляет пустое."""
    raw = clean(value)
    if not raw:
        return []
    parts = []
    for separator in (";", ","):
        if separator in raw:
            parts = [p.strip() for p in raw.split(separator)]
            break
    if not parts:
        parts = [raw]
    return [p for p in (clean(x) for x in parts) if p]


def map_choice(value: str | None, mapping: dict[str, str], default: str) -> str:
    """Маппит свободный русский ввод в значение TextChoices.

    Сопоставление по нижнему регистру и фрагменту: если в `value` встречается
    любой ключ из mapping — возвращаем соответствующее значение. Иначе default.
    """
    raw = clean(value).lower()
    if not raw:
        return default
    for key, mapped in mapping.items():
        if key in raw:
            return mapped
    return default


class ImportReport:
    """Сводка результатов импорта."""

    def __init__(self):
        self.created = 0
        self.updated = 0
        self.skipped = 0
        self.errors: list[tuple[int, str]] = []
        self.created_directions = 0

    def add_error(self, row_num: int, message: str):
        self.errors.append((row_num, message))

    def format(self, dry_run: bool = False) -> str:
        prefix = "[DRY RUN] " if dry_run else ""
        lines = [
            f"{prefix}Создано: {self.created}",
            f"{prefix}Обновлено: {self.updated}",
            f"{prefix}Пропущено дублей: {self.skipped}",
            f"{prefix}Новых направлений: {self.created_directions}",
            f"{prefix}Ошибок: {len(self.errors)}",
        ]
        if self.errors:
            lines.append("Ошибки:")
            for row, msg in self.errors[:20]:
                lines.append(f"  строка {row}: {msg}")
            if len(self.errors) > 20:
                lines.append(f"  … и ещё {len(self.errors) - 20}")
        return "\n".join(lines)


def ensure_directions(names: Iterable[str], report: ImportReport):
    """Получает или создаёт Direction по именам. Возвращает список объектов."""
    from django.utils.text import slugify

    from students.models import Direction

    directions = []
    for name in names:
        name = clean(name)
        if not name:
            continue
        obj, created = Direction.objects.get_or_create(
            name=name,
            defaults={"slug": slugify(name, allow_unicode=False) or name.lower()},
        )
        if created:
            report.created_directions += 1
        directions.append(obj)
    return directions
