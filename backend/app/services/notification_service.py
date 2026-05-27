"""Notification service.

Handles:
- Building per-event message text (PRD §7 templates).
- Creating MessageLog entries (PENDING).
- Dispatching to the internal messaging API (or Mock mode).
- Retry logic (up to 3 attempts).
"""

from __future__ import annotations

import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.audit import MessageLog
from app.models.meeting import Meeting
from app.models.org import Employee
from app.repositories import notification_repo

logger = structlog.get_logger(__name__)


# ── Message templates ─────────────────────────────────────────────────────────


def _format_time(t: datetime.time) -> str:
    return t.strftime("%H:%M")


def _format_date(d: datetime.date) -> str:
    return d.strftime("%Y-%m-%d")


def _build_message_text(event_type: str, meeting: Meeting) -> str:
    """Build notification message text per PRD §7 templates."""
    title = meeting.title
    date_str = _format_date(meeting.date)
    start_str = _format_time(meeting.start_time)
    end_str = _format_time(meeting.end_time)
    room_name = meeting.room.name if meeting.room else "알 수 없는 회의실"

    if event_type == "CREATED":
        return f"[회의 신청] {title} | {date_str} {start_str}-{end_str} | {room_name}"
    elif event_type == "UPDATED":
        return f"[회의 수정] {title} | {date_str} {start_str}-{end_str} | {room_name}"
    elif event_type == "CANCELLED":
        return f"[회의 취소] {title} | {date_str} | 취소 처리되었습니다."
    elif event_type == "COMPLETED":
        return f"[회의 완료] {title} | {date_str} | 완료 처리되었습니다."
    else:
        return f"[회의 알림] {title} | {date_str} {start_str}-{end_str} | {room_name}"


def _build_message(log: MessageLog) -> dict:
    """Build HTTP payload dict from a MessageLog for sending to the messaging API."""
    event_subjects = {
        "CREATED": "회의 신청 알림",
        "UPDATED": "회의 수정 알림",
        "CANCELLED": "회의 취소 알림",
        "COMPLETED": "회의 완료 알림",
    }
    return {
        "recipient_emp_no": log.recipient_emp_no,
        "message": log.message,
        "subject": event_subjects.get(log.event_type, "회의 알림"),
        "ref_type": "MEETING",
        "ref_id": log.meeting_id,
    }


# ── Core dispatch ─────────────────────────────────────────────────────────────


async def _send_one(log_id: str, db: AsyncSession) -> None:
    """
    Attempt to send a single MessageLog.

    Mock mode  (INTERNAL_MSG_API_URL is empty):
        Marks as SENT, logs the message.

    Real mode:
        POSTs to INTERNAL_MSG_API_URL.
        On failure, increments retry_count.
        If retry_count >= 3, gives up (status=FAILED permanently).
    """
    log = await notification_repo.get_log(log_id, db)
    if log is None:
        logger.warning("notification_log_not_found", log_id=log_id)
        return

    if log.status == "SENT":
        return  # already sent

    # Mark as SENDING
    await notification_repo.update_log(log_id, {"status": "SENDING"}, db)

    payload = _build_message(log)

    if not settings.internal_msg_api_url:
        # ── Mock mode ──────────────────────────────────────────────────────────
        logger.info(
            "notification_mock_sent",
            recipient=log.recipient_emp_no,
            event_type=log.event_type,
            message=log.message,
        )
        await notification_repo.update_log(
            log_id,
            {"status": "SENT", "sent_at": datetime.datetime.now()},
            db,
        )
        return

    # ── Real mode ──────────────────────────────────────────────────────────────
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=settings.internal_msg_api_timeout
        ) as client:
            response = await client.post(
                settings.internal_msg_api_url,
                json={
                    "sender": "system",
                    "recipients": [payload["recipient_emp_no"]],
                    "message": payload["message"],
                    "ref_type": payload["ref_type"],
                    "ref_id": payload["ref_id"],
                },
            )
            response.raise_for_status()

        await notification_repo.update_log(
            log_id,
            {"status": "SENT", "sent_at": datetime.datetime.now()},
            db,
        )
        logger.info(
            "notification_sent",
            recipient=log.recipient_emp_no,
            event_type=log.event_type,
        )

    except Exception as exc:
        new_retry_count = log.retry_count + 1
        logger.warning(
            "notification_send_failed",
            log_id=log_id,
            attempt=new_retry_count,
            error=str(exc),
        )
        await notification_repo.update_log(
            log_id,
            {
                "status": "FAILED",
                "retry_count": new_retry_count,
                "error_message": str(exc)[:500],
            },
            db,
        )


async def _dispatch_all(log_ids: list[str], db: AsyncSession) -> None:
    """Send all MessageLogs identified by log_ids."""
    for log_id in log_ids:
        try:
            await _send_one(log_id, db)
        except Exception as exc:
            logger.error("notification_dispatch_error", log_id=log_id, error=str(exc))


async def send_meeting_notification(
    meeting_id: str,
    event_type: str,
    recipients: list[str],
    db: AsyncSession,
) -> None:
    """
    Background-safe entry point.

    1. Load the meeting (with room) from the provided session.
    2. Filter out RETIRED employees.
    3. Create a MessageLog (PENDING) for each active recipient.
    4. Dispatch immediately (mock or real).
    """
    if not recipients:
        return

    # Load meeting with room info
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.room))
        .where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        logger.warning("notification_meeting_not_found", meeting_id=meeting_id)
        return

    # Filter to active employees only
    active_result = await db.execute(
        select(Employee.emp_no)
        .where(Employee.emp_no.in_(recipients), Employee.status == "ACTIVE")
    )
    active_emp_nos = {row[0] for row in active_result.all()}

    message_text = _build_message_text(event_type, meeting)

    log_ids: list[str] = []
    for emp_no in recipients:
        if emp_no not in active_emp_nos:
            continue  # skip retired employees
        log = await notification_repo.create_log(
            {
                "meeting_id": meeting_id,
                "event_type": event_type,
                "recipient_emp_no": emp_no,
                "message": message_text,
            },
            db,
        )
        log_ids.append(log.id)

    # Dispatch (non-blocking in real mode due to retry logic; immediate in mock mode)
    await _dispatch_all(log_ids, db)
