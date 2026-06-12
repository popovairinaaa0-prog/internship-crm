"""Тесты дашборда и healthz."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from companies.models import Company, HiringStatus
from notifications.dashboard import build_dashboard_data
from placements.models import Placement, PlacementStatus
from students.models import Direction, Student, StudentStatus


@pytest.fixture
def admin_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="dash_admin", password="x", is_staff=True, is_superuser=True
    )


@pytest.mark.django_db
def test_build_dashboard_empty_db():
    data = build_dashboard_data()
    assert data["metrics"]["students_total"] == 0
    assert data["metrics"]["companies_total"] == 0
    assert data["alerts"] == []


@pytest.mark.django_db
def test_dashboard_metrics_count_correctly():
    direction = Direction.objects.create(name="Python", slug="python")
    s1 = Student.objects.create(full_name="A", status=StudentStatus.WAITING)
    Student.objects.create(full_name="B", status=StudentStatus.STUDYING)
    c = Company.objects.create(name="Open Co", hiring_status=HiringStatus.OPEN)
    Company.objects.create(name="Paused Co", hiring_status=HiringStatus.PAUSED)
    Placement.objects.create(
        student=s1, company=c, direction=direction, status=PlacementStatus.IN_PROGRESS
    )
    Placement.objects.create(
        student=s1, company=c, direction=direction, status=PlacementStatus.SENT_TO_COMPANY
    )

    data = build_dashboard_data()
    m = data["metrics"]
    assert m["students_total"] == 2
    assert m["students_waiting"] == 1
    assert m["companies_total"] == 2
    assert m["companies_open"] == 1
    assert m["placements_in_progress"] == 1
    assert m["placements_sent"] == 1


@pytest.mark.django_db
def test_dashboard_alerts_for_stale_placement():
    direction = Direction.objects.create(name="Python", slug="python")
    s = Student.objects.create(full_name="A")
    c = Company.objects.create(name="Co")
    p = Placement.objects.create(
        student=s, company=c, direction=direction, status=PlacementStatus.SENT_TO_COMPANY
    )
    Placement.objects.filter(pk=p.pk).update(
        status_changed_at=timezone.now() - timedelta(days=20)
    )

    data = build_dashboard_data()
    titles = [a["title"] for a in data["alerts"]]
    assert any("ждут решения" in t for t in titles)


@pytest.mark.django_db
def test_dashboard_alerts_for_overdue_contacts():
    Student.objects.create(
        full_name="Late", next_contact_at=date.today() - timedelta(days=2)
    )
    data = build_dashboard_data()
    titles = [a["title"] for a in data["alerts"]]
    assert any("просрочены" in t for t in titles)


@pytest.mark.django_db
def test_dashboard_alerts_for_paused_company():
    c = Company.objects.create(name="Paused", hiring_status=HiringStatus.PAUSED)
    Company.objects.filter(pk=c.pk).update(
        status_changed_at=timezone.now() - timedelta(days=40)
    )
    data = build_dashboard_data()
    titles = [a["title"] for a in data["alerts"]]
    assert any("на паузе" in t for t in titles)


@pytest.mark.django_db
def test_dashboard_recent_events_includes_placement_change():
    direction = Direction.objects.create(name="Python", slug="python")
    s = Student.objects.create(full_name="Иванов")
    c = Company.objects.create(name="Ромашка")
    Placement.objects.create(
        student=s, company=c, direction=direction, status=PlacementStatus.SENT_TO_COMPANY
    )

    data = build_dashboard_data()
    assert len(data["recent_events"]) >= 1
    assert any("Иванов" in e["text"] for e in data["recent_events"])


@pytest.mark.django_db
def test_admin_index_shows_dashboard(client, admin_user):
    Student.objects.create(full_name="X", status=StudentStatus.WAITING)
    client.force_login(admin_user)

    resp = client.get(reverse("admin:index"))
    assert resp.status_code == 200
    assert b"dash-grid" in resp.content
    assert "Студентов".encode("utf-8") in resp.content


# --- healthz -----------------------------------------------------------


@pytest.mark.django_db
def test_healthz_ok(client):
    resp = client.get(reverse("healthz"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["db"] == "ok"
