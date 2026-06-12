"""Тесты импорта студентов."""

from __future__ import annotations

import io
from datetime import date

import pytest

from students.imports import import_students
from students.models import Direction, Student, StudentStatus


HEADER = "ФИО,Telegram,Телефон,Email,Направления,Статус,Гид,Маркетплейс,Следующий контакт,Заметки\n"


def _csv(rows: list[str]) -> io.StringIO:
    return io.StringIO(HEADER + "\n".join(rows) + "\n")


@pytest.mark.django_db
def test_basic_import_creates_students():
    src = _csv(
        [
            "Иванов Иван,@ivan,+7 916 000 11 22,ivan@example.com,Python,обучается,,,15.06.2026,",
            "Петрова Анна,anna_p,, ,QA,ожидает,,,,",
        ]
    )
    report = import_students(src)
    assert report.created == 2
    assert report.updated == 0
    assert report.skipped == 0
    assert Student.objects.count() == 2

    ivan = Student.objects.get(email="ivan@example.com")
    assert ivan.telegram_username == "ivan"  # @ убрана
    assert ivan.phone == "+79160001122"  # пробелы убраны
    assert ivan.status == StudentStatus.STUDYING
    assert ivan.next_contact_at == date(2026, 6, 15)
    assert list(ivan.directions.values_list("name", flat=True)) == ["Python"]


@pytest.mark.django_db
def test_empty_name_logged_as_error():
    src = _csv([",,,no.name@example.com,,,,,,"])
    report = import_students(src)
    assert report.created == 0
    assert len(report.errors) == 1
    assert "ФИО" in report.errors[0][1]


@pytest.mark.django_db
def test_idempotent_by_email():
    src1 = _csv(["Иванов,@ivan,,ivan@example.com,Python,обучается,,,,"])
    import_students(src1)
    assert Student.objects.count() == 1

    # Повторный прогон того же файла без --update — должен пропустить
    src2 = _csv(["Иванов,@ivan,,ivan@example.com,Python,обучается,,,,"])
    report = import_students(src2)
    assert report.created == 0
    assert report.skipped == 1
    assert Student.objects.count() == 1


@pytest.mark.django_db
def test_update_flag_overwrites_existing():
    Student.objects.create(full_name="Иванов", email="ivan@example.com")

    src = _csv(["Иванов Иван,@ivan,,ivan@example.com,QA,стажируется,,,,"])
    report = import_students(src, update=True)
    assert report.updated == 1
    assert report.created == 0

    s = Student.objects.get(email="ivan@example.com")
    assert s.full_name == "Иванов Иван"
    assert s.status == StudentStatus.IN_PROGRESS
    assert list(s.directions.values_list("name", flat=True)) == ["QA"]


@pytest.mark.django_db
def test_dry_run_does_not_persist():
    src = _csv(["Тестов,,,,Python,обучается,,,,"])
    report = import_students(src, dry_run=True)
    assert report.created == 1  # счётчики идут, но БД не меняется
    assert Student.objects.count() == 0
    assert Direction.objects.count() == 0


@pytest.mark.django_db
def test_limit_stops_processing():
    src = _csv(
        [
            "А,,,a@a.com,Python,обучается,,,,",
            "Б,,,b@a.com,QA,обучается,,,,",
            "В,,,c@a.com,Frontend,обучается,,,,",
        ]
    )
    report = import_students(src, limit=2)
    assert report.created == 2
    assert Student.objects.count() == 2


@pytest.mark.django_db
def test_dedup_cascade_falls_back_to_phone_then_telegram():
    # Существующий студент с phone
    existing = Student.objects.create(full_name="Старый", phone="+79991234567")

    src = _csv(["Новый,,+7 999 123 45 67,,Python,обучается,,,,"])
    report = import_students(src, update=True)
    assert report.updated == 1
    existing.refresh_from_db()
    assert existing.full_name == "Новый"


@pytest.mark.django_db
def test_directions_created_on_the_fly():
    src = _csv(["Иванов,,,ivanov@example.com,\"Python, QA, Что-то новое\",обучается,,,,"])
    report = import_students(src)
    assert report.created == 1
    assert report.created_directions == 3
    s = Student.objects.get(email="ivanov@example.com")
    assert set(s.directions.values_list("name", flat=True)) == {"Python", "QA", "Что-то новое"}
