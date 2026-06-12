"""Views для рассылок и дашборда."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from students.models import Student

from .dashboard import build_dashboard_data
from .models import BroadcastJob, BroadcastStatus, DeliveryStatus
from .services import (
    collect_delivery_stats,
    create_broadcast_job,
    enqueue_broadcast,
    render_message,
)


DASHBOARD_CACHE_KEY = "dashboard_data"
DASHBOARD_CACHE_TTL = 60  # секунд


def get_dashboard_data() -> dict:
    """Берёт данные дашборда из кеша или строит заново."""
    return cache.get_or_set(DASHBOARD_CACHE_KEY, build_dashboard_data, DASHBOARD_CACHE_TTL)


def healthz(request):
    """Health-check эндпоинт. Возвращает 200 если БД доступна, 503 иначе."""
    from django.db import connection

    db_ok = True
    error = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        error = str(exc)

    return JsonResponse(
        {"ok": db_ok, "db": "ok" if db_ok else "error", "error": error},
        status=200 if db_ok else 503,
    )


def _parse_ids(raw: str) -> list[int]:
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]


def _serialize_recipient(s: Student) -> dict:
    return {
        "id": s.pk,
        "label": s.full_name,
        "telegram_username": s.telegram_username,
        "has_chat_id": s.telegram_chat_id is not None,
    }


@staff_member_required
@require_http_methods(["GET", "POST"])
def broadcast_new(request):
    """Форма создания и запуска рассылки."""
    if request.method == "POST":
        return _handle_broadcast_post(request)

    raw_ids = request.GET.get("ids", "")
    ids = _parse_ids(raw_ids)
    students = list(Student.objects.filter(pk__in=ids).order_by("full_name"))

    recipients_json = [_serialize_recipient(s) for s in students]
    preview_for = students[0] if students else None
    preview_text = (
        render_message("Привет, {имя}!", preview_for) if preview_for else "Привет!"
    )

    context = {
        "title": "Рассылка в Telegram",
        "recipients": students,
        "recipients_json": recipients_json,
        "preview_text": preview_text,
        "preview_for": preview_for,
    }
    return render(request, "admin/notifications/broadcast_new.html", context)


def _handle_broadcast_post(request):
    action = request.POST.get("action", "send")
    text = request.POST.get("message_text", "").strip()
    raw_ids = request.POST.get("recipient_ids", "")
    ids = _parse_ids(raw_ids)

    if not text:
        messages.error(request, "Текст сообщения не может быть пустым.")
        return HttpResponseRedirect(
            reverse("notifications:broadcast_new")
            + (f"?ids={raw_ids}" if raw_ids else "")
        )

    if not ids:
        messages.error(request, "Не выбран ни один получатель.")
        return HttpResponseRedirect(reverse("notifications:broadcast_new"))

    job = create_broadcast_job(
        created_by=request.user, message_text=text, recipient_ids=ids
    )

    if action == "draft":
        messages.success(request, f"Черновик сохранён (#{job.pk}).")
        return HttpResponseRedirect(
            reverse("admin:notifications_broadcastjob_change", args=[job.pk])
        )

    # action == "send"
    enqueue_broadcast(job)
    messages.success(request, f"Рассылка #{job.pk} поставлена в очередь.")
    return HttpResponseRedirect(
        reverse("notifications:broadcast_detail", args=[job.pk])
    )


@staff_member_required
def broadcast_detail(request, pk: int):
    """Страница статуса конкретной рассылки с live-poll."""
    job = get_object_or_404(BroadcastJob, pk=pk)
    stats = collect_delivery_stats(job)
    context = {
        "title": f"Рассылка #{job.pk}",
        "job": job,
        "stats": stats,
        "status_url": reverse("notifications:broadcast_status", args=[job.pk]),
        "is_finished": job.status in (BroadcastStatus.DONE, BroadcastStatus.FAILED),
    }
    return render(request, "admin/notifications/broadcast_detail.html", context)


@staff_member_required
def broadcast_status(request, pk: int):
    """JSON-эндпоинт для JS-поллинга."""
    job = get_object_or_404(BroadcastJob, pk=pk)
    stats = collect_delivery_stats(job)
    return JsonResponse(
        {
            "status": job.status,
            "status_label": job.get_status_display(),
            "is_finished": job.status in (BroadcastStatus.DONE, BroadcastStatus.FAILED),
            "stats": stats,
        }
    )
