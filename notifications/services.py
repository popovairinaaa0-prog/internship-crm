"""Сервисы рассылок и низкоуровневой отправки в Telegram."""

from __future__ import annotations

import logging
import time
from typing import Any, Iterable

import httpx
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django_q.tasks import async_task

from students.models import Student

from .models import (
    BroadcastDelivery,
    BroadcastJob,
    BroadcastStatus,
    DeliveryStatus,
    ManualContact,
)


logger = logging.getLogger(__name__)


# --- Низкоуровневая отправка ---------------------------------------------


_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_429_RETRIES = 3
_INTER_MESSAGE_PAUSE_SEC = 0.05  # 50мс между отправками — см. CLAUDE.md


class SafeDict(dict):
    """dict, который не падает на отсутствующих ключах: оставляет {key}.

    Нужно, чтобы шаблон рассылки с опечаткой не валил всю задачу — менеджер
    увидит {неизвестное_имя} в сообщении и поправит шаблон.
    """

    def __missing__(self, key):
        return "{" + key + "}"


def render_message(template_text: str, student: Student) -> str:
    """Подставляет {имя} = первое слово full_name. Не падает на лишних ключах."""
    first_name = (student.full_name or "").split()[0] if student.full_name else ""
    context = SafeDict({"имя": first_name})
    return template_text.format_map(context)


def send_telegram_message(
    chat_id: int,
    text: str,
    bot_token: str,
    *,
    inline_buttons: list[list[dict]] | None = None,
    _client: httpx.Client | None = None,
    _sleep=time.sleep,
) -> dict[str, Any]:
    """Отправляет сообщение через Telegram Bot API. Возвращает статус доставки.

    Args:
        chat_id: куда отправлять.
        text: текст (уже отрендеренный).
        bot_token: токен бота (разные для студентов и менеджеров).
        inline_buttons: опциональные inline-кнопки в формате InlineKeyboardMarkup.
        _client, _sleep: точки расширения для тестов.

    Returns dict вида {"status": "SENT|BLOCKED|FAILED", "error": "..."}.
    """
    url = _TELEGRAM_API_URL.format(token=bot_token)
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if inline_buttons:
        payload["reply_markup"] = {"inline_keyboard": inline_buttons}

    client = _client or httpx.Client(timeout=10.0)
    close_after = _client is None

    try:
        for attempt in range(_MAX_429_RETRIES + 1):
            try:
                resp = client.post(url, json=payload)
            except httpx.RequestError as exc:
                logger.warning("telegram network error for chat %s: %s", chat_id, exc)
                return {"status": DeliveryStatus.FAILED, "error": f"network: {exc}"}

            if resp.status_code == 200:
                return {"status": DeliveryStatus.SENT}

            if resp.status_code == 403:
                # bot was blocked / kicked
                return {"status": DeliveryStatus.BLOCKED, "error": resp.text[:200]}

            if resp.status_code == 429:
                # экспоненциальный backoff: 1, 2, 4 секунды
                if attempt == _MAX_429_RETRIES:
                    return {
                        "status": DeliveryStatus.FAILED,
                        "error": f"429 after {_MAX_429_RETRIES} retries",
                    }
                wait = 2**attempt
                logger.info("telegram 429 for chat %s, sleeping %ss", chat_id, wait)
                _sleep(wait)
                continue

            # Прочие 4xx/5xx — просто FAILED, без повторов
            return {
                "status": DeliveryStatus.FAILED,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }

        # Сюда мы прийти не должны, но на всякий случай
        return {"status": DeliveryStatus.FAILED, "error": "unreachable"}
    finally:
        if close_after:
            client.close()


# --- Высокоуровневая логика рассылки -------------------------------------


def enqueue_broadcast(job: BroadcastJob) -> str:
    """Кладёт задачу выполнения рассылки в django-q2."""
    return async_task("notifications.services.run_broadcast_worker", job.pk)


def _ensure_deliveries(job: BroadcastJob) -> None:
    """Создаёт BroadcastDelivery для каждого получателя, если их ещё нет."""
    existing_student_ids = set(
        BroadcastDelivery.objects.filter(job=job).values_list("student_id", flat=True)
    )
    to_create = [
        BroadcastDelivery(job=job, student=s, status=DeliveryStatus.PENDING)
        for s in job.recipients.all()
        if s.pk not in existing_student_ids
    ]
    if to_create:
        BroadcastDelivery.objects.bulk_create(to_create)


def run_broadcast_worker(
    job_id: int,
    *,
    _send=send_telegram_message,
    _sleep=time.sleep,
) -> None:
    """Воркер рассылки, дёргается django-q2 (или напрямую в тестах)."""
    job = BroadcastJob.objects.select_related("created_by").get(pk=job_id)

    # Идемпотентный старт: если кто-то уже завершил — не запускаем второй раз.
    if job.status in (BroadcastStatus.DONE, BroadcastStatus.FAILED):
        logger.info("broadcast %s already finished (%s) — skip", job.pk, job.status)
        return

    job.status = BroadcastStatus.RUNNING
    if job.started_at is None:
        job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    _ensure_deliveries(job)

    bot_token = getattr(settings, "STUDENT_BOT_TOKEN", "")
    if not bot_token:
        logger.error("broadcast %s: STUDENT_BOT_TOKEN пустой", job.pk)

    try:
        # Берём только ещё не отправленные (на случай ретрая воркера)
        deliveries = (
            BroadcastDelivery.objects.filter(job=job, status=DeliveryStatus.PENDING)
            .select_related("student")
        )

        for delivery in deliveries:
            student = delivery.student
            if student.telegram_chat_id is None:
                delivery.status = DeliveryStatus.NO_CHAT_ID
                delivery.save(update_fields=["status"])
                continue

            text = render_message(job.message_text, student)
            result = _send(student.telegram_chat_id, text, bot_token)

            delivery.status = result["status"]
            delivery.error_text = result.get("error", "")[:1000]
            if delivery.status == DeliveryStatus.SENT:
                delivery.sent_at = timezone.now()
            delivery.save(update_fields=["status", "error_text", "sent_at"])

            _sleep(_INTER_MESSAGE_PAUSE_SEC)

        job.status = BroadcastStatus.DONE
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at"])

    except Exception as exc:  # noqa: BLE001
        logger.exception("broadcast %s failed: %s", job.pk, exc)
        job.status = BroadcastStatus.FAILED
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at"])
        raise

    # После завершения — уведомляем менеджеров о студентах без подписки.
    # Ошибки тут НЕ должны валить сам Job (он уже DONE).
    try:
        notify_managers_about_unreachable(job)
    except Exception as exc:  # noqa: BLE001
        logger.exception("notify_managers failed for job %s: %s", job.pk, exc)


def collect_delivery_stats(job: BroadcastJob) -> dict[str, int]:
    """Сводка по доставкам для UI/JSON-эндпоинта."""
    qs = BroadcastDelivery.objects.filter(job=job)
    stats = {
        "total": qs.count(),
        "pending": qs.filter(status=DeliveryStatus.PENDING).count(),
        "sent": qs.filter(status=DeliveryStatus.SENT).count(),
        "blocked": qs.filter(status=DeliveryStatus.BLOCKED).count(),
        "no_chat_id": qs.filter(status=DeliveryStatus.NO_CHAT_ID).count(),
        "failed": qs.filter(status=DeliveryStatus.FAILED).count(),
    }
    return stats


# --- Служебный бот: уведомления о непривязанных и ручные отметки -----


def _format_unreachable_message(job: BroadcastJob, deliveries) -> str:
    """Собирает HTML-текст уведомления для служебного чата."""
    author = job.created_by.get_full_name() if job.created_by else "—"
    if job.created_by and not author:
        author = job.created_by.username

    lines = [
        f"<b>{deliveries.count()} студентов без подписки на бот</b>",
        f"<i>Рассылка #{job.pk} от {author}, {job.created_at:%d.%m.%Y %H:%M}</i>",
        "",
    ]
    for idx, delivery in enumerate(deliveries, start=1):
        s = delivery.student
        directions = ", ".join(d.name for d in s.directions.all()) or "—"
        lines.append(f"{idx}. <b>{s.full_name}</b> · {directions}")
        if s.telegram_username:
            lines.append(f"@{s.telegram_username}")
        elif s.phone:
            lines.append(f"нет telegram, тел. {s.phone}")
        else:
            lines.append("контакта нет")
        lines.append("")

    lines.append("———")
    lines.append("Текст рассылки:")
    lines.append(f"<i>{job.message_text}</i>")
    return "\n".join(lines)


def _build_manual_contact_keyboard(deliveries, job: BroadcastJob) -> list[list[dict]]:
    """Одна кнопка на строку — по одной на каждого студента."""
    return [
        [
            {
                "text": f"✓ Написал(а) {d.student.full_name}",
                "callback_data": f"manual_contact:{d.student_id}:{job.pk}",
            }
        ]
        for d in deliveries
    ]


def notify_managers_about_unreachable(
    job: BroadcastJob,
    *,
    _send=send_telegram_message,
) -> int:
    """Шлёт в служебный чат список студентов с NO_CHAT_ID и кнопки toggle.

    Возвращает количество студентов в уведомлении. Если их нет — 0 и
    ничего не шлёт.
    """
    deliveries = list(
        BroadcastDelivery.objects.filter(job=job, status=DeliveryStatus.NO_CHAT_ID)
        .select_related("student")
        .prefetch_related("student__directions")
        .order_by("student__full_name")
    )
    if not deliveries:
        return 0

    chat_id_raw = getattr(settings, "MANAGERS_CHAT_ID", "")
    bot_token = getattr(settings, "MANAGERS_BOT_TOKEN", "")
    if not chat_id_raw or not bot_token:
        logger.warning(
            "notify_managers: MANAGERS_CHAT_ID или MANAGERS_BOT_TOKEN пуст — "
            "уведомление о %d студентах не отправлено",
            len(deliveries),
        )
        return 0
    try:
        chat_id = int(chat_id_raw)
    except (TypeError, ValueError):
        logger.error("notify_managers: MANAGERS_CHAT_ID не число: %r", chat_id_raw)
        return 0

    text = _format_unreachable_message(job, BroadcastDelivery.objects.filter(pk__in=[d.pk for d in deliveries]))
    keyboard = _build_manual_contact_keyboard(deliveries, job)

    _send(chat_id, text, bot_token, inline_buttons=keyboard)
    return len(deliveries)


def register_manual_contact(
    student_id: int,
    broadcast_job_id: int | None,
    manager_telegram_id: int,
) -> tuple[bool, ManualContact | None]:
    """Toggle ручной отметки контакта.

    Если менеджер не привязан (нет User с таким telegram_chat_id) — возвращает
    (False, None). Если запись уже есть — удаляет (False, contact). Иначе
    создаёт новую (True, contact).
    """
    User = get_user_model()
    manager = User.objects.filter(telegram_chat_id=manager_telegram_id).first()
    if manager is None:
        return False, None

    existing = ManualContact.objects.filter(
        student_id=student_id,
        broadcast_job_id=broadcast_job_id,
        manager=manager,
    ).first()
    if existing is not None:
        existing.delete()
        logger.info(
            "manual_contact removed: student=%s, job=%s, manager=%s",
            student_id, broadcast_job_id, manager.pk,
        )
        return False, existing

    contact = ManualContact.objects.create(
        student_id=student_id,
        broadcast_job_id=broadcast_job_id,
        manager=manager,
    )
    logger.info(
        "manual_contact created: student=%s, job=%s, manager=%s",
        student_id, broadcast_job_id, manager.pk,
    )
    return True, contact


def create_broadcast_job(
    *,
    created_by,
    message_text: str,
    recipient_ids: Iterable[int],
) -> BroadcastJob:
    """Создаёт BroadcastJob c фиксированной аудиторией."""
    with transaction.atomic():
        job = BroadcastJob.objects.create(
            created_by=created_by,
            message_text=message_text,
            status=BroadcastStatus.PENDING,
        )
        students = list(Student.objects.filter(pk__in=list(recipient_ids)))
        job.recipients.set(students)
    return job
