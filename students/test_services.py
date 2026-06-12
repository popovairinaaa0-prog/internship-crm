"""Тесты сервисов студентов: create_invite_link / consume_invite_token."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from students.models import Student, TelegramInviteToken
from students.services import consume_invite_token, create_invite_link


@pytest.mark.django_db
def test_create_invite_link_returns_t_me_url(settings):
    settings.STUDENT_BOT_USERNAME = "test_bot"
    s = Student.objects.create(full_name="Иванов Иван")

    url = create_invite_link(s)

    assert url.startswith("https://t.me/test_bot?start=")
    token = url.split("start=", 1)[1]
    assert TelegramInviteToken.objects.filter(token=token, student=s).exists()


@pytest.mark.django_db
def test_consume_invite_token_valid_binds_chat_id():
    s = Student.objects.create(full_name="Иванов Иван")
    invite = TelegramInviteToken.objects.create(student=s)

    result = consume_invite_token(invite.token, chat_id=42)

    assert result == s
    s.refresh_from_db()
    assert s.telegram_chat_id == 42

    invite.refresh_from_db()
    assert invite.used_at is not None


@pytest.mark.django_db
def test_consume_invite_token_unknown_returns_none():
    s = Student.objects.create(full_name="Иванов Иван")

    result = consume_invite_token("does-not-exist", chat_id=42)

    assert result is None
    s.refresh_from_db()
    assert s.telegram_chat_id is None


@pytest.mark.django_db
def test_consume_invite_token_expired_returns_none():
    s = Student.objects.create(full_name="Иванов Иван")
    invite = TelegramInviteToken.objects.create(student=s)
    # Сдвигаем срок в прошлое
    TelegramInviteToken.objects.filter(pk=invite.pk).update(
        expires_at=timezone.now() - timedelta(days=1)
    )

    result = consume_invite_token(invite.token, chat_id=42)

    assert result is None
    s.refresh_from_db()
    assert s.telegram_chat_id is None


@pytest.mark.django_db
def test_consume_invite_token_already_used_returns_none():
    s = Student.objects.create(full_name="Иванов Иван")
    invite = TelegramInviteToken.objects.create(student=s, used_at=timezone.now())

    result = consume_invite_token(invite.token, chat_id=42)

    assert result is None


@pytest.mark.django_db
def test_consume_invite_token_chat_id_already_bound_to_other():
    other = Student.objects.create(full_name="Старый", telegram_chat_id=42)
    new = Student.objects.create(full_name="Новый")
    invite = TelegramInviteToken.objects.create(student=new)

    result = consume_invite_token(invite.token, chat_id=42)

    assert result is None
    new.refresh_from_db()
    assert new.telegram_chat_id is None
    other.refresh_from_db()
    assert other.telegram_chat_id == 42
