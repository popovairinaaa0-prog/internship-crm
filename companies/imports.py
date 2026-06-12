"""Импорт компаний из CSV."""

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
    parse_date,
    split_list,
)

from .models import Company, HiringStatus


HIRING_STATUS_MAP = {
    "приним": HiringStatus.OPEN,
    "open": HiringStatus.OPEN,
    "да": HiringStatus.OPEN,
    "пауза": HiringStatus.PAUSED,
    "пауз": HiringStatus.PAUSED,
    "ждать": HiringStatus.PAUSED,
    "не приним": HiringStatus.CLOSED,
    "закры": HiringStatus.CLOSED,
    "нет": HiringStatus.CLOSED,
}


def _apply_row_to_company(company: Company, row: dict) -> Company:
    company.name = clean(row.get("Название"))
    company.website = clean(row.get("Сайт"))
    company.contacts = clean(row.get("Контакты"))
    company.hiring_status = map_choice(
        row.get("Статус найма"), HIRING_STATUS_MAP, HiringStatus.OPEN
    )
    company.next_contact_at = parse_date(row.get("Следующий контакт"))
    company.notes = clean(row.get("Заметки"))
    return company


def import_companies(
    source: IO | Path | str,
    *,
    dry_run: bool = False,
    update: bool = False,
    limit: int | None = None,
) -> ImportReport:
    """Импортирует компании из CSV. Дедупликация по name (уникален в БД)."""
    report = ImportReport()
    rows = _iter_rows(source)

    with transaction.atomic():
        sid = transaction.savepoint()
        try:
            for row_num, row in enumerate(rows, start=2):
                if limit is not None and (report.created + report.updated + report.skipped) >= limit:
                    break

                name = clean(row.get("Название"))
                if not name:
                    report.add_error(row_num, "пустое название")
                    continue

                try:
                    existing = Company.objects.filter(name__iexact=name).first()
                    if existing is not None and not update:
                        report.skipped += 1
                        continue

                    company = existing or Company()
                    _apply_row_to_company(company, row)
                    company.save()

                    direction_names = split_list(row.get("Направления"))
                    if direction_names:
                        directions = ensure_directions(direction_names, report)
                        company.directions.set(directions)

                    if existing is None:
                        report.created += 1
                    else:
                        report.updated += 1
                except Exception as exc:  # noqa: BLE001
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
