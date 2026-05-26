"""
Meeting backend tests.

Covers:
- 회의 생성 → SCHEDULED 상태, MeetingHistory(CREATE) 기록, created_by가 자동으로 참석자에 포함
- 동일 회의실 동일 시간 겹치는 예약 → 409 ROOM_BOOKING_CONFLICT
- 시간이 연속 붙어있을 때 (A: 09:00~10:00, B: 10:00~11:00) → 충돌 없음
- 주최자가 아닌 사람이 회의 수정 → 403
- admin이 다른 사람 회의 수정 → 성공
- SCHEDULED 회의 취소 → CANCELLED 상태 (재취소 불가 → 422)
- CANCELLED 회의 수정 시도 → 422
- 주최자(created_by)를 참석자에서 삭제 → 422
- NORMAL 상태가 아닌 회의실에 예약 → 422
- ?my=true 필터: 내가 주최하거나 참석자인 회의만 반환
"""

from __future__ import annotations

import datetime

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AdminAccount, Department, Employee
from app.models.meeting import Meeting, MeetingAttendee, MeetingHistory
from app.models.room import MeetingRoom


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


def _admin_headers(admin: AdminAccount) -> dict:
    return {"Authorization": f"Bearer {_make_token('admin', is_admin=True)}"}


def _emp_headers(emp: Employee) -> dict:
    return {"Authorization": f"Bearer {_make_token(emp.emp_no)}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def normal_room(db: AsyncSession) -> MeetingRoom:
    room = MeetingRoom(
        name="테스트회의실",
        location="본관 1층",
        status="NORMAL",
        dept_code="TESTDEPT",
    )
    db.add(room)
    await db.flush()
    return room


@pytest.fixture
async def closed_room(db: AsyncSession) -> MeetingRoom:
    room = MeetingRoom(
        name="폐쇄회의실",
        location="본관 2층",
        status="CLOSED",
        dept_code="TESTDEPT",
    )
    db.add(room)
    await db.flush()
    return room


@pytest.fixture
async def emp_creator(db: AsyncSession) -> Employee:
    emp = Employee(
        emp_no="C00001",
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
async def emp_other(db: AsyncSession) -> Employee:
    """다른 직원 (같은 부서, 비주최자)."""
    emp = Employee(
        emp_no="O00001",
        name="다른직원",
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
async def scheduled_meeting(
    db: AsyncSession, normal_room: MeetingRoom, emp_creator: Employee
) -> Meeting:
    meeting = Meeting(
        title="예정회의",
        date=datetime.date.today() + datetime.timedelta(days=1),
        start_time=datetime.time(14, 0),
        end_time=datetime.time(15, 0),
        room_id=normal_room.id,
        status="SCHEDULED",
        dept_code="TESTDEPT",
        created_by=emp_creator.emp_no,
    )
    db.add(meeting)
    await db.flush()
    db.add(MeetingAttendee(meeting_id=meeting.id, emp_no=emp_creator.emp_no))
    await db.flush()
    return meeting


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_create_meeting_scheduled_with_history(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    normal_room: MeetingRoom,
    emp_creator: Employee,
):
    """회의 생성 → SCHEDULED 상태, MeetingHistory(CREATE), created_by 자동 참석자."""
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    resp = await client.post(
        "/api/meetings",
        json={
            "title": "신규회의",
            "room_id": normal_room.id,
            "meeting_date": tomorrow,
            "start_time": "10:00:00",
            "end_time": "11:00:00",
        },
        headers=_emp_headers(emp_creator),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "SCHEDULED"
    assert data["title"] == "신규회의"

    # 주최자가 자동으로 참석자에 포함되어 있어야 함
    attendee_emp_nos = [a["emp_no"] for a in data["attendees"]]
    assert emp_creator.emp_no in attendee_emp_nos

    # MeetingHistory(CREATE) 기록 확인
    result = await db.execute(
        select(MeetingHistory).where(MeetingHistory.target_id == data["id"])
    )
    history = result.scalar_one_or_none()
    assert history is not None
    assert history.change_type == "CREATE"
    assert history.before_data is None
    assert history.after_data["title"] == "신규회의"


async def test_create_meeting_room_booking_conflict(
    client: AsyncClient,
    db: AsyncSession,
    normal_room: MeetingRoom,
    emp_creator: Employee,
    emp_other: Employee,
    scheduled_meeting: Meeting,
):
    """동일 회의실 동일 시간 겹치는 예약 → 409 ROOM_BOOKING_CONFLICT."""
    # scheduled_meeting: 내일 14:00~15:00
    meeting_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    resp = await client.post(
        "/api/meetings",
        json={
            "title": "충돌회의",
            "room_id": normal_room.id,
            "meeting_date": meeting_date,
            "start_time": "14:30:00",
            "end_time": "15:30:00",
        },
        headers=_emp_headers(emp_other),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ROOM_BOOKING_CONFLICT"


async def test_create_meeting_no_conflict_adjacent_times(
    client: AsyncClient,
    db: AsyncSession,
    normal_room: MeetingRoom,
    emp_creator: Employee,
    emp_other: Employee,
    scheduled_meeting: Meeting,
):
    """시간이 연속 붙어있을 때 (A: 14:00~15:00, B: 15:00~16:00) → 충돌 없음."""
    # scheduled_meeting: 내일 14:00~15:00
    meeting_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    resp = await client.post(
        "/api/meetings",
        json={
            "title": "연속회의",
            "room_id": normal_room.id,
            "meeting_date": meeting_date,
            "start_time": "15:00:00",
            "end_time": "16:00:00",
        },
        headers=_emp_headers(emp_other),
    )
    assert resp.status_code == 201, resp.text


async def test_update_meeting_non_creator_raises_403(
    client: AsyncClient,
    db: AsyncSession,
    emp_other: Employee,
    scheduled_meeting: Meeting,
):
    """주최자가 아닌 사람이 회의 수정 → 403."""
    resp = await client.put(
        f"/api/meetings/{scheduled_meeting.id}",
        json={"title": "수정된제목"},
        headers=_emp_headers(emp_other),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_update_meeting_admin_succeeds(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    scheduled_meeting: Meeting,
):
    """admin이 다른 사람 회의 수정 → 성공."""
    resp = await client.put(
        f"/api/meetings/{scheduled_meeting.id}",
        json={"title": "admin이수정"},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "admin이수정"


async def test_cancel_meeting_changes_status_to_cancelled(
    client: AsyncClient,
    db: AsyncSession,
    emp_creator: Employee,
    scheduled_meeting: Meeting,
):
    """SCHEDULED 회의 취소 → CANCELLED 상태."""
    resp = await client.delete(
        f"/api/meetings/{scheduled_meeting.id}",
        headers=_emp_headers(emp_creator),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"

    # DB에서 실제 삭제되지 않았는지 확인
    result = await db.execute(
        select(Meeting).where(Meeting.id == scheduled_meeting.id)
    )
    m = result.scalar_one_or_none()
    assert m is not None
    assert m.status == "CANCELLED"


async def test_cancel_already_cancelled_meeting_raises_422(
    client: AsyncClient,
    db: AsyncSession,
    emp_creator: Employee,
    scheduled_meeting: Meeting,
):
    """이미 취소된 회의를 재취소 → 422."""
    # 먼저 취소
    await client.delete(
        f"/api/meetings/{scheduled_meeting.id}",
        headers=_emp_headers(emp_creator),
    )
    # 재취소 시도
    resp = await client.delete(
        f"/api/meetings/{scheduled_meeting.id}",
        headers=_emp_headers(emp_creator),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "MEETING_ALREADY_CLOSED"


async def test_update_cancelled_meeting_raises_422(
    client: AsyncClient,
    db: AsyncSession,
    emp_creator: Employee,
    scheduled_meeting: Meeting,
):
    """CANCELLED 회의 수정 시도 → 422."""
    # 취소
    await client.delete(
        f"/api/meetings/{scheduled_meeting.id}",
        headers=_emp_headers(emp_creator),
    )
    # 수정 시도
    resp = await client.put(
        f"/api/meetings/{scheduled_meeting.id}",
        json={"title": "수정불가"},
        headers=_emp_headers(emp_creator),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "MEETING_ALREADY_CLOSED"


async def test_remove_creator_from_attendees_raises_422(
    client: AsyncClient,
    db: AsyncSession,
    emp_creator: Employee,
    scheduled_meeting: Meeting,
):
    """주최자(created_by)를 참석자에서 삭제 → 422."""
    resp = await client.delete(
        f"/api/meetings/{scheduled_meeting.id}/attendees/{emp_creator.emp_no}",
        headers=_emp_headers(emp_creator),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


async def test_create_meeting_non_normal_room_raises_409(
    client: AsyncClient,
    db: AsyncSession,
    closed_room: MeetingRoom,
    emp_creator: Employee,
):
    """NORMAL 상태가 아닌 회의실에 예약 → 409 ROOM_NOT_AVAILABLE."""
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    resp = await client.post(
        "/api/meetings",
        json={
            "title": "폐쇄회의실예약",
            "room_id": closed_room.id,
            "meeting_date": tomorrow,
            "start_time": "10:00:00",
            "end_time": "11:00:00",
        },
        headers=_emp_headers(emp_creator),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ROOM_NOT_AVAILABLE"


async def test_list_my_meetings_filter(
    client: AsyncClient,
    db: AsyncSession,
    normal_room: MeetingRoom,
    emp_creator: Employee,
    emp_other: Employee,
    test_admin: AdminAccount,
):
    """?my=true 필터: 내가 주최하거나 참석자인 회의만 반환."""
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)

    # emp_creator가 주최하는 회의
    m1 = Meeting(
        title="creator주최회의",
        date=tomorrow,
        start_time=datetime.time(9, 0),
        end_time=datetime.time(10, 0),
        room_id=normal_room.id,
        status="SCHEDULED",
        dept_code="TESTDEPT",
        created_by=emp_creator.emp_no,
    )
    db.add(m1)
    await db.flush()
    db.add(MeetingAttendee(meeting_id=m1.id, emp_no=emp_creator.emp_no))

    # emp_other가 주최하고 emp_creator가 참석자인 회의
    m2 = Meeting(
        title="other주최creator참석회의",
        date=tomorrow,
        start_time=datetime.time(11, 0),
        end_time=datetime.time(12, 0),
        room_id=normal_room.id,
        status="SCHEDULED",
        dept_code="TESTDEPT",
        created_by=emp_other.emp_no,
    )
    db.add(m2)
    await db.flush()
    db.add(MeetingAttendee(meeting_id=m2.id, emp_no=emp_other.emp_no))
    db.add(MeetingAttendee(meeting_id=m2.id, emp_no=emp_creator.emp_no))

    # emp_other만의 회의 (emp_creator와 무관)
    m3 = Meeting(
        title="other만의회의",
        date=tomorrow,
        start_time=datetime.time(14, 0),
        end_time=datetime.time(15, 0),
        room_id=normal_room.id,
        status="SCHEDULED",
        dept_code="TESTDEPT",
        created_by=emp_other.emp_no,
    )
    db.add(m3)
    await db.flush()
    db.add(MeetingAttendee(meeting_id=m3.id, emp_no=emp_other.emp_no))
    await db.flush()

    # emp_creator로 ?my=true 조회
    resp = await client.get(
        "/api/meetings",
        params={"my": "true"},
        headers=_emp_headers(emp_creator),
    )
    assert resp.status_code == 200
    data = resp.json()
    returned_ids = {item["id"] for item in data["items"]}

    assert m1.id in returned_ids, "주최자 회의가 포함되어야 함"
    assert m2.id in returned_ids, "참석자 회의가 포함되어야 함"
    assert m3.id not in returned_ids, "무관한 회의는 포함되면 안 됨"


async def test_delete_route_is_soft_cancel_not_hard_delete(
    client: AsyncClient,
    db: AsyncSession,
    emp_creator: Employee,
    scheduled_meeting: Meeting,
):
    """DELETE /api/meetings/{id}는 실제 DB 삭제가 아닌 CANCELLED 처리."""
    resp = await client.delete(
        f"/api/meetings/{scheduled_meeting.id}",
        headers=_emp_headers(emp_creator),
    )
    assert resp.status_code == 200

    # DB row가 남아있어야 함
    result = await db.execute(select(Meeting).where(Meeting.id == scheduled_meeting.id))
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.status == "CANCELLED"


async def test_add_attendee_duplicate_raises_409(
    client: AsyncClient,
    db: AsyncSession,
    emp_creator: Employee,
    emp_other: Employee,
    scheduled_meeting: Meeting,
):
    """이미 참석자인 직원을 다시 추가 → 409."""
    # emp_other를 참석자로 추가
    await client.post(
        f"/api/meetings/{scheduled_meeting.id}/attendees",
        json={"emp_no": emp_other.emp_no},
        headers=_emp_headers(emp_creator),
    )
    # 다시 추가
    resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/attendees",
        json={"emp_no": emp_other.emp_no},
        headers=_emp_headers(emp_creator),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


async def test_complete_meeting_admin_only(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    emp_creator: Employee,
    scheduled_meeting: Meeting,
):
    """완료 처리는 admin만 가능 (일반 직원은 403)."""
    # 일반 직원 시도 → 403
    resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/complete",
        headers=_emp_headers(emp_creator),
    )
    assert resp.status_code == 403

    # admin 시도 → 200
    resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/complete",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"
