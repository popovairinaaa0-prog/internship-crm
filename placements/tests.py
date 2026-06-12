"""Тесты связок student↔company и сервиса смены статуса."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from companies.models import Company
from placements.models import Placement, PlacementStatus
from placements.services import change_placement_status
from students.models import Direction, Student


@pytest.fixture
def trio(db):
    direction = Direction.objects.create(name="Python", slug="python")
    student = Student.objects.create(full_name="Иванов Иван")
    company = Company.objects.create(name="ООО Ромашка")
    return student, company, direction


@pytest.mark.django_db
def test_create_placement(trio):
    student, company, direction = trio
    p = Placement.objects.create(student=student, company=company, direction=direction)
    assert p.pk is not None
    assert p.status == PlacementStatus.SENT_TO_COMPANY
    assert p.sent_at == date.today()
    assert p.status_changed_at is not None  # default=timezone.now сработал
    assert str(p).startswith("Иванов Иван → ООО Ромашка")


@pytest.mark.django_db
def test_change_placement_status_updates_timestamp(trio):
    """change_placement_status явно проставляет status_changed_at."""
    student, company, direction = trio

    p = Placement.objects.create(student=student, company=company, direction=direction)
    # Откатываем status_changed_at в прошлое через .update() (обходит default)
    old = timezone.make_aware(datetime(2026, 6, 1, 12, 0, 0))
    Placement.objects.filter(pk=p.pk).update(status_changed_at=old)
    p.refresh_from_db()
    assert p.status_changed_at == old

    # Патч действует на вызов timezone.now() внутри сервиса
    t1 = timezone.make_aware(datetime(2026, 6, 12, 9, 30, 0))
    with patch("django.utils.timezone.now", return_value=t1):
        change_placement_status(p, PlacementStatus.IN_PROGRESS, user=None)

    p.refresh_from_db()
    assert p.status == PlacementStatus.IN_PROGRESS
    assert p.status_changed_at == t1
    assert p.started_at is not None  # IN_PROGRESS → started_at заполняется


@pytest.mark.django_db
def test_save_without_service_does_not_touch_status_changed_at(trio):
    """Правка comment напрямую через save() НЕ сбрасывает status_changed_at."""
    student, company, direction = trio
    p = Placement.objects.create(student=student, company=company, direction=direction)

    old = timezone.make_aware(datetime(2026, 6, 1, 12, 0, 0))
    Placement.objects.filter(pk=p.pk).update(status_changed_at=old)
    p.refresh_from_db()

    # Через сутки правим только комментарий
    p.comment = "Перезвонила, ждут"
    p.save(update_fields=["comment", "updated_at"])

    p.refresh_from_db()
    assert p.status_changed_at == old


@pytest.mark.django_db
def test_change_placement_status_to_in_progress_with_explicit_dates(trio):
    student, company, direction = trio
    p = Placement.objects.create(student=student, company=company, direction=direction)

    change_placement_status(
        p,
        PlacementStatus.IN_PROGRESS,
        user=None,
        started_at=date(2026, 6, 10),
        planned_duration_days=60,
    )
    p.refresh_from_db()
    assert p.status == PlacementStatus.IN_PROGRESS
    assert p.started_at == date(2026, 6, 10)
    assert p.planned_duration_days == 60


@pytest.mark.django_db
def test_change_placement_status_rejects_unknown_value(trio):
    student, company, direction = trio
    p = Placement.objects.create(student=student, company=company, direction=direction)
    with pytest.raises(ValueError):
        change_placement_status(p, "GARBAGE", user=None)


@pytest.mark.django_db
def test_placement_manager_active_and_stale(trio):
    student, company, direction = trio

    p_old = Placement.objects.create(student=student, company=company, direction=direction)
    p_fresh = Placement.objects.create(student=student, company=company, direction=direction)

    # Сдвигаем p_old на 20 дней назад через .update() (обходит default)
    Placement.objects.filter(pk=p_old.pk).update(
        status_changed_at=timezone.now() - timedelta(days=20)
    )

    active_ids = set(Placement.objects.active().values_list("id", flat=True))
    stale_ids = set(Placement.objects.stale().values_list("id", flat=True))

    assert {p_old.id, p_fresh.id} <= active_ids
    assert p_old.id in stale_ids
    assert p_fresh.id not in stale_ids
