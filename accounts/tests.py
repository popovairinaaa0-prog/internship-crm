"""Тесты ролей и прав: admin vs vip_managers."""

from __future__ import annotations

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse

from companies.models import Company
from notifications.admin import CommentAdmin
from notifications.models import Comment
from placements.admin import PlacementAdmin
from placements.models import Placement
from students.models import Direction, Student


# --- Фикстуры -----------------------------------------------------------


@pytest.fixture
def User(db):
    return get_user_model()


@pytest.fixture
def admin_user(User):
    u = User.objects.create_user(
        username="ira_admin",
        email="ira_admin@local.dev",
        password="x",
        is_superuser=True,
        is_staff=True,
    )
    u.groups.add(Group.objects.get(name="admins"))
    return u


@pytest.fixture
def vip_user(User):
    u = User.objects.create_user(
        username="ira_vip",
        email="ira_vip@local.dev",
        password="x",
        is_staff=True,
    )
    u.groups.add(Group.objects.get(name="vip_managers"))
    return u


@pytest.fixture
def other_vip_user(User):
    u = User.objects.create_user(
        username="other_vip",
        email="other_vip@local.dev",
        password="x",
        is_staff=True,
    )
    u.groups.add(Group.objects.get(name="vip_managers"))
    return u


@pytest.fixture
def trio(db):
    direction = Direction.objects.create(name="Python", slug="python")
    student = Student.objects.create(full_name="Иванов Иван")
    company = Company.objects.create(name="ООО Ромашка")
    return student, company, direction


# --- Группы созданы миграцией -------------------------------------------


@pytest.mark.django_db
def test_groups_exist_with_permissions():
    """Миграция 0003 должна создать обе группы с нужными правами."""
    admins = Group.objects.get(name="admins")
    vip = Group.objects.get(name="vip_managers")

    # У admins — все права на проектные модели
    assert admins.permissions.filter(codename="delete_student").exists()

    # У vip — нет delete_student, нет change_student, но есть view_student
    vip_codenames = set(vip.permissions.values_list("codename", flat=True))
    assert "view_student" in vip_codenames
    assert "delete_student" not in vip_codenames
    assert "change_student" not in vip_codenames
    assert "add_student" not in vip_codenames
    assert "change_placement" in vip_codenames  # будет ограничено readonly_fields
    assert "add_comment" in vip_codenames
    assert "change_comment" in vip_codenames
    assert "delete_comment" not in vip_codenames


# --- VIP в админке: студент/компания -----------------------------------


@pytest.mark.django_db
def test_vip_cannot_delete_student(client, vip_user, trio):
    student, _, _ = trio
    client.force_login(vip_user)
    url = reverse("admin:students_student_delete", args=[student.pk])
    resp = client.post(url, {"post": "yes"})
    assert resp.status_code == 403
    assert Student.objects.filter(pk=student.pk).exists()


@pytest.mark.django_db
def test_vip_cannot_change_student(client, vip_user, trio):
    student, _, direction = trio
    client.force_login(vip_user)
    url = reverse("admin:students_student_change", args=[student.pk])
    resp = client.post(
        url,
        {"full_name": "ПОДМЕНА", "status": "STUDYING", "directions": [direction.pk]},
    )
    # VIP без change_student → 403 на POST
    assert resp.status_code == 403
    student.refresh_from_db()
    assert student.full_name == "Иванов Иван"


@pytest.mark.django_db
def test_admin_can_delete_student(client, admin_user, trio):
    student, _, _ = trio
    client.force_login(admin_user)
    url = reverse("admin:students_student_delete", args=[student.pk])
    resp = client.post(url, {"post": "yes"})
    # 302 редирект на список после удаления
    assert resp.status_code == 302
    assert not Student.objects.filter(pk=student.pk).exists()


# --- VIP в PlacementAdmin: только status редактируем -------------------


@pytest.mark.django_db
def test_placement_admin_vip_readonly_fields(rf, vip_user, admin_user, trio):
    student, company, direction = trio
    placement = Placement.objects.create(
        student=student, company=company, direction=direction
    )
    admin = PlacementAdmin(Placement, AdminSite())

    req_vip = rf.get("/")
    req_vip.user = vip_user
    ro_vip = set(admin.get_readonly_fields(req_vip, placement))
    # Все «полезные» поля заморожены, кроме status
    assert "student" in ro_vip
    assert "company" in ro_vip
    assert "direction" in ro_vip
    assert "planned_duration_days" in ro_vip
    assert "comment" in ro_vip
    assert "status" not in ro_vip

    req_admin = rf.get("/")
    req_admin.user = admin_user
    ro_admin = set(admin.get_readonly_fields(req_admin, placement))
    # У админа readonly только служебные счётчики и created_at/updated_at
    assert "student" not in ro_admin
    assert "comment" not in ro_admin
    assert "status_changed_at" in ro_admin  # это readonly для всех


# --- VIP комментирует: только свои -------------------------------------


@pytest.mark.django_db
def test_comment_admin_filters_to_own_comments_for_vip(rf, vip_user, other_vip_user, trio):
    student, _, _ = trio
    ct = ContentType.objects.get_for_model(Student)
    own = Comment.objects.create(
        content_type=ct, object_id=student.pk, author=vip_user, text="мой"
    )
    others = Comment.objects.create(
        content_type=ct, object_id=student.pk, author=other_vip_user, text="чужой"
    )

    admin = CommentAdmin(Comment, AdminSite())
    req = rf.get("/")
    req.user = vip_user
    qs_ids = set(admin.get_queryset(req).values_list("id", flat=True))
    assert own.id in qs_ids
    assert others.id not in qs_ids


@pytest.mark.django_db
def test_vip_can_change_own_comment_not_others(rf, vip_user, other_vip_user, trio):
    student, _, _ = trio
    ct = ContentType.objects.get_for_model(Student)
    own = Comment.objects.create(
        content_type=ct, object_id=student.pk, author=vip_user, text="мой"
    )
    others = Comment.objects.create(
        content_type=ct, object_id=student.pk, author=other_vip_user, text="чужой"
    )

    admin = CommentAdmin(Comment, AdminSite())
    req = rf.get("/")
    req.user = vip_user

    assert admin.has_change_permission(req, own) is True
    assert admin.has_change_permission(req, others) is False
    # Удалять нельзя ни свой, ни чужой
    assert admin.has_delete_permission(req, own) is False
    assert admin.has_delete_permission(req, others) is False


@pytest.mark.django_db
def test_admin_can_change_any_comment(rf, admin_user, other_vip_user, trio):
    student, _, _ = trio
    ct = ContentType.objects.get_for_model(Student)
    foreign = Comment.objects.create(
        content_type=ct, object_id=student.pk, author=other_vip_user, text="чужой"
    )

    admin = CommentAdmin(Comment, AdminSite())
    req = rf.get("/")
    req.user = admin_user

    assert admin.has_change_permission(req, foreign) is True
    assert admin.has_delete_permission(req, foreign) is True


# --- helpers ------------------------------------------------------------


@pytest.fixture
def rf():
    return RequestFactory()
