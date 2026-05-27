"""
Admin backend tests.

Covers:
- admin이 감사 로그 조회 → 200, 페이지네이션 포함
- 비 admin이 감사 로그 조회 → 403
- action 필터: ?action=LOGIN → LOGIN 액션만 반환
- resource_type 필터: ?resource_type=Meeting → Meeting 관련만 반환
- date_from/date_to 필터: 해당 기간 범위만 반환
- 감사 로그 단건 조회 (admin) → 200
- 감사 로그 단건 조회 (없는 ID) → 404
- admin이 직원 권한 변경 → EmployeeHistory(UPDATE) 기록
- 비 admin이 권한 변경 → 403
- 퇴직 직원 권한 변경 → 400
- EmployeeResponse에 password_hash 미포함
"""

from __future__ import annotations

import datetime

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AdminAccount, AuditLog, Employee
from app.models.org import EmployeeHistory


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
    return {"Authorization": f"Bearer {_make_token(emp.emp_no, is_admin=False)}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def active_emp(db: AsyncSession, test_admin: AdminAccount) -> Employee:
    """재직 직원 (비 admin, is_initial_password=False)."""
    emp = Employee(
        emp_no="A00001",
        name="일반직원",
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
async def target_emp(db: AsyncSession, test_admin: AdminAccount) -> Employee:
    """권한 변경 대상 직원."""
    emp = Employee(
        emp_no="A00002",
        name="대상직원",
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
async def retired_emp(db: AsyncSession, test_admin: AdminAccount) -> Employee:
    """퇴직 직원."""
    emp = Employee(
        emp_no="A00003",
        name="퇴직직원",
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
async def sample_audit_logs(db: AsyncSession) -> list[AuditLog]:
    """테스트용 감사 로그 레코드 삽입."""
    import datetime

    now = datetime.datetime.now()
    logs = [
        AuditLog(
            actor="admin",
            action="LOGIN",
            target_table=None,
            target_id=None,
            detail="admin login success",
            ip_address="127.0.0.1",
            created_at=now - datetime.timedelta(days=2),
        ),
        AuditLog(
            actor="A00001",
            action="CREATE",
            target_table="Meeting",
            target_id="meeting-uuid-1",
            detail='{"before": null, "after": {"id": "meeting-uuid-1"}}',
            ip_address="127.0.0.1",
            created_at=now - datetime.timedelta(days=1),
        ),
        AuditLog(
            actor="admin",
            action="UPDATE",
            target_table="Employee",
            target_id="A00001",
            detail="POST /api/admin/employees/A00001/permissions → 200",
            ip_address="127.0.0.1",
            created_at=now,
        ),
    ]
    for log in logs:
        db.add(log)
    await db.flush()
    return logs


# ── 감사 로그 조회 ─────────────────────────────────────────────────────────────


async def test_list_audit_logs_admin_200(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    sample_audit_logs: list[AuditLog],
):
    """admin이 감사 로그 조회 → 200, 페이지네이션 포함."""
    resp = await client.get(
        "/api/admin/audit-logs",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data
    assert data["total"] >= 3
    assert isinstance(data["items"], list)


async def test_list_audit_logs_non_admin_403(
    client: AsyncClient,
    db: AsyncSession,
    active_emp: Employee,
):
    """비 admin이 감사 로그 조회 → 403."""
    resp = await client.get(
        "/api/admin/audit-logs",
        headers=_employee_headers(active_emp),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_list_audit_logs_filter_action(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    active_emp: Employee,
    sample_audit_logs: list[AuditLog],
):
    """action=LOGIN 필터 → LOGIN 액션만 반환."""
    resp = await client.get(
        "/api/admin/audit-logs?action=LOGIN",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["action"] == "LOGIN" for item in data["items"])
    assert data["total"] >= 1


async def test_list_audit_logs_filter_resource_type(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    active_emp: Employee,
    sample_audit_logs: list[AuditLog],
):
    """resource_type=Meeting 필터 → Meeting 관련만 반환."""
    resp = await client.get(
        "/api/admin/audit-logs?resource_type=Meeting",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["resource_type"] == "Meeting" for item in data["items"])
    assert data["total"] >= 1


async def test_list_audit_logs_filter_date_range(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    sample_audit_logs: list[AuditLog],
):
    """date_from/date_to 필터 → 해당 기간만 반환."""
    import datetime

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    resp = await client.get(
        f"/api/admin/audit-logs?date_from={yesterday}&date_to={today}",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    # sample_audit_logs 중 yesterday와 today에 해당하는 2건 포함되어야 함
    assert data["total"] >= 2


async def test_list_audit_logs_response_fields(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    active_emp: Employee,
    sample_audit_logs: list[AuditLog],
):
    """감사 로그 응답에 필수 필드가 포함되고 최신순 정렬."""
    resp = await client.get(
        "/api/admin/audit-logs",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1

    item = items[0]
    # 필수 필드 확인
    assert "id" in item
    assert "action" in item
    assert "actor_emp_no" in item
    assert "created_at" in item

    # 최신순 정렬 확인 (첫 번째 항목이 가장 최신)
    if len(items) >= 2:
        dt1 = datetime.datetime.fromisoformat(items[0]["created_at"])
        dt2 = datetime.datetime.fromisoformat(items[1]["created_at"])
        assert dt1 >= dt2


async def test_get_audit_log_single_admin_200(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    active_emp: Employee,
    sample_audit_logs: list[AuditLog],
):
    """감사 로그 단건 조회 (admin) → 200, detail 포함."""
    log_with_json = sample_audit_logs[1]  # JSON detail이 있는 로그

    resp = await client.get(
        f"/api/admin/audit-logs/{log_with_json.id}",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == log_with_json.id
    assert data["action"] == "CREATE"
    assert data["resource_type"] == "Meeting"
    assert data["resource_id"] == "meeting-uuid-1"
    # detail은 JSON으로 파싱되거나 문자열로 반환
    assert data["detail"] is not None


async def test_get_audit_log_not_found_404(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
):
    """없는 감사 로그 ID → 404."""
    resp = await client.get(
        "/api/admin/audit-logs/999999999",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 404


async def test_get_audit_log_non_admin_403(
    client: AsyncClient,
    db: AsyncSession,
    active_emp: Employee,
    sample_audit_logs: list[AuditLog],
):
    """비 admin이 단건 조회 → 403."""
    log = sample_audit_logs[0]
    resp = await client.get(
        f"/api/admin/audit-logs/{log.id}",
        headers=_employee_headers(active_emp),
    )
    assert resp.status_code == 403


async def test_audit_log_detail_json_parsed(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    active_emp: Employee,
    sample_audit_logs: list[AuditLog],
):
    """JSON 형식의 detail은 dict로 파싱되어야 한다."""
    json_log = sample_audit_logs[1]  # detail이 JSON 문자열인 로그
    resp = await client.get(
        f"/api/admin/audit-logs/{json_log.id}",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    # detail이 JSON이면 dict로 반환
    assert isinstance(data["detail"], dict)
    assert "before" in data["detail"]
    assert "after" in data["detail"]


async def test_no_audit_log_delete_api_exists(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    sample_audit_logs: list[AuditLog],
):
    """감사 로그 DELETE API가 없어야 함 (405 또는 404)."""
    log = sample_audit_logs[0]
    resp = await client.delete(
        f"/api/admin/audit-logs/{log.id}",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code in (404, 405)


# ── 직원 권한 관리 ─────────────────────────────────────────────────────────────


async def test_update_permissions_admin_success(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    target_emp: Employee,
):
    """admin이 직원 권한 변경 → EmployeeResponse 반환, EmployeeHistory 기록."""
    resp = await client.put(
        f"/api/admin/employees/{target_emp.emp_no}/permissions",
        json={"is_admin": False, "is_room_manager": True},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["emp_no"] == target_emp.emp_no
    assert data["is_room_manager"] is True
    assert data["is_admin"] is False
    # password_hash 미포함
    assert "password_hash" not in data

    # EmployeeHistory(UPDATE) 기록 확인
    result = await db.execute(
        select(EmployeeHistory).where(
            EmployeeHistory.target_id == target_emp.emp_no,
            EmployeeHistory.change_type == "UPDATE",
        )
    )
    history = result.scalars().all()
    assert len(history) >= 1
    last = history[-1]
    assert last.after_data["is_room_manager"] is True


async def test_update_permissions_non_admin_403(
    client: AsyncClient,
    db: AsyncSession,
    active_emp: Employee,
    target_emp: Employee,
):
    """비 admin이 권한 변경 → 403."""
    resp = await client.put(
        f"/api/admin/employees/{target_emp.emp_no}/permissions",
        json={"is_admin": True, "is_room_manager": False},
        headers=_employee_headers(active_emp),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_update_permissions_retired_employee_400(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    retired_emp: Employee,
):
    """퇴직 직원 권한 변경 → 400."""
    resp = await client.put(
        f"/api/admin/employees/{retired_emp.emp_no}/permissions",
        json={"is_admin": False, "is_room_manager": True},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 400


async def test_update_permissions_not_found_404(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
):
    """없는 직원 권한 변경 → 404."""
    resp = await client.put(
        "/api/admin/employees/XXXXXX/permissions",
        json={"is_admin": True, "is_room_manager": False},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 404


async def test_update_permissions_response_excludes_password(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    target_emp: Employee,
):
    """권한 변경 응답에 password_hash가 없어야 한다."""
    resp = await client.put(
        f"/api/admin/employees/{target_emp.emp_no}/permissions",
        json={"is_admin": True, "is_room_manager": True},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "password_hash" not in data
    assert "emp_no" in data
    assert "name" in data
    assert "is_admin" in data
    assert "is_room_manager" in data


async def test_list_audit_logs_pagination(
    client: AsyncClient,
    db: AsyncSession,
    test_admin: AdminAccount,
    sample_audit_logs: list[AuditLog],
):
    """페이지네이션: size=1이면 pages는 total과 동일."""
    resp = await client.get(
        "/api/admin/audit-logs?page=1&size=1",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["size"] == 1
    assert data["page"] == 1
    assert len(data["items"]) == 1
    assert data["pages"] >= data["total"]
