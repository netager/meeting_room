"""
Room backend tests.

Covers:
- 회의실 생성 → MeetingRoomHistory(CREATE) 기록
- CLOSED 상태에서 NORMAL로 변경 → admin만 가능, 일반 room_manager는 403
- 기존 SCHEDULED 회의가 있는 상태에서 회의실 임시폐쇄 → 200 + warnings 반환
- 연결된 회의가 있는 회의실 삭제 시도 → 409
- 집기 중복 등록 → 409
- 집기 수량 0 입력 → 422
- 다른 부서 회의실을 room_manager가 수정 → 403
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
from app.models.meeting import Meeting, MeetingAttendee
from app.models.room import MeetingRoom, MeetingRoomHistory, RoomEquipment, RoomEquipmentHistory


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


def _employee_headers(emp: Employee) -> dict:
    return {"Authorization": f"Bearer {_make_token(emp.emp_no)}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def dept_b(db: AsyncSession) -> Department:
    dept = Department(code="DEPTB", name="B부서")
    db.add(dept)
    await db.flush()
    return dept


@pytest.fixture
async def room_manager_emp(db: AsyncSession) -> Employee:
    emp = Employee(
        emp_no="RM0001",
        name="룸매니저",
        dept_code="TESTDEPT",
        password_hash="$test$Password1",
        status="ACTIVE",
        is_initial_password=False,
        is_room_manager=True,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()
    return emp


@pytest.fixture
async def room_manager_dept_b(db: AsyncSession, dept_b: Department) -> Employee:
    emp = Employee(
        emp_no="RM0002",
        name="B부서룸매니저",
        dept_code="DEPTB",
        password_hash="$test$Password1",
        status="ACTIVE",
        is_initial_password=False,
        is_room_manager=True,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()
    return emp


@pytest.fixture
async def test_room(db: AsyncSession) -> MeetingRoom:
    room = MeetingRoom(
        name="기본회의실",
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
        location="별관 2층",
        status="CLOSED",
        dept_code="TESTDEPT",
    )
    db.add(room)
    await db.flush()
    return room


@pytest.fixture
async def room_with_meeting(db: AsyncSession, active_employee: Employee) -> MeetingRoom:
    """SCHEDULED 회의가 있는 회의실."""
    room = MeetingRoom(
        name="예약있는회의실",
        location="본관 3층",
        status="NORMAL",
        dept_code="TESTDEPT",
    )
    db.add(room)
    await db.flush()

    meeting = Meeting(
        title="테스트회의",
        date=datetime.date.today() + datetime.timedelta(days=1),
        start_time=datetime.time(10, 0),
        end_time=datetime.time(11, 0),
        room_id=room.id,
        status="SCHEDULED",
        dept_code="TESTDEPT",
        created_by=active_employee.emp_no,
    )
    db.add(meeting)
    await db.flush()
    return room


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_create_room_records_history(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
):
    """회의실 생성 시 MeetingRoomHistory(CREATE) 기록."""
    resp = await client.post(
        "/api/meeting-rooms",
        json={"name": "히스토리테스트룸", "location": "1층", "dept_code": "TESTDEPT"},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    room_id = data["id"]

    result = await db.execute(
        select(MeetingRoomHistory).where(MeetingRoomHistory.target_id == room_id)
    )
    history = result.scalar_one_or_none()
    assert history is not None
    assert history.change_type == "CREATE"
    assert history.before_data is None
    assert history.after_data["name"] == "히스토리테스트룸"


async def test_closed_to_normal_admin_only(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    room_manager_emp: Employee,
    closed_room: MeetingRoom,
):
    """CLOSED → NORMAL: admin만 가능, room_manager는 403."""
    # room_manager 시도 → 403
    resp = await client.put(
        f"/api/meeting-rooms/{closed_room.id}",
        json={"status": "NORMAL"},
        headers=_employee_headers(room_manager_emp),
    )
    assert resp.status_code == 403

    # admin 시도 → 200
    resp = await client.put(
        f"/api/meeting-rooms/{closed_room.id}",
        json={"status": "NORMAL"},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    assert resp.json()["room"]["status"] == "NORMAL"


async def test_closed_to_temp_closed_admin_only(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    room_manager_emp: Employee,
    closed_room: MeetingRoom,
):
    """CLOSED → TEMP_CLOSED: admin만 가능."""
    resp = await client.put(
        f"/api/meeting-rooms/{closed_room.id}",
        json={"status": "TEMP_CLOSED"},
        headers=_employee_headers(room_manager_emp),
    )
    assert resp.status_code == 403

    resp = await client.put(
        f"/api/meeting-rooms/{closed_room.id}",
        json={"status": "TEMP_CLOSED"},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200


async def test_temp_close_room_with_scheduled_meetings_returns_warnings(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    room_with_meeting: MeetingRoom,
):
    """예정된 회의가 있는 회의실 임시폐쇄 → 200 + warnings 반환."""
    resp = await client.put(
        f"/api/meeting-rooms/{room_with_meeting.id}",
        json={"status": "TEMP_CLOSED"},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["room"]["status"] == "TEMP_CLOSED"
    assert len(data["warnings"]) > 0
    assert "1건" in data["warnings"][0]


async def test_close_room_with_no_meetings_no_warnings(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    test_room: MeetingRoom,
):
    """예정된 회의가 없는 회의실 폐쇄 → warnings 없음."""
    resp = await client.put(
        f"/api/meeting-rooms/{test_room.id}",
        json={"status": "CLOSED"},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["room"]["status"] == "CLOSED"
    assert data["warnings"] == []


async def test_delete_room_with_meeting_raises_409(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    room_with_meeting: MeetingRoom,
):
    """연결된 회의가 있는 회의실 삭제 → 409."""
    resp = await client.delete(
        f"/api/meeting-rooms/{room_with_meeting.id}",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


async def test_delete_room_with_equipment_raises_409(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    test_room: MeetingRoom,
):
    """집기가 있는 회의실 삭제 → 409 (집기 먼저 삭제 필요 메시지)."""
    eq = RoomEquipment(
        room_id=test_room.id,
        name="빔프로젝터",
        quantity=1,
        note=None,
    )
    db.add(eq)
    await db.flush()

    resp = await client.delete(
        f"/api/meeting-rooms/{test_room.id}",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 409
    assert "집기" in resp.json()["error"]["message"]


async def test_delete_room_success(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    test_room: MeetingRoom,
):
    """연결된 데이터 없는 회의실 삭제 → 200."""
    resp = await client.delete(
        f"/api/meeting-rooms/{test_room.id}",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200

    result = await db.execute(
        select(MeetingRoom).where(MeetingRoom.id == test_room.id)
    )
    assert result.scalar_one_or_none() is None


async def test_create_duplicate_equipment_raises_409(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    test_room: MeetingRoom,
):
    """집기 중복 등록 → 409."""
    resp = await client.post(
        f"/api/meeting-rooms/{test_room.id}/equipment",
        json={"name": "빔프로젝터", "quantity": 1},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 201

    resp = await client.post(
        f"/api/meeting-rooms/{test_room.id}/equipment",
        json={"name": "빔프로젝터", "quantity": 2},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


async def test_create_equipment_zero_quantity_raises_422(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    test_room: MeetingRoom,
):
    """집기 수량 0 입력 → 422."""
    resp = await client.post(
        f"/api/meeting-rooms/{test_room.id}/equipment",
        json={"name": "마이크", "quantity": 0},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 422


async def test_room_manager_different_dept_raises_403(
    client: AsyncClient,
    db: AsyncSession,
    room_manager_emp: Employee,
    dept_b: Department,
):
    """다른 부서 회의실을 room_manager가 생성 → 403."""
    resp = await client.post(
        "/api/meeting-rooms",
        json={"name": "타부서회의실", "location": "별관", "dept_code": "DEPTB"},
        headers=_employee_headers(room_manager_emp),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_room_manager_different_dept_update_raises_403(
    client: AsyncClient,
    db: AsyncSession,
    room_manager_emp: Employee,
    dept_b: Department,
    test_admin: AdminAccount,
):
    """다른 부서 회의실을 room_manager가 수정 → 403."""
    # admin이 B부서 회의실 생성
    resp = await client.post(
        "/api/meeting-rooms",
        json={"name": "B부서회의실", "location": "별관", "dept_code": "DEPTB"},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 201
    room_id = resp.json()["id"]

    # TESTDEPT room_manager가 수정 시도
    resp = await client.put(
        f"/api/meeting-rooms/{room_id}",
        json={"name": "이름변경"},
        headers=_employee_headers(room_manager_emp),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_create_equipment_records_history(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    test_room: MeetingRoom,
):
    """집기 생성 시 RoomEquipmentHistory(CREATE) 기록."""
    resp = await client.post(
        f"/api/meeting-rooms/{test_room.id}/equipment",
        json={"name": "화이트보드", "quantity": 2},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 201
    eq_id = resp.json()["id"]

    result = await db.execute(
        select(RoomEquipmentHistory).where(RoomEquipmentHistory.target_id == eq_id)
    )
    history = result.scalar_one_or_none()
    assert history is not None
    assert history.change_type == "CREATE"


async def test_get_room_detail_includes_equipment(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    test_room: MeetingRoom,
):
    """GET /api/meeting-rooms/{id} 응답에 집기 목록 포함."""
    eq = RoomEquipment(
        room_id=test_room.id,
        name="TV",
        quantity=1,
        note="65인치",
    )
    db.add(eq)
    await db.flush()

    resp = await client.get(
        f"/api/meeting-rooms/{test_room.id}",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["equipment"]) == 1
    assert data["equipment"][0]["name"] == "TV"


async def test_get_room_schedule_returns_sorted_slots(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    active_employee: Employee,
):
    """GET /api/meeting-rooms/{id}/schedule 응답이 시작시간 오름차순."""
    room = MeetingRoom(
        name="스케줄테스트룸",
        location="2층",
        status="NORMAL",
        dept_code="TESTDEPT",
    )
    db.add(room)
    await db.flush()

    today = datetime.date.today()
    for start, end in [(14, 15), (10, 11), (9, 10)]:
        m = Meeting(
            title=f"{start}시회의",
            date=today,
            start_time=datetime.time(start, 0),
            end_time=datetime.time(end, 0),
            room_id=room.id,
            status="SCHEDULED",
            dept_code="TESTDEPT",
            created_by=active_employee.emp_no,
        )
        db.add(m)
    await db.flush()

    resp = await client.get(
        f"/api/meeting-rooms/{room.id}/schedule",
        params={"date": today.isoformat()},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    slots = resp.json()
    assert len(slots) == 3
    times = [s["start_time"] for s in slots]
    assert times == sorted(times)


async def test_list_rooms_requires_auth(client: AsyncClient):
    """GET /api/meeting-rooms는 인증 필요."""
    resp = await client.get("/api/meeting-rooms")
    assert resp.status_code == 401


async def test_update_room_response_structure(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    test_room: MeetingRoom,
):
    """PUT /api/meeting-rooms/{id} 응답이 {"room": {...}, "warnings": [...]} 구조."""
    resp = await client.put(
        f"/api/meeting-rooms/{test_room.id}",
        json={"name": "이름수정"},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "room" in data
    assert "warnings" in data
    assert data["room"]["name"] == "이름수정"
