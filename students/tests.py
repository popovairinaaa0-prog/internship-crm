"""Тесты студентов и справочника направлений."""

import pytest

from students.models import Direction, Student, StudentStatus, TelegramInviteToken


@pytest.mark.django_db
def test_create_direction():
    d = Direction.objects.create(name="Python", slug="python")
    assert d.pk is not None
    assert str(d) == "Python"
    assert d.is_active is True


@pytest.mark.django_db
def test_create_student_with_directions():
    py = Direction.objects.create(name="Python", slug="python")
    qa = Direction.objects.create(name="QA", slug="qa")

    s = Student.objects.create(
        full_name="Иванов Иван",
        telegram_username="ivanov",
        email="ivanov@example.com",
        status=StudentStatus.STUDYING,
    )
    s.directions.add(py, qa)

    assert s.pk is not None
    assert str(s) == "Иванов Иван"
    assert set(s.directions.all()) == {py, qa}


@pytest.mark.django_db
def test_invite_token_default_valid():
    s = Student.objects.create(full_name="Петров Пётр")
    t = TelegramInviteToken.objects.create(student=s)
    assert t.is_valid() is True
    assert t.used_at is None
    assert len(t.token) >= 30
