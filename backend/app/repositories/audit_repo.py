from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.org import Employee


async def get_audit_logs(
    db: AsyncSession,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    actor_emp_no: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[tuple[AuditLog, Optional[str]]], int]:
    """
    Returns a list of (AuditLog, actor_name) tuples and total count.
    actor_name is the Employee.name for emp_no actors, or None for 'admin'.
    Ordered by created_at DESC.
    """
    # Base query with outer join to Employee for actor_name
    q = (
        select(AuditLog, Employee.name.label("actor_name"))
        .outerjoin(Employee, AuditLog.actor == Employee.emp_no)
    )

    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(AuditLog.target_table == resource_type)
    if actor_emp_no:
        filters.append(AuditLog.actor == actor_emp_no)
    if date_from:
        filters.append(func.date(AuditLog.created_at) >= date_from)
    if date_to:
        filters.append(func.date(AuditLog.created_at) <= date_to)

    if filters:
        q = q.where(and_(*filters))

    # Count query (count AuditLog rows only)
    count_q = select(func.count(AuditLog.id))
    if filters:
        count_q = count_q.where(and_(*filters))
    total = await db.scalar(count_q)

    q = q.order_by(desc(AuditLog.created_at)).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    rows = result.all()

    items = [(row[0], row[1]) for row in rows]
    return items, total or 0


async def get_audit_log(
    log_id: int, db: AsyncSession
) -> tuple[AuditLog, Optional[str]] | None:
    """
    Returns (AuditLog, actor_name) or None if not found.
    """
    q = (
        select(AuditLog, Employee.name.label("actor_name"))
        .outerjoin(Employee, AuditLog.actor == Employee.emp_no)
        .where(AuditLog.id == log_id)
    )
    result = await db.execute(q)
    row = result.one_or_none()
    if row is None:
        return None
    return (row[0], row[1])
