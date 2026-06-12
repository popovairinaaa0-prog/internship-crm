"""Импорт студентов из CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import IO, Iterable

from django.db import transaction

from common.import_utils import (
    ImportReport,
    clean,
    ensure_directions,
    map_choice,
    normalize_phone,
    normalize_telegram,
    parse_date,
    split_list,
)

from .models import Student, StudentStatus


STATUS_MAP = {
    "обуч": StudentStatus.STUDYING,
    "учит": StudentStatus.STUDYING,
    "ожид": StudentStatus.WAITING,
    "ждёт": StudentStatus.WAITING,
    "ждет": StudentStatus.WAITING,
    "проход": StudentStatus.IN_PROGRESS,
    "стажир": StudentStatus.IN_PROGRESS,
    "прошёл": StudentStatus.COMPLETED,
    "прошел": StudentStatus.COMPLETED,
    "заверш": StudentStatus.COMPLETED,
    "отчисл": StudentStatus.DROPPED,
    "дроп": StudentStatus.DROPPED,
    "брос": StudentStatus.DROPPED,
}


REQUIRED_COLUMNS = ("ФИО",)


def _find_existing(row: dict) -> Student | None:
    """Каскадный dedup: email → phone → telegram_username → full_name."""
    email = clean(row.get("Email")).lower()
    if email and (s := Student.objects.filter(email__iexact=email).first()):
        return s

    phone = normalize_phone(row.get("Телефон"))
    if phone and (s := Student.objects.filter(phone=phone).first()):
        return s

    tg = normalize_telegram(row.get("Telegram"))
    if tg and (s := Student.objects.filter(telegram_username__iexact=tg).first()):
        return s

    name = clean(row.get("ФИО"))
    if name and (s := Student.objects.filter(full_name__iexact=name).first()):
        return s

    return None


def _apply_row_to_student(student: Student, row: dict) -> Student:
    student.full_name = clean(row.get("ФИО"))
    student.telegram_username = normalize_telegram(row.get("Telegram"))
    student.phone = normalize_phone(row.get("Телефон"))
    student.email = clean(row.get("Email"))
    student.status = map_choice(row.get("Статус"), STATUS_MAP, StudentStatus.STUDYING)
    student.guide_url = clean(row.get("Гид"))
    student.marketplace_url = clean(row.get("Маркетплейс"))
    student.next_contact_at = parse_date(row.get("Следующий контакт"))
    student.notes = clean(row.get("Заметки"))
    return student


def import_students(
    source: IO | Path | str,
    *,
    dry_run: bool = False,
    update: bool = False,
    limit: int | None = None,
) -> ImportReport:
    """Импортирует студентов из CSV.

    Args:
        source: открытый файл, путь к файлу или csv-строка.
        dry_run: не пишет в БД, только считает.
        update: обновлять существующие записи (иначе пропускать как дубль).
        limit: ограничение по числу обработанных строк.
    """
    report = ImportReport()
    rows = _iter_rows(source)

    with transaction.atomic():
        sid = transaction.savepoint()
        try:
            for row_num, row in enumerate(rows, start=2):  # 1 — заголовок
                if limit is not None and (report.created + report.updated + report.skipped) >= limit:
                    break

                name = clean(row.get("ФИО"))
                if not name:
                    report.add_error(row_num, "пустое ФИО")
                    continue

                try:
                    existing = _find_existing(row)
                    if existing is not None and not update:
                        report.skipped += 1
                        continue

                    student = existing or Student()
                    _apply_row_to_student(student, row)
                    student.save()

                    direction_names = split_list(row.get("Направления"))
                    if direction_names:
                        directions = ensure_directions(direction_names, report)
                        student.directions.set(directions)

                    if existing is None:
                        report.created += 1
                    else:
                        report.updated += 1
                except Exception as exc:  # noqa: BLE001 — мягкий лог
                    report.add_error(row_num, f"{type(exc).__name__}: {exc}")

            if dry_run:
                transaction.savepoint_rollback(sid)
            else:
                transaction.savepoint_commit(sid)
        except Exception:
            transaction.savepoint_rollback(sid)
            raise

    return report


def _iter_rows(source) -> Iterable[dict]:
    if hasattr(source, "read"):
        reader = csv.DictReader(source)
        yield from reader
        return
    path = Path(source)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)
