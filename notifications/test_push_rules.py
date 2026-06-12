"""Тесты автопушей менеджерам."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from companies.models import Company, HiringStatus
from companies.services import change_company_status
from notifications.models import (
    DeliveryStatus,
    MessageAudience,
    MessageTemplate,
    PushRule,
    PushSent,
    TriggerType,
)
from notifications.services import render_template, run_push_rules_tick
from placements.models import Placement, PlacementStatus
from students.models import Direction, Student


# --- render_template ---------------------------------------------------


@pytest.mark.django_db
def test_render_template_substitutes_keys():
    tmpl = MessageTemplate.objects.create(
        code="t1",
        name="t1",
        audience=MessageAudience.MANAGER,
        text="По {student_name} в {company_name} нет решения {days} дн.",
    )
    out = render_template(tmpl, {"student_name": "Иван", "company_name": "Ромашка", "days": 20})
    assert out == "По Иван в Ромашка нет решения 20 дн."


@pytest.mark.django_db
def test_render_template_safedict_keeps_unknown_keys():
    tmpl = MessageTemplate.objects.create(
        code="t2",
        name="t2",
        audience=MessageAudience.MANAGER,
        text="{a} {missing}",
    )
    assert render_template(tmpl, {"a": "ok"}) == "ok {missing}"


# --- Company.status_changed_at ---------------------------------------


@pytest.mark.django_db
def test_change_company_status_updates_timestamp():
    c = Company.objects.create(name="X", hiring_status=HiringStatus.OPEN)
    old_ts = c.status_changed_at
    # Сдвинем status_changed_at в прошлое для контраста
    Company.objects.filter(pk=c.pk).update(
        status_changed_at=timezone.now() - timedelta(days=10)
    )
    c.refresh_from_db()

    change_company_status(c, HiringStatus.PAUSED)
    c.refresh_from_db()

    assert c.hiring_status == HiringStatus.PAUSED
    assert c.status_changed_at > old_ts - timedelta(seconds=1)


@pytest.mark.django_db
def test_change_company_status_rejects_unknown():
    c = Company.objects.create(name="X")
    with pytest.raises(ValueError):
        change_company_status(c, "GARBAGE")


# --- run_push_rules_tick --------------------------------------------


@pytest.fixture
def settings_managers(settings):
    settings.MANAGERS_CHAT_ID = "100"
    settings.MANAGERS_BOT_TOKEN = "fake"
    return settings


@pytest.fixture
def trio(db):
    direction = Direction.objects.create(name="Python", slug="python")
    student = Student.objects.create(full_name="Иванов Иван")
    company = Company.objects.create(name="ООО Ромашка")
    return student, company, direction


def _stub_sender(captured: list):
    def _send(chat_id, text, token, *, inline_buttons=None):
        captured.append({"chat_id": chat_id, "text": text, "token": token})
        return {"status": DeliveryStatus.SENT}
    return _send


@pytest.mark.django_db
def test_tick_skips_when_settings_empty(settings, trio):
    settings.MANAGERS_CHAT_ID = ""
    settings.MANAGERS_BOT_TOKEN = ""

    captured: list = []
    summary = run_push_rules_tick(_send=_stub_sender(captured))
    assert captured == []
    assert summary == {"checked": 0, "sent": 0, "skipped": 0, "errors": 0}


@pytest.mark.django_db
def test_tick_placement_stale_sends_once(settings_managers, trio):
    student, company, direction = trio
    p = Placement.objects.create(student=student, company=company, direction=direction)
    Placement.objects.filter(pk=p.pk).update(
        status_changed_at=timezone.now() - timedelta(days=20)
    )

    captured: list = []
    summary = run_push_rules_tick(_send=_stub_sender(captured))

    assert summary["sent"] >= 1
    assert any("Иванов Иван" in c["text"] for c in captured)
    assert PushSent.objects.filter(placement=p).count() == 1

    # Повторный прогон — не должно создаться дубликата
    captured2: list = []
    run_push_rules_tick(_send=_stub_sender(captured2))
    assert PushSent.objects.filter(placement=p).count() == 1


@pytest.mark.django_db
def test_tick_placement_overdue_sends(settings_managers, trio):
    student, company, direction = trio
    p = Placement.objects.create(
        student=student,
        company=company,
        direction=direction,
        status=PlacementStatus.IN_PROGRESS,
        started_at=date.today() - timedelta(days=70),
        planned_duration_days=30,
    )

    captured: list = []
    summary = run_push_rules_tick(_send=_stub_sender(captured))

    overdue_sent = PushSent.objects.filter(placement=p).count()
    assert overdue_sent >= 1
    assert any("превысила" in c["text"] for c in captured)


@pytest.mark.django_db
def test_tick_company_paused_sends_after_threshold(settings_managers):
    c = Company.objects.create(name="ООО Заря", hiring_status=HiringStatus.PAUSED)
    Company.objects.filter(pk=c.pk).update(
        status_changed_at=timezone.now() - timedelta(days=45)
    )

    captured: list = []
    summary = run_push_rules_tick(_send=_stub_sender(captured))

    assert any("ООО Заря" in c["text"] and "паузе" in c["text"] for c in captured)
    assert PushSent.objects.filter(company=c).count() == 1


@pytest.mark.django_db
def test_tick_recurring_rule_resends_after_interval(settings_managers, trio):
    student, company, direction = trio

    # Делаем правило по PLACEMENT_STATUS_STALE recurring
    rule = PushRule.objects.get(name="Зависшие резюме")
    rule.recurring_every_days = 7
    rule.save()

    p = Placement.objects.create(student=student, company=company, direction=direction)
    Placement.objects.filter(pk=p.pk).update(
        status_changed_at=timezone.now() - timedelta(days=20)
    )

    captured: list = []
    run_push_rules_tick(_send=_stub_sender(captured))
    assert PushSent.objects.filter(rule=rule, placement=p).count() == 1

    # Сразу повторно — должен пропустить (только что отправили)
    run_push_rules_tick(_send=_stub_sender(captured))
    assert PushSent.objects.filter(rule=rule, placement=p).count() == 1

    # Сдвигаем sent_at старого PushSent на 10 дней назад — должен отправить второй раз
    PushSent.objects.filter(rule=rule).update(
        sent_at=timezone.now() - timedelta(days=10)
    )
    run_push_rules_tick(_send=_stub_sender(captured))
    assert PushSent.objects.filter(rule=rule, placement=p).count() == 2


@pytest.mark.django_db
def test_tick_skips_inactive_rules(settings_managers, trio):
    student, company, direction = trio
    p = Placement.objects.create(student=student, company=company, direction=direction)
    Placement.objects.filter(pk=p.pk).update(
        status_changed_at=timezone.now() - timedelta(days=20)
    )

    PushRule.objects.update(is_active=False)

    captured: list = []
    summary = run_push_rules_tick(_send=_stub_sender(captured))

    assert summary["sent"] == 0
    assert PushSent.objects.count() == 0
