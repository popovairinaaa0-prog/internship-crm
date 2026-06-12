"""API-эндпоинты для служебного бота."""

from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.services import consume_manager_invite_token


BOT_TOKEN_HEADER = "HTTP_X_BOT_TOKEN"


def _check_bot_token(request) -> bool:
    expected = getattr(settings, "BOT_API_TOKEN", "")
    if not expected:
        return False
    return request.META.get(BOT_TOKEN_HEADER, "") == expected


class ConsumeManagerInviteView(APIView):
    """POST /api/managers/consume-invite/

    Body: {"token": "mgr_...", "chat_id": 12345}
    Header: X-Bot-Token: <BOT_API_TOKEN>

    Ответ:
      200 {"ok": true, "name": "Имя менеджера"}
      200 {"ok": false, "error": "invalid_token"}
      401 — нет/неверный X-Bot-Token
      400 — нет поля token или chat_id
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

        user = consume_manager_invite_token(str(token), chat_id_int)
        if user is None:
            return Response({"ok": False, "error": "invalid_token"})

        return Response(
            {
                "ok": True,
                "name": user.get_full_name() or user.username,
            }
        )
