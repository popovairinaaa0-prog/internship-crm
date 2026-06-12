"""Тесты сервисов рассылок и формы."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from notifications.models import (
    BroadcastDelivery,
    BroadcastJob,
    BroadcastStatus,
    DeliveryStatus,
)
from notifications.services import (
    create_broadcast_job,
    render_message,
    run_broadcast_worker,
    send_telegram_message,
)
from students.models import Student


# --- render_message -----------------------------------------------------


@pytest.mark.django_db
def test_render_message_substitutes_first_name():
    s = Student.objects.create(full_name="Иванов Иван Сергеевич")
    assert render_message("Привет, {имя}!", s) == "Привет, Иванов!"


@pytest.mark.django_db
def test_render_message_safedict_keeps_unknown_keys():
    s = Student.objects.create(full_name="Иванов Иван")
    out = render_message("Hi {имя}, ты {не_указан}", s)
    assert out == "Hi Иванов, ты {не_указан}"


# --- send_telegram_message ---------------------------------------------


def _mock_response(status_code: int, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


def test_send_message_200_returns_sent():
    client = MagicMock()
    client.post.return_value = _mock_response(200)
    out = send_telegram_message(42, "hi", "fake", _client=client)
    assert out == {"status": DeliveryStatus.SENT}


def test_send_message_403_returns_blocked():
    client = MagicMock()
    client.post.return_value = _mock_response(403, "blocked")
    out = send_telegram_message(42, "hi", "fake", _client=client)
    assert out["status"] == DeliveryStatus.BLOCKED


def test_send_message_429_retries_then_fails():
    client = MagicMock()
    client.post.return_value = _mock_response(429, "too many")
    sleeps: list[float] = []
    out = send_telegram_message(42, "hi", "fake", _client=client, _sleep=sleeps.append)
    # 1 первая попытка + 3 retry = 4 запроса, между ними 3 сна (1, 2, 4)
    assert client.post.call_count == 4
    assert sleeps == [1, 2, 4]
    assert out["status"] == DeliveryStatus.FAILED


def test_send_message_429_then_success():
    client = MagicMock()
    client.post.side_effect = [_mock_response(429), _mock_response(200)]
    out = send_telegram_message(42, "hi", "fake", _client=client, _sleep=lambda s: None)
    assert out == {"status": DeliveryStatus.SENT}


def test_send_message_network_error_returns_failed():
    client = MagicMock()
    client.post.side_effect = httpx.RequestError("DNS")
    out = send_telegram_message(42, "hi", "fake", _client=client)
    assert out["status"] == DeliveryStatus.FAILED
    assert "network" in out["error"]


# --- run_broadcast_worker ---------------------------------------------


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(username="sender", password="x")


def _make_job(user, students, text="Привет, {имя}!"):
    return create_broadcast_job(
        created_by=user, message_text=text, recipient_ids=[s.pk for s in students]
    )


@pytest.mark.django_db
def test_worker_with_real_chat_id_sends_message(user, settings):
    settings.STUDENT_BOT_TOKEN = "fake-token"
    s = Student.objects.create(full_name="Иванов Иван", telegram_chat_id=42)
    job = _make_job(user, [s])

    sent_calls = []

    def fake_send(chat_id, text, token):
        sent_calls.append((chat_id, text, token))
        return {"status": DeliveryStatus.SENT}

    run_broadcast_worker(job.pk, _send=fake_send, _sleep=lambda s: None)

    job.refresh_from_db()
    assert job.status == BroadcastStatus.DONE
    assert job.finished_at is not None

    delivery = BroadcastDelivery.objects.get(job=job, student=s)
    assert delivery.status == DeliveryStatus.SENT
    assert delivery.sent_at is not None

    assert sent_calls == [(42, "Привет, Иванов!", "fake-token")]


@pytest.mark.django_db
def test_worker_without_chat_id_marks_no_chat_id(user, settings):
    settings.STUDENT_BOT_TOKEN = "fake"
    s = Student.objects.create(full_name="Соколова Дарья")  # без chat_id
    job = _make_job(user, [s])

    fake_send = MagicMock()
    run_broadcast_worker(job.pk, _send=fake_send, _sleep=lambda s: None)

    delivery = BroadcastDelivery.objects.get(job=job, student=s)
    assert delivery.status == DeliveryStatus.NO_CHAT_ID
    fake_send.assert_not_called()


@pytest.mark.django_db
def test_worker_handles_blocked_student(user, settings):
    settings.STUDENT_BOT_TOKEN = "fake"
    s = Student.objects.create(full_name="Иванов Иван", telegram_chat_id=42)
    job = _make_job(user, [s])

    fake_send = lambda *a, **kw: {"status": DeliveryStatus.BLOCKED, "error": "bot blocked"}
    run_broadcast_worker(job.pk, _send=fake_send, _sleep=lambda s: None)

    delivery = BroadcastDelivery.objects.get(job=job, student=s)
    assert delivery.status == DeliveryStatus.BLOCKED
    assert "bot blocked" in delivery.error_text


@pytest.mark.django_db
def test_worker_idempotent_on_rerun(user, settings):
    settings.STUDENT_BOT_TOKEN = "fake"
    s = Student.objects.create(full_name="Иванов Иван", telegram_chat_id=42)
    job = _make_job(user, [s])

    fake_send = lambda *a, **kw: {"status": DeliveryStatus.SENT}
    run_broadcast_worker(job.pk, _send=fake_send, _sleep=lambda s: None)

    # Повторный вызов — job уже DONE, повторно не идём
    fake_send2 = MagicMock()
    run_broadcast_worker(job.pk, _send=fake_send2, _sleep=lambda s: None)
    fake_send2.assert_not_called()
    assert BroadcastDelivery.objects.filter(job=job).count() == 1


# --- View: форма рассылки ---------------------------------------------


@pytest.fixture
def admin_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="admin_test", password="x", is_staff=True, is_superuser=True
    )


@pytest.mark.django_db
def test_broadcast_new_get_with_ids_shows_recipients(client, admin_user):
    s1 = Student.objects.create(full_name="Иванов Иван", telegram_chat_id=42)
    s2 = Student.objects.create(full_name="Петров Пётр")  # без chat_id

    client.force_login(admin_user)
    url = reverse("notifications:broadcast_new") + f"?ids={s1.pk},{s2.pk}"
    resp = client.get(url)

    assert resp.status_code == 200
    assert "Иванов".encode("utf-8") in resp.content
    assert "Петров".encode("utf-8") in resp.content


@pytest.mark.django_db
def test_broadcast_new_post_send_creates_job_and_enqueues(client, admin_user):
    s = Student.objects.create(full_name="Иванов Иван", telegram_chat_id=42)

    client.force_login(admin_user)
    with patch("notifications.views.enqueue_broadcast") as mock_enq:
        resp = client.post(
            reverse("notifications:broadcast_new"),
            data={
                "action": "send",
                "message_text": "Привет, {имя}!",
                "recipient_ids": str(s.pk),
            },
        )

    assert resp.status_code == 302
    job = BroadcastJob.objects.get()
    assert job.message_text == "Привет, {имя}!"
    assert job.created_by == admin_user
    assert list(job.recipients.all()) == [s]
    mock_enq.assert_called_once_with(job)


@pytest.mark.django_db
def test_broadcast_new_post_draft_does_not_enqueue(client, admin_user):
    s = Student.objects.create(full_name="Иванов Иван", telegram_chat_id=42)

    client.force_login(admin_user)
    with patch("notifications.views.enqueue_broadcast") as mock_enq:
        resp = client.post(
            reverse("notifications:broadcast_new"),
            data={
                "action": "draft",
                "message_text": "черновик",
                "recipient_ids": str(s.pk),
            },
        )

    assert resp.status_code == 302
    assert BroadcastJob.objects.count() == 1
    mock_enq.assert_not_called()


@pytest.mark.django_db
def test_broadcast_new_post_requires_text(client, admin_user):
    s = Student.objects.create(full_name="Иванов")

    client.force_login(admin_user)
    resp = client.post(
        reverse("notifications:broadcast_new"),
        data={"action": "send", "message_text": "  ", "recipient_ids": str(s.pk)},
    )
    # редирект назад с error-сообщением, без создания job
    assert resp.status_code == 302
    assert BroadcastJob.objects.count() == 0


@pytest.mark.django_db
def test_broadcast_status_json(client, admin_user):
    s = Student.objects.create(full_name="Иванов", telegram_chat_id=42)
    job = create_broadcast_job(
        created_by=admin_user, message_text="hi", recipient_ids=[s.pk]
    )

    client.force_login(admin_user)
    resp = client.get(reverse("notifications:broadcast_status", args=[job.pk]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == BroadcastStatus.PENDING
    assert body["stats"]["total"] == 0  # deliveries создаются только в worker
    assert body["is_finished"] is False


# --- Autocomplete -----------------------------------------------------


@pytest.mark.django_db
def test_autocomplete_filters_by_query(client, admin_user):
    Student.objects.create(full_name="Иванов Иван", telegram_username="ivan")
    Student.objects.create(full_name="Петров Пётр", telegram_username="petr")

    client.force_login(admin_user)
    resp = client.get(reverse("students_api:autocomplete") + "?q=иван")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["label"] == "Иванов Иван"


@pytest.mark.django_db
def test_autocomplete_requires_staff(client):
    User = get_user_model()
    regular = User.objects.create_user(username="reg", password="x")
    client.force_login(regular)
    resp = client.get(reverse("students_api:autocomplete") + "?q=x")
    # staff_member_required редиректит на admin login
    assert resp.status_code in (302, 403)
