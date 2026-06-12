"""Тесты ManualContact (служебный бот, этап 8)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from notifications.models import (
    BroadcastDelivery,
    BroadcastJob,
    BroadcastStatus,
    DeliveryStatus,
    ManualContact,
)
from notifications.services import (
    create_broadcast_job,
    notify_managers_about_unreachable,
    register_manual_contact,
    run_broadcast_worker,
)
from students.models import Direction, Student


# --- register_manual_contact (toggle) --------------------------------


@pytest.fixture
def manager(db):
    User = get_user_model()
    return User.objects.create_user(
        username="manager_a",
        password="x",
        first_name="Анна",
        last_name="Менеджер",
        telegram_chat_id=42,
    )


@pytest.fixture
def unbound_manager(db):
    User = get_user_model()
    return User.objects.create_user(username="unbound", password="x")


@pytest.fixture
def job_with_student(db, manager):
    student = Student.objects.create(full_name="Иванов Иван")
    job = create_broadcast_job(
        created_by=manager, message_text="hi", recipient_ids=[student.pk]
    )
    return job, student


@pytest.mark.django_db
def test_register_manual_contact_creates_then_toggles(manager, job_with_student):
    job, student = job_with_student

    created, contact = register_manual_contact(
        student_id=student.pk,
        broadcast_job_id=job.pk,
        manager_telegram_id=manager.telegram_chat_id,
    )
    assert created is True
    assert contact.manager == manager
    assert ManualContact.objects.count() == 1

    # Повторный вызов — toggle, удаляет
    created2, contact2 = register_manual_contact(
        student_id=student.pk,
        broadcast_job_id=job.pk,
        manager_telegram_id=manager.telegram_chat_id,
    )
    assert created2 is False
    assert ManualContact.objects.count() == 0


@pytest.mark.django_db
def test_register_manual_contact_unbound_manager_returns_none(job_with_student):
    job, student = job_with_student

    created, contact = register_manual_contact(
        student_id=student.pk,
        broadcast_job_id=job.pk,
        manager_telegram_id=99999,  # никем не привязан
    )
    assert created is False
    assert contact is None
    assert ManualContact.objects.count() == 0


# --- notify_managers_about_unreachable -------------------------------


@pytest.mark.django_db
def test_notify_managers_skips_when_no_unreachable(manager, job_with_student, settings):
    settings.MANAGERS_CHAT_ID = "100"
    settings.MANAGERS_BOT_TOKEN = "fake"
    job, _ = job_with_student
    sent_calls = []
    n = notify_managers_about_unreachable(
        job, _send=lambda *a, **kw: sent_calls.append((a, kw)) or {}
    )
    assert n == 0
    assert sent_calls == []


@pytest.mark.django_db
def test_notify_managers_sends_with_keyboard(manager, settings):
    settings.MANAGERS_CHAT_ID = "100"
    settings.MANAGERS_BOT_TOKEN = "fake"

    direction = Direction.objects.create(name="Python", slug="python")
    s1 = Student.objects.create(full_name="Иванов Иван", telegram_username="ivanov")
    s1.directions.add(direction)
    s2 = Student.objects.create(full_name="Соколова Дарья", phone="+79161234567")

    job = create_broadcast_job(
        created_by=manager,
        message_text="hi",
        recipient_ids=[s1.pk, s2.pk],
    )
    BroadcastDelivery.objects.create(job=job, student=s1, status=DeliveryStatus.NO_CHAT_ID)
    BroadcastDelivery.objects.create(job=job, student=s2, status=DeliveryStatus.NO_CHAT_ID)

    captured = {}

    def fake_send(chat_id, text, token, *, inline_buttons=None):
        captured["chat_id"] = chat_id
        captured["text"] = text
        captured["token"] = token
        captured["buttons"] = inline_buttons
        return {"status": DeliveryStatus.SENT}

    n = notify_managers_about_unreachable(job, _send=fake_send)

    assert n == 2
    assert captured["chat_id"] == 100
    assert captured["token"] == "fake"
    assert "Иванов Иван" in captured["text"]
    assert "Соколова Дарья" in captured["text"]
    # Кнопки — две, по одной на строку
    assert len(captured["buttons"]) == 2
    assert all(len(row) == 1 for row in captured["buttons"])
    cb_data = [row[0]["callback_data"] for row in captured["buttons"]]
    assert f"manual_contact:{s1.pk}:{job.pk}" in cb_data
    assert f"manual_contact:{s2.pk}:{job.pk}" in cb_data


@pytest.mark.django_db
def test_notify_managers_skips_when_settings_empty(manager, job_with_student, settings):
    settings.MANAGERS_CHAT_ID = ""
    settings.MANAGERS_BOT_TOKEN = ""
    job, student = job_with_student
    BroadcastDelivery.objects.create(
        job=job, student=student, status=DeliveryStatus.NO_CHAT_ID
    )

    sent_calls = []
    n = notify_managers_about_unreachable(
        job, _send=lambda *a, **kw: sent_calls.append((a, kw))
    )
    assert n == 0
    assert sent_calls == []


# --- worker → notify integration -------------------------------------


@pytest.mark.django_db
def test_worker_calls_notify_after_done(manager, settings):
    settings.STUDENT_BOT_TOKEN = "fake"
    settings.MANAGERS_CHAT_ID = "100"
    settings.MANAGERS_BOT_TOKEN = "fake"

    s = Student.objects.create(full_name="Без чата")  # без chat_id
    job = create_broadcast_job(
        created_by=manager, message_text="hi", recipient_ids=[s.pk]
    )

    with patch("notifications.services.notify_managers_about_unreachable") as mock_notify:
        run_broadcast_worker(job.pk, _send=lambda *a, **kw: None, _sleep=lambda s: None)

    job.refresh_from_db()
    assert job.status == BroadcastStatus.DONE
    mock_notify.assert_called_once()
    args, _ = mock_notify.call_args
    assert args[0].pk == job.pk


# --- API endpoint /api/manual-contacts/ -------------------------------


@pytest.fixture
def api_url():
    return reverse("notifications_api:register_manual_contact")


@pytest.mark.django_db
def test_api_manual_contact_requires_token(client, api_url, manager, settings):
    settings.BOT_API_TOKEN = "secret"
    s = Student.objects.create(full_name="X")
    resp = client.post(
        api_url,
        data={
            "student_id": s.pk,
            "broadcast_job_id": None,
            "manager_telegram_id": manager.telegram_chat_id,
        },
        content_type="application/json",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_api_manual_contact_creates(client, api_url, manager, settings):
    settings.BOT_API_TOKEN = "secret"
    s = Student.objects.create(full_name="X")

    resp = client.post(
        api_url,
        data={
            "student_id": s.pk,
            "broadcast_job_id": None,
            "manager_telegram_id": manager.telegram_chat_id,
        },
        content_type="application/json",
        HTTP_X_BOT_TOKEN="secret",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["created"] is True
    assert body["manager_name"] == "Анна Менеджер"


@pytest.mark.django_db
def test_api_manual_contact_not_bound(client, api_url, settings):
    settings.BOT_API_TOKEN = "secret"
    s = Student.objects.create(full_name="X")

    resp = client.post(
        api_url,
        data={
            "student_id": s.pk,
            "broadcast_job_id": None,
            "manager_telegram_id": 99999,
        },
        content_type="application/json",
        HTTP_X_BOT_TOKEN="secret",
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": False, "error": "not_bound"}


@pytest.mark.django_db
def test_api_manual_contact_toggle(client, api_url, manager, settings):
    settings.BOT_API_TOKEN = "secret"
    s = Student.objects.create(full_name="X")

    payload = {
        "student_id": s.pk,
        "broadcast_job_id": None,
        "manager_telegram_id": manager.telegram_chat_id,
    }
    headers = {"HTTP_X_BOT_TOKEN": "secret"}

    # Первый клик — создание
    resp1 = client.post(api_url, data=payload, content_type="application/json", **headers)
    assert resp1.json()["created"] is True

    # Второй клик — удаление
    resp2 = client.post(api_url, data=payload, content_type="application/json", **headers)
    assert resp2.json()["created"] is False

    assert ManualContact.objects.count() == 0
