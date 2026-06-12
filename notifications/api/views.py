"""API для служебного бота: регистрация ручных контактов."""

from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.services import register_manual_contact


BOT_TOKEN_HEADER = "HTTP_X_BOT_TOKEN"


def _check_bot_token(request) -> bool:
    expected = getattr(settings, "BOT_API_TOKEN", "")
    if not expected:
        return False
    return request.META.get(BOT_TOKEN_HEADER, "") == expected


class RegisterManualContactView(APIView):
    """POST /api/manual-contacts/

    Body: {"student_id": 1, "broadcast_job_id": 2, "manager_telegram_id": 99}
    Header: X-Bot-Token

    Ответ:
      200 {"ok": true, "created": true,  "manager_name": "..."}  — создано
      200 {"ok": true, "created": false, "manager_name": "..."}  — toggle-удалено
      200 {"ok": false, "error": "not_bound"}                    — менеджер не привязан
      400 — нет student_id или manager_telegram_id
      401 — нет/неверный X-Bot-Token
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not _check_bot_token(request):
            return Response(
                {"ok": False, "error": "unauthorized"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        student_id = request.data.get("student_id")
        manager_telegram_id = request.data.get("manager_telegram_id")
        broadcast_job_id = request.data.get("broadcast_job_id")

        if student_id is None or manager_telegram_id is None:
            return Response(
                {"ok": False, "error": "student_id and manager_telegram_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            student_id_int = int(student_id)
            manager_telegram_id_int = int(manager_telegram_id)
            broadcast_job_id_int = (
                int(broadcast_job_id) if broadcast_job_id is not None else None
            )
        except (TypeError, ValueError):
            return Response(
                {"ok": False, "error": "ids must be integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created, contact = register_manual_contact(
            student_id=student_id_int,
            broadcast_job_id=broadcast_job_id_int,
            manager_telegram_id=manager_telegram_id_int,
        )
        if contact is None:
            return Response({"ok": False, "error": "not_bound"})

        manager_name = contact.manager.get_full_name() or contact.manager.username
        return Response(
            {
                "ok": True,
                "created": created,
                "manager_name": manager_name,
                "student_id": student_id_int,
            }
        )
