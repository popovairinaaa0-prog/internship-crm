"""API-эндпоинты, доступные ботам."""

from __future__ import annotations

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.http import JsonResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from students.models import Student
from students.services import consume_invite_token


BOT_TOKEN_HEADER = "HTTP_X_BOT_TOKEN"


def _check_bot_token(request) -> bool:
    expected = getattr(settings, "BOT_API_TOKEN", "")
    if not expected:
        return False  # На проде с пустым токеном всё закрыто
    return request.META.get(BOT_TOKEN_HEADER, "") == expected


class ConsumeInviteView(APIView):
    """POST /api/students/consume-invite/

    Body: {"token": "...", "chat_id": 12345}
    Header: X-Bot-Token: <BOT_API_TOKEN из .env>

    Ответ:
      200 {"ok": true, "name": "Иванов Иван"}      — активация прошла
      200 {"ok": false, "error": "invalid_token"}  — токен не найден/протух/использован
      401                                          — нет/неверный X-Bot-Token
      400                                          — нет поля token или chat_id
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not _check_bot_token(request):
            return Response(
                {"ok": False, "error": "unauthorized"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = request.data.get("token")
        chat_id = request.data.get("chat_id")
        if not token or chat_id is None:
            return Response(
                {"ok": False, "error": "token and chat_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            chat_id_int = int(chat_id)
        except (TypeError, ValueError):
            return Response(
                {"ok": False, "error": "chat_id must be integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student = consume_invite_token(str(token), chat_id_int)
        if student is None:
            return Response({"ok": False, "error": "invalid_token"})

        return Response({"ok": True, "name": student.full_name})


@staff_member_required
def student_autocomplete(request):
    """JSON-эндпоинт для autocomplete на форме рассылки.

    Возвращает до 20 студентов, у которых ФИО/telegram_username содержат `q`.
    """
    q = request.GET.get("q", "").strip()
    qs = Student.objects.all()
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(telegram_username__icontains=q))
    results = [
        {
            "id": s.pk,
            "label": s.full_name,
            "telegram_username": s.telegram_username,
            "has_chat_id": s.telegram_chat_id is not None,
        }
        for s in qs.order_by("full_name")[:20]
    ]
    return JsonResponse({"results": results})
