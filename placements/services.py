"""Сервисы для placements."""

from __future__ import annotations

import logging
from datetime import date

from django.utils import timezone

from .models import Placement, PlacementStatus

logger = logging.getLogger(__name__)


def change_placement_status(
    placement: Placement,
    new_status: str,
    user=None,
    *,
    started_at: date | None = None,
    planned_duration_days: int | None = None,
) -> Placement:
    """Единственный путь менять статус Placement.

    Явно проставляет status_changed_at=timezone.now(), чтобы счётчик «дней без
    движения» сбрасывался ТОЛЬКО при реальной смене статуса. При переводе в
    IN_PROGRESS — заполняет started_at (если не передан, берёт сегодня) и,
    опционально, planned_duration_days.
    """
    if new_status not in PlacementStatus.values:
        raise ValueError(f"Unknown placement status: {new_status!r}")

    old_status = placement.status
    placement.status = new_status
    placement.status_changed_at = timezone.now()

    if new_status == PlacementStatus.IN_PROGRESS:
        placement.started_at = started_at or placement.started_at or timezone.localdate()
        if planned_duration_days is not None:
            placement.planned_duration_days = planned_duration_days

    placement.save(
        update_fields=[
            "status",
            "status_changed_at",
            "started_at",
            "planned_duration_days",
            "updated_at",
        ]
    )

    logger.info(
        "placement %s: status %s → %s by %s",
        placement.pk,
        old_status,
        new_status,
        getattr(user, "username", "system"),
    )
    return placement
