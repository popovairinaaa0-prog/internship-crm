"""Views для рассылок и автопушей. На этапе 3 — только заглушка."""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from students.models import Student


@staff_member_required
def broadcast_new(request):
    """Заглушка экрана рассылки. Полноценная форма — на этапе 7."""
    raw_ids = request.GET.get("ids", "")
    ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
    students = (
        Student.objects.filter(pk__in=ids).prefetch_related("directions") if ids else []
    )
    return render(
        request,
        "admin/notifications/broadcast_new_placeholder.html",
        {
            "students": students,
            "count": len(students),
            "title": "Рассылка в Telegram (этап 7)",
        },
    )
