"""Тесты сервисов и API онбординга менеджеров."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from accounts.models import ManagerInviteToken
from accounts.services import (
    consume_manager_invite_token,
    create_manager_invite_link,
)


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="manager_a", password="x", first_name="Анна", last_name="Менеджер"
    )


# --- Сервисы ----------------------------------------------------------


@pytest.mark.django_db
def test_create_manager_invite_link_uses_settings_username(user, settings):
    settings.MANAGERS_BOT_USERNAME = "test_mgr_bot"

    url = create_manager_invite_link(user)

    assert url.startswith("https://t.me/test_mgr_bot?start=mgr_")
    token = url.split("start=", 1)[1]
    assert ManagerInviteToken.objects.filter(token=token, user=user).exists()


@pytest.mark.django_db
def test_consume_manager_invite_token_valid_binds(user):
    invite = ManagerInviteToken.objects.create(user=user)

    result = consume_manager_invite_token(invite.token, chat_id=777)

    assert result == user
    user.refresh_from_db()
    assert user.telegram_chat_id == 777
    invite.refresh_from_db()
    assert invite.used_at is not None


@pytest.mark.django_db
def test_consume_manager_invite_token_unknown_returns_none():
    result = consume_manager_invite_token("does-not-exist", chat_id=42)
    assert result is None


@pytest.mark.django_db
def test_consume_manager_invite_token_expired_returns_none(user):
    invite = ManagerInviteToken.objects.create(user=user)
    ManagerInviteToken.objects.filter(pk=invite.pk).update(
        expires_at=timezone.now() - timedelta(days=1)
    )

    result = consume_manager_invite_token(invite.token, chat_id=42)

    assert result is None
    user.refresh_from_db()
    assert user.telegram_chat_id is None


@pytest.mark.django_db
def test_consume_manager_invite_token_already_used_returns_none(user):
    invite = ManagerInviteToken.objects.create(user=user, used_at=timezone.now())
    result = consume_manager_invite_token(invite.token, chat_id=42)
    assert result is None


@pytest.mark.django_db
def test_consume_manager_invite_token_chat_id_already_bound(user):
    User = get_user_model()
    other = User.objects.create_user(
        username="other", password="x", telegram_chat_id=42
    )
    invite = ManagerInviteToken.objects.create(user=user)

    result = consume_manager_invite_token(invite.token, chat_id=42)

    assert result is None
    user.refresh_from_db()
    assert user.telegram_chat_id is None
    other.refresh_from_db()
    assert other.telegram_chat_id == 42


# --- API endpoint -----------------------------------------------------


@pytest.fixture
def api_url():
    return reverse("accounts_api:consume_invite")


@pytest.mark.django_db
def test_api_requires_bot_token(client, api_url, user, settings):
    settings.BOT_API_TOKEN = "secret"
    invite = ManagerInviteToken.objects.create(user=user)

    resp = client.post(
        api_url,
        data={"token": invite.token, "chat_id": 42},
        content_type="application/json",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_api_valid_binds_and_returns_name(client, api_url, user, settings):
    settings.BOT_API_TOKEN = "secret"
    invite = ManagerInviteToken.objects.create(user=user)

    resp = client.post(
        api_url,
        data={"token": invite.token, "chat_id": 42},
        content_type="application/json",
        HTTP_X_BOT_TOKEN="secret",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["name"] == "Анна Менеджер"
    user.refresh_from_db()
    assert user.telegram_chat_id == 42


@pytest.mark.django_db
def test_api_invalid_token_returns_business_error(client, api_url, settings):
    settings.BOT_API_TOKEN = "secret"
    resp = client.post(
        api_url,
        data={"token": "missing", "chat_id": 42},
        content_type="application/json",
        HTTP_X_BOT_TOKEN="secret",
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": False, "error": "invalid_token"}
