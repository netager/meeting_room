"""Notification schemas."""

from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: str
    event_type: str
    message: str
    status: str  # PENDING | SENDING | SENT | FAILED
    created_at: datetime.datetime
    sent_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedNotifications(BaseModel):
    items: list[NotificationResponse]
    total: int
    page: int
    size: int
    pages: int
