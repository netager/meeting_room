from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    """Audit log read schema. Field names differ from ORM column names."""

    id: int
    action: str
    resource_type: Optional[str] = None   # mapped from AuditLog.target_table
    resource_id: Optional[str] = None     # mapped from AuditLog.target_id
    actor_emp_no: Optional[str] = None    # mapped from AuditLog.actor
    actor_name: Optional[str] = None      # resolved via Employee join
    detail: Optional[Any] = None          # Text field; JSON-parsed when possible
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=False)

    @classmethod
    def from_log(
        cls,
        log: Any,
        actor_name: Optional[str] = None,
    ) -> "AuditLogResponse":
        """Construct from an AuditLog ORM instance and optional actor_name."""
        # Try to parse detail as JSON; fall back to the raw string
        detail: Any = log.detail
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except (json.JSONDecodeError, ValueError):
                pass  # keep as plain string

        return cls(
            id=log.id,
            action=log.action,
            resource_type=log.target_table,
            resource_id=log.target_id,
            actor_emp_no=log.actor,
            actor_name=actor_name,
            detail=detail,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )


class PaginatedAuditLogs(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    size: int
    pages: int
