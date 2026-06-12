"""Сервисы компаний."""

from __future__ import annotations

import logging

from django.utils import timezone

from .models import Company, HiringStatus

logger = logging.getLogger(__name__)


def change_company_status(company: Company, new_status: str, user=None) -> Company:
    """Единственный путь менять hiring_status. Проставляет status_changed_at."""
    if new_status not in HiringStatus.values:
        raise ValueError(f"Unknown hiring status: {new_status!r}")

    old = company.hiring_status
    company.hiring_status = new_status
    company.status_changed_at = timezone.now()
    company.save(update_fields=["hiring_status", "status_changed_at", "updated_at"])

    logger.info(
        "company %s: hiring_status %s → %s by %s",
        company.pk,
        old,
        new_status,
        getattr(user, "username", "system"),
    )
    return company
