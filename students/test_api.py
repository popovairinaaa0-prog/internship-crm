"""Тесты API-эндпоинта consume-invite."""

from __future__ import annotations

import pytest
from django.urls import reverse

from students.models import Student, TelegramInviteToken


@pytest.fixture
def api_url():
    return reverse("students_api:consume_invite")


@pytest.mark.django_db
def test_requires_bot_token(client, api_url, settings):
    settings.BOT_API_TOKEN = "secret"
    student = Student.objects.create(full_name="Иванов Иван")
    invite = TelegramInviteToken.objects.create(student=student)

    resp = client.post(
        api_url,
        data={"token": invite.token, "chat_id": 42},
        content_type="application/json",
    )
    assert resp.status_code == 401
    student.refresh_from_db()
    assert student.telegram_chat_id is None


@pytest.mark.django_db
def test_wrong_bot_token_rejected(client, api_url, settings):
    settings.BOT_API_TOKEN = "secret"
    student = Student.objects.create(full_name="Иванов Иван")
    invite = TelegramInviteToken.objects.create(student=student)

    resp = client.post(
        api_url,
        data={"token": invite.token, "chat_id": 42},
        content_type="application/json",
        HTTP_X_BOT_TOKEN="other",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_valid_consume_returns_ok_and_binds(client, api_url, settings):
    settings.BOT_API_TOKEN = "secret"
    student = Student.objects.create(full_name="Иванов Иван")
    invite = TelegramInviteToken.objects.create(student=student)

    resp = client.post(
        api_url,
        data={"token": invite.token, "chat_id": 42},
        content_type="application/json",
        HTTP_X_BOT_TOKEN="secret",
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "name": "Иванов Иван"}
    student.refresh_from_db()
    assert student.telegram_chat_id == 42


@pytest.mark.django_db
def test_invalid_token_returns_business_error(client, api_url, settings):
    settings.BOT_API_TOKEN = "secret"

    resp = client.post(
        api_url,
        data={"token": "does-not-exist", "chat_id": 42},
        content_type="application/json",
        HTTP_X_BOT_TOKEN="secret",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"ok": False, "error": "invalid_token"}


@pytest.mark.django_db
def test_missing_fields_return_400(client, api_url, settings):
    settings.BOT_API_TOKEN = "secret"

    resp = client.post(
        api_url,
        data={"chat_id": 42},
        content_type="application/json",
        HTTP_X_BOT_TOKEN="secret",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_non_integer_chat_id_returns_400(client, api_url, settings):
    settings.BOT_API_TOKEN = "secret"
    student = Student.objects.create(full_name="Иванов")
    invite = TelegramInviteToken.objects.create(student=student)

    resp = client.post(
        api_url,
        data={"token": invite.token, "chat_id": "not-int"},
        content_type="application/json",
        HTTP_X_BOT_TOKEN="secret",
    )
    assert resp.status_code == 400
