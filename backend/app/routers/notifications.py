"""Notification router — /api/notifications."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import require_active_user
from app.models import Employee
from app.repositories import notification_repo
from app.schemas.notification import NotificationResponse, PaginatedNotifications

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=PaginatedNotifications)
async def get_my_notifications(
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_active_user),
):
    """Return the current user's notification list (newest first)."""
    size = min(size, 100)

    # Admin account has no emp_no — return empty list
    if not isinstance(current_user, Employee):
        return PaginatedNotifications(items=[], total=0, page=page, size=size, pages=0)

    logs, total = await notification_repo.get_my_notifications(
        current_user.emp_no, db, page=page, size=size
    )
    pages = math.ceil(total / size) if total > 0 else 0
    return PaginatedNotifications(
        items=[NotificationResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
