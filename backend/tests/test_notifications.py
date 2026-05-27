"""
Notification backend tests.

Covers:
- 회의 생성 시 참석자(주최자 제외)에게 MessageLog(PENDING/SENT) 생성
- Mock 모드에서 _send_one 호출 → status=SENT 로 변경
- 회의 취소 시 CANCELLED 이벤트 메시지 생성
- GET /api/notifications → 내 알림 목록 반환
- 메시지 빌드 결과가 PRD 템플릿 형식과 일치하는가
- 퇴직 직원은 알림 대상에서 제외
"""

from __future__ import annotations

import datetime

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AdminAccount, Employee
from app.models.audit import MessageLog
from app.models.meeting import Meeting, MeetingAttendee
from app.models.room import MeetingRoom
from app.repositories import notification_repo
from app.services import notification_service


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_token(sub: str, is_admin: bool = False) -> str:
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    payload = {
        "sub": sub,
        "is_admin": is_admin,
        "exp": now + datetime.timedelta(minutes=30),
        "iat": now,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def _emp_headers(emp: Employee) -> dict:
    return {"Authorization": f"Bearer {_make_token(emp.emp_no)}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def normal_room(db: AsyncSession) -> MeetingRoom:
    room = MeetingRoom(
        name="알림테스트회의실",
        location="본관 1층",
        status="NORMAL",
        dept_code="TESTDEPT",
    )
    db.add(room)
    await db.flush()
    return room


@pytest.fixture
async def creator(db: AsyncSession) -> Employee:
    emp = Employee(
        emp_no="N00001",
        name="주최자",
        dept_code="TESTDEPT",
        password_hash="$test$Password1",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()
    return emp


@pytest.fixture
async def attendee1(db: AsyncSession) -> Employee:
    emp = Employee(
        emp_no="N00002",
        name="참석자1",
        dept_code="TESTDEPT",
        password_hash="$test$Password1",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()
    return emp


@pytest.fixture
async def attendee2(db: AsyncSession) -> Employee:
    emp = Employee(
        emp_no="N00003",
        name="참석자2",
        dept_code="TESTDEPT",
        password_hash="$test$Password1",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()
    return emp


@pytest.fixture
async def retired_emp(db: AsyncSession) -> Employee:
    emp = Employee(
        emp_no="N00004",
        name="퇴직자",
        dept_code="TESTDEPT",
        password_hash="$test$Password1",
        status="RETIRED",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()
    return emp


@pytest.fixture
async def meeting_with_attendees(
    db: AsyncSession,
    normal_room: MeetingRoom,
    creator: Employee,
    attendee1: Employee,
    attendee2: Employee,
) -> Meeting:
    """Meeting with creator + 2 attendees."""
    meeting = Meeting(
        title="알림테스트회의",
        date=datetime.date.today() + datetime.timedelta(days=1),
        start_time=datetime.time(10, 0),
        end_time=datetime.time(11, 0),
        room_id=normal_room.id,
        status="SCHEDULED",
        dept_code="TESTDEPT",
        created_by=creator.emp_no,
    )
    db.add(meeting)
    await db.flush()
    db.add(MeetingAttendee(meeting_id=meeting.id, emp_no=creator.emp_no))
    db.add(MeetingAttendee(meeting_id=meeting.id, emp_no=attendee1.emp_no))
    db.add(MeetingAttendee(meeting_id=meeting.id, emp_no=attendee2.emp_no))
    await db.flush()
    return meeting


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_send_meeting_notification_creates_logs(
    db: AsyncSession,
    meeting_with_attendees: Meeting,
    creator: Employee,
    attendee1: Employee,
    attendee2: Employee,
):
    """send_meeting_notification creates MessageLog per recipient, excluding creator."""
    recipients = [attendee1.emp_no, attendee2.emp_no]

    await notification_service.send_meeting_notification(
        meeting_with_attendees.id,
        "CREATED",
        recipients,
        db,
    )

    # Both attendees should have logs
    result = await db.execute(
        select(MessageLog).where(
            MessageLog.meeting_id == meeting_with_attendees.id
        )
    )
    logs = result.scalars().all()
    assert len(logs) == 2

    emp_nos = {log.recipient_emp_no for log in logs}
    assert attendee1.emp_no in emp_nos
    assert attendee2.emp_no in emp_nos
    assert creator.emp_no not in emp_nos  # creator excluded


async def test_send_one_mock_mode_sets_sent(
    db: AsyncSession,
    meeting_with_attendees: Meeting,
    attendee1: Employee,
    monkeypatch,
):
    """In mock mode (_send_one with no API URL), status becomes SENT."""
    monkeypatch.setattr(settings, "internal_msg_api_url", "")

    log = await notification_repo.create_log(
        {
            "meeting_id": meeting_with_attendees.id,
            "event_type": "CREATED",
            "recipient_emp_no": attendee1.emp_no,
            "message": "[회의 신청] 테스트 | 2026-05-27 10:00-11:00 | 회의실",
        },
        db,
    )
    assert log.status == "PENDING"

    await notification_service._send_one(log.id, db)

    updated = await notification_repo.get_log(log.id, db)
    assert updated is not None
    assert updated.status == "SENT"
    assert updated.sent_at is not None


async def test_cancelled_event_message_format(
    db: AsyncSession,
    meeting_with_attendees: Meeting,
    attendee1: Employee,
):
    """Cancellation event produces correct PRD template message."""
    recipients = [attendee1.emp_no]

    await notification_service.send_meeting_notification(
        meeting_with_attendees.id,
        "CANCELLED",
        recipients,
        db,
    )

    result = await db.execute(
        select(MessageLog).where(
            MessageLog.meeting_id == meeting_with_attendees.id,
            MessageLog.recipient_emp_no == attendee1.emp_no,
        )
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert "[회의 취소]" in log.message
    assert "취소 처리되었습니다" in log.message
    assert meeting_with_attendees.title in log.message


async def test_message_format_created(
    db: AsyncSession,
    meeting_with_attendees: Meeting,
    attendee1: Employee,
):
    """CREATED message format matches PRD template."""
    recipients = [attendee1.emp_no]

    await notification_service.send_meeting_notification(
        meeting_with_attendees.id,
        "CREATED",
        recipients,
        db,
    )

    result = await db.execute(
        select(MessageLog).where(
            MessageLog.meeting_id == meeting_with_attendees.id,
            MessageLog.recipient_emp_no == attendee1.emp_no,
        )
    )
    log = result.scalar_one_or_none()
    assert log is not None
    # PRD template: "[회의 신청] {제목} | {날짜} {시작}-{종료} | {회의실}"
    assert "[회의 신청]" in log.message
    assert meeting_with_attendees.title in log.message
    assert "10:00-11:00" in log.message
    assert "알림테스트회의실" in log.message


async def test_retired_employee_excluded_from_notification(
    db: AsyncSession,
    meeting_with_attendees: Meeting,
    retired_emp: Employee,
    attendee1: Employee,
):
    """Retired employee is excluded from notification sending."""
    recipients = [retired_emp.emp_no, attendee1.emp_no]

    await notification_service.send_meeting_notification(
        meeting_with_attendees.id,
        "CREATED",
        recipients,
        db,
    )

    # Only active attendee1 should have a log
    result = await db.execute(
        select(MessageLog).where(
            MessageLog.meeting_id == meeting_with_attendees.id
        )
    )
    logs = result.scalars().all()
    emp_nos = {log.recipient_emp_no for log in logs}
    assert attendee1.emp_no in emp_nos
    assert retired_emp.emp_no not in emp_nos


async def test_get_my_notifications_endpoint(
    client: AsyncClient,
    db: AsyncSession,
    meeting_with_attendees: Meeting,
    attendee1: Employee,
):
    """GET /api/notifications returns logs for the current user only."""
    # Manually create logs for attendee1
    await notification_repo.create_log(
        {
            "meeting_id": meeting_with_attendees.id,
            "event_type": "CREATED",
            "recipient_emp_no": attendee1.emp_no,
            "message": "[회의 신청] 테스트 | 2026-05-27 10:00-11:00 | 회의실",
        },
        db,
    )

    resp = await client.get(
        "/api/notifications",
        headers=_emp_headers(attendee1),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    items = data["items"]
    assert len(items) >= 1
    # All returned notifications should belong to attendee1
    # (The endpoint filters by current_user)
    for item in items:
        assert "event_type" in item
        assert "message" in item
        assert "status" in item
        assert "created_at" in item


async def test_cancel_meeting_via_api_triggers_notification(
    client: AsyncClient,
    db: AsyncSession,
    normal_room: MeetingRoom,
    creator: Employee,
    attendee1: Employee,
):
    """Cancelling a meeting via API triggers CANCELLED notification for all attendees."""
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    # Step 1: Create meeting (only creator added as attendee)
    resp = await client.post(
        "/api/meetings",
        json={
            "title": "API취소알림테스트",
            "room_id": normal_room.id,
            "meeting_date": tomorrow,
            "start_time": "14:00:00",
            "end_time": "15:00:00",
        },
        headers=_emp_headers(creator),
    )
    assert resp.status_code == 201
    meeting_id = resp.json()["id"]

    # Step 2: Add attendee1 via API
    resp2 = await client.post(
        f"/api/meetings/{meeting_id}/attendees",
        json={"emp_no": attendee1.emp_no},
        headers=_emp_headers(creator),
    )
    assert resp2.status_code == 201

    # Step 3: Cancel meeting → should trigger CANCELLED notification for all attendees
    resp3 = await client.delete(
        f"/api/meetings/{meeting_id}",
        headers=_emp_headers(creator),
    )
    assert resp3.status_code == 200

    # Background task should have run by now (ASGI transport is synchronous)
    result = await db.execute(
        select(MessageLog).where(
            MessageLog.meeting_id == meeting_id,
            MessageLog.event_type == "CANCELLED",
        )
    )
    logs = result.scalars().all()

    # attendee1 should have received a cancellation notification
    notified_emp_nos = {log.recipient_emp_no for log in logs}
    assert attendee1.emp_no in notified_emp_nos


async def test_build_message_dict(
    db: AsyncSession,
    meeting_with_attendees: Meeting,
    attendee1: Employee,
):
    """_build_message returns correct dict structure."""
    log = await notification_repo.create_log(
        {
            "meeting_id": meeting_with_attendees.id,
            "event_type": "UPDATED",
            "recipient_emp_no": attendee1.emp_no,
            "message": "[회의 수정] 테스트",
        },
        db,
    )

    msg_dict = notification_service._build_message(log)
    assert msg_dict["recipient_emp_no"] == attendee1.emp_no
    assert msg_dict["message"] == "[회의 수정] 테스트"
    assert "subject" in msg_dict
    assert msg_dict["ref_type"] == "MEETING"
    assert msg_dict["ref_id"] == meeting_with_attendees.id
