"""Расчёты для главного дашборда.

Все расчёты собраны в одной функции `build_dashboard_data`, чтобы их можно
было кешировать одним вызовом и удобно тестировать.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from companies.models import Company, HiringStatus
from notifications.models import (
    BroadcastJob,
    BroadcastStatus,
    DeliveryStatus,
    ManualContact,
)
from placements.models import ACTIVE_STATUSES, Placement, PlacementStatus
from students.models import Student, StudentStatus


def build_dashboard_data() -> dict[str, Any]:
    """Собирает все данные для главной страницы за один проход."""
    today = timezone.localdate()
    now = timezone.now()
    stale_days = getattr(settings, "PLACEMENT_STALE_CRITICAL_DAYS", 14)
    pause_days = getattr(settings, "COMPANY_PAUSE_ALERT_DAYS", 30)
    stale_cutoff = now - timedelta(days=stale_days)
    pause_cutoff = now - timedelta(days=pause_days)

    metrics = _build_metrics()
    alerts = _build_alerts(today=today, stale_cutoff=stale_cutoff, pause_cutoff=pause_cutoff)
    student_counts = _build_student_counts()
    company_counts = _build_company_counts(stale_cutoff=stale_cutoff)
    recent_events = _build_recent_events(limit=5)

    return {
        "metrics": metrics,
        "alerts": alerts,
        "student_counts": student_counts,
        "company_counts": company_counts,
        "recent_events": recent_events,
        "generated_at": now,
    }


def _build_metrics() -> dict[str, Any]:
    students_total = Student.objects.count()
    students_waiting = Student.objects.filter(status=StudentStatus.WAITING).count()

    companies_total = Company.objects.count()
    companies_open = Company.objects.filter(hiring_status=HiringStatus.OPEN).count()

    placements_in_progress = Placement.objects.filter(
        status=PlacementStatus.IN_PROGRESS
    ).count()
    companies_with_progress = (
        Placement.objects.filter(status=PlacementStatus.IN_PROGRESS)
        .values("company_id")
        .distinct()
        .count()
    )

    placements_sent = Placement.objects.filter(
        status=PlacementStatus.SENT_TO_COMPANY
    ).count()

    student_list = reverse("admin:students_student_changelist")
    company_list = reverse("admin:companies_company_changelist")
    placement_list = reverse("admin:placements_placement_changelist")

    return {
        "students_total": students_total,
        "students_waiting": students_waiting,
        "students_url": student_list,
        "students_waiting_url": student_list + f"?status__exact={StudentStatus.WAITING}",

        "companies_total": companies_total,
        "companies_open": companies_open,
        "companies_url": company_list,
        "companies_open_url": company_list + f"?hiring_status__exact={HiringStatus.OPEN}",

        "placements_in_progress": placements_in_progress,
        "companies_with_progress": companies_with_progress,
        "placements_in_progress_url": placement_list + f"?status__exact={PlacementStatus.IN_PROGRESS}",

        "placements_sent": placements_sent,
        "placements_sent_url": placement_list + f"?status__exact={PlacementStatus.SENT_TO_COMPANY}",
    }


def _build_alerts(*, today, stale_cutoff, pause_cutoff) -> list[dict]:
    alerts = []

    # 1. Зависшие связки
    stale = Placement.objects.filter(
        status=PlacementStatus.SENT_TO_COMPANY,
        status_changed_at__lte=stale_cutoff,
    ).count()
    if stale > 0:
        alerts.append(
            {
                "level": "critical",
                "title": f"{stale} студентов ждут решения компании > 14 дней",
                "subtitle": "Стоит пушнуть",
                "url": reverse("admin:placements_placement_changelist")
                + f"?status__exact={PlacementStatus.SENT_TO_COMPANY}",
            }
        )

    # 2. Просроченные контакты
    overdue_contacts = Student.objects.filter(next_contact_at__lt=today).count()
    if overdue_contacts > 0:
        alerts.append(
            {
                "level": "critical",
                "title": f"{overdue_contacts} контактов со студентами просрочены",
                "subtitle": "Нужно связаться",
                "url": reverse("admin:students_student_changelist")
                + "?contact_due=overdue",
            }
        )

    # 3. Превышен срок стажировки — считаем через raw SQL
    overdue_internships = Placement.objects.filter(
        status=PlacementStatus.IN_PROGRESS,
        started_at__isnull=False,
        planned_duration_days__isnull=False,
    ).extra(
        where=["started_at + (planned_duration_days || ' days')::interval < %s"],
        params=[today],
    ).count()
    if overdue_internships > 0:
        alerts.append(
            {
                "level": "warning",
                "title": f"{overdue_internships} стажировок превысили плановый срок",
                "subtitle": "Проверить статус",
                "url": reverse("admin:placements_placement_changelist")
                + f"?status__exact={PlacementStatus.IN_PROGRESS}",
            }
        )

    # 4. Компании на паузе давно
    paused_long = Company.objects.filter(
        hiring_status=HiringStatus.PAUSED,
        status_changed_at__lte=pause_cutoff,
    ).count()
    if paused_long > 0:
        alerts.append(
            {
                "level": "warning",
                "title": f"{paused_long} компаний на паузе > 30 дней",
                "subtitle": "Уточнить статус",
                "url": reverse("admin:companies_company_changelist")
                + f"?hiring_status__exact={HiringStatus.PAUSED}",
            }
        )

    # 5. Контакты сегодня
    today_contacts = Student.objects.filter(next_contact_at=today).count()
    if today_contacts > 0:
        alerts.append(
            {
                "level": "warning",
                "title": f"{today_contacts} контактов со студентами сегодня",
                "subtitle": "В календаре на сегодня",
                "url": reverse("admin:students_student_changelist")
                + "?contact_due=today",
            }
        )

    return alerts


def _build_student_counts() -> list[dict]:
    raw = dict(
        Student.objects.values_list("status").annotate(c=Count("id"))
    )
    base_url = reverse("admin:students_student_changelist")
    order = [
        (StudentStatus.STUDYING, "Обучается", "purple"),
        (StudentStatus.WAITING, "Ожидает", "amber"),
        (StudentStatus.IN_PROGRESS, "Стажируется", "teal"),
        (StudentStatus.COMPLETED, "Прошёл", "gray"),
        (StudentStatus.DROPPED, "Отчислен", "gray-light"),
    ]
    return [
        {
            "label": label,
            "count": raw.get(status, 0),
            "color": color,
            "url": base_url + f"?status__exact={status}",
        }
        for status, label, color in order
    ]


def _build_company_counts(*, stale_cutoff) -> list[dict]:
    raw = dict(
        Company.objects.values_list("hiring_status").annotate(c=Count("id"))
    )
    base_url = reverse("admin:companies_company_changelist")
    rows = [
        {
            "label": "Принимают",
            "count": raw.get(HiringStatus.OPEN, 0),
            "color": "green",
            "url": base_url + f"?hiring_status__exact={HiringStatus.OPEN}",
        },
        {
            "label": "Пауза",
            "count": raw.get(HiringStatus.PAUSED, 0),
            "color": "amber",
            "url": base_url + f"?hiring_status__exact={HiringStatus.PAUSED}",
        },
        {
            "label": "Не принимают",
            "count": raw.get(HiringStatus.CLOSED, 0),
            "color": "gray",
            "url": base_url + f"?hiring_status__exact={HiringStatus.CLOSED}",
        },
    ]

    # Отдельной строкой — компании с зависшими placement'ами
    stale_companies = (
        Placement.objects.filter(
            status=PlacementStatus.SENT_TO_COMPANY,
            status_changed_at__lte=stale_cutoff,
        )
        .values("company_id")
        .distinct()
        .count()
    )
    if stale_companies > 0:
        rows.append(
            {
                "label": "С зависшими",
                "count": stale_companies,
                "color": "red",
                "highlight": True,
                "url": base_url + "?has_stale=yes",
            }
        )
    return rows


def _build_recent_events(*, limit: int) -> list[dict]:
    """Последние 5 событий из разных источников, отсортированные по времени."""
    events: list[dict] = []

    # LogEntry — общие изменения в админке
    for entry in LogEntry.objects.select_related("content_type")[: limit * 2]:
        events.append(
            {
                "when": entry.action_time,
                "text": f"{entry.user or 'система'}: {entry.get_action_flag_display()} «{entry.object_repr}»",
                "kind": "admin",
            }
        )

    # Завершённые рассылки
    for job in BroadcastJob.objects.filter(
        status=BroadcastStatus.DONE, finished_at__isnull=False
    ).order_by("-finished_at")[:limit]:
        sent = job.deliveries.filter(status=DeliveryStatus.SENT).count()
        total = job.recipients.count()
        events.append(
            {
                "when": job.finished_at,
                "text": f"Рассылка #{job.pk} отправлена ({sent}/{total})",
                "kind": "broadcast",
            }
        )

    # Ручные отметки
    for mc in ManualContact.objects.select_related("student", "manager").order_by(
        "-contacted_at"
    )[:limit]:
        manager = mc.manager.get_full_name() if mc.manager else "—"
        events.append(
            {
                "when": mc.contacted_at,
                "text": f"{manager} написал(а) {mc.student.full_name}",
                "kind": "manual_contact",
            }
        )

    # Смены статуса Placement (по status_changed_at)
    for p in Placement.objects.select_related("student", "company").order_by(
        "-status_changed_at"
    )[:limit]:
        events.append(
            {
                "when": p.status_changed_at,
                "text": f"{p.student.full_name} → {p.company.name}: «{p.get_status_display()}»",
                "kind": "placement_status",
            }
        )

    # Сортируем и отрезаем
    events.sort(key=lambda x: x["when"], reverse=True)
    return events[:limit]
