"""Notification (MessageLog) repository."""

from __future__ import annotations


from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import MessageLog


async def create_log(data: dict, db: AsyncSession) -> MessageLog:
    """Insert a new MessageLog with status=PENDING."""
    log = MessageLog(
        meeting_id=data.get("meeting_id"),
        event_type=data["event_type"],
        recipient_emp_no=data["recipient_emp_no"],
        message=data["message"],
        status="PENDING",
    )
    db.add(log)
    await db.flush()
    return log


async def get_log(log_id: str, db: AsyncSession) -> MessageLog | None:
    result = await db.execute(select(MessageLog).where(MessageLog.id == log_id))
    return result.scalar_one_or_none()


async def update_log(log_id: str, data: dict, db: AsyncSession) -> MessageLog:
    """Update MessageLog fields: status, retry_count, sent_at, error_message."""
    log = await get_log(log_id, db)
    if log is None:
        raise ValueError(f"MessageLog not found: {log_id}")
    for key, value in data.items():
        setattr(log, key, value)
    await db.flush()
    return log


async def get_my_notifications(
    emp_no: str,
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
) -> tuple[list[MessageLog], int]:
    """Return paginated MessageLog entries where recipient_emp_no=emp_no, newest first."""
    base_q = select(MessageLog).where(MessageLog.recipient_emp_no == emp_no)
    total_result = await db.execute(
        select(func.count()).select_from(base_q.subquery())
    )
    total = total_result.scalar_one()

    result = await db.execute(
        base_q.order_by(desc(MessageLog.created_at))
        .offset((page - 1) * size)
        .limit(size)
    )
    logs = list(result.scalars().all())
    return logs, total


async def get_pending_logs(db: AsyncSession) -> list[MessageLog]:
    """Return logs that need sending or retrying (PENDING or FAILED with retry_count < 3)."""
    result = await db.execute(
        select(MessageLog)
        .where(
            or_(
                MessageLog.status == "PENDING",
                (MessageLog.status == "FAILED") & (MessageLog.retry_count < 3),
            )
        )
        .order_by(MessageLog.created_at)
    )
    return list(result.scalars().all())
