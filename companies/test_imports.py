"""Тесты импорта компаний."""

from __future__ import annotations

import io
from datetime import date

import pytest

from companies.imports import import_companies
from companies.models import Company, HiringStatus


HEADER = "Название,Сайт,Контакты,Направления,Статус найма,Следующий контакт,Заметки\n"


def _csv(rows):
    return io.StringIO(HEADER + "\n".join(rows) + "\n")


@pytest.mark.django_db
def test_basic_import_creates_companies():
    src = _csv(
        [
            'ООО Ромашка,https://romashka.example,"Иван, +7 916","Python, QA",принимают,15.06.2026,',
            "ТехноСофт,,,Frontend,пауза,,",
        ]
    )
    report = import_companies(src)
    assert report.created == 2

    r = Company.objects.get(name="ООО Ромашка")
    assert r.hiring_status == HiringStatus.OPEN
    assert r.next_contact_at == date(2026, 6, 15)
    assert set(r.directions.values_list("name", flat=True)) == {"Python", "QA"}

    t = Company.objects.get(name="ТехноСофт")
    assert t.hiring_status == HiringStatus.PAUSED


@pytest.mark.django_db
def test_idempotent_by_name():
    src1 = _csv(["ООО Ромашка,,,,принимают,,"])
    import_companies(src1)
    assert Company.objects.count() == 1

    src2 = _csv(["ООО Ромашка,,,,не принимают,,"])
    report = import_companies(src2)
    assert report.skipped == 1
    assert Company.objects.get(name="ООО Ромашка").hiring_status == HiringStatus.OPEN


@pytest.mark.django_db
def test_update_flag():
    Company.objects.create(name="ООО Ромашка", hiring_status=HiringStatus.OPEN)
    src = _csv(["ООО Ромашка,,,,пауза,,новая заметка"])
    report = import_companies(src, update=True)
    assert report.updated == 1
    c = Company.objects.get(name="ООО Ромашка")
    assert c.hiring_status == HiringStatus.PAUSED
    assert c.notes == "новая заметка"


@pytest.mark.django_db
def test_empty_name_logged_as_error():
    src = _csv([",https://x.example,,,принимают,,"])
    report = import_companies(src)
    assert report.created == 0
    assert len(report.errors) == 1


@pytest.mark.django_db
def test_dry_run_does_not_persist():
    src = _csv(["DryCompany,,,Python,принимают,,"])
    report = import_companies(src, dry_run=True)
    assert report.created == 1
    assert Company.objects.count() == 0
