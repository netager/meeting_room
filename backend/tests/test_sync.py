"""
ETL 동기화 배치 테스트.

password hashing은 conftest.py의 mock_password_ops가 fast hash로 대체한다.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Department, Employee, EmployeeHistory, EmployeeStaging


# ── helpers ───────────────────────────────────────────────────────────────────


async def _add_dept(db: AsyncSession, code: str, name: str) -> Department:
    result = await db.execute(select(Department).where(Department.code == code))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    dept = Department(code=code, name=name)
    db.add(dept)
    await db.flush()
    return dept


async def _add_staging(
    db: AsyncSession,
    emp_no: str,
    name: str = "스테이징직원",
    dept_code: str = "TESTDEPT",
    rank: str | None = None,
    team_code: str | None = None,
) -> EmployeeStaging:
    staging = EmployeeStaging(
        emp_no=emp_no,
        name=name,
        dept_code=dept_code,
        team_code=team_code,
        rank=rank,
    )
    db.add(staging)
    await db.flush()
    return staging


async def _add_employee(
    db: AsyncSession,
    emp_no: str,
    name: str = "기존직원",
    dept_code: str = "TESTDEPT",
    status: str = "ACTIVE",
    is_admin: bool = False,
    is_room_manager: bool = False,
    password_hash: str = "$test$Password1",
    login_fail_count: int = 0,
) -> Employee:
    emp = Employee(
        emp_no=emp_no,
        name=name,
        dept_code=dept_code,
        status=status,
        password_hash=password_hash,
        is_admin=is_admin,
        is_room_manager=is_room_manager,
        is_initial_password=False,
        login_fail_count=login_fail_count,
    )
    db.add(emp)
    await db.flush()
    return emp


async def _run_sync(db: AsyncSession, triggered_by: str = "test") -> dict:
    from app.services import sync_service

    return await sync_service.run(db, triggered_by=triggered_by)


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_new_employee(db: AsyncSession):
    """신규 직원 동기화 → Employee INSERT, is_initial_password=True, 초기 비밀번호=행번."""
    await _add_staging(db, "S00001", name="신규직원")

    result = await _run_sync(db)

    assert result["added"] == 1
    assert result["updated"] == 0
    assert result["retired"] == 0

    emp = await db.get(Employee, "S00001")
    assert emp is not None
    assert emp.name == "신규직원"
    assert emp.status == "ACTIVE"
    assert emp.is_initial_password is True
    # 초기 비밀번호 = 행번 (mock hash: $test$<password>)
    assert emp.password_hash == "$test$S00001"
    assert emp.is_admin is False
    assert emp.is_room_manager is False


@pytest.mark.asyncio
async def test_sync_new_employee_history_recorded(db: AsyncSession):
    """신규 직원 동기화 시 EmployeeHistory(CREATE) 기록."""
    await _add_staging(db, "S00010", name="이력테스트")

    await _run_sync(db)

    result = await db.execute(
        select(EmployeeHistory).where(EmployeeHistory.target_id == "S00010")
    )
    histories = result.scalars().all()
    assert len(histories) == 1
    assert histories[0].change_type == "CREATE"
    assert histories[0].before_data is None
    assert histories[0].after_data["name"] == "이력테스트"


@pytest.mark.asyncio
async def test_sync_update_employee(db: AsyncSession):
    """정보 변경 동기화 → UPDATE (비밀번호·권한 필드는 유지)."""
    await _add_employee(
        db, "S00002", name="이전이름", dept_code="TESTDEPT",
        is_admin=True, is_room_manager=True, password_hash="$test$OldPass1",
    )
    await _add_staging(db, "S00002", name="새이름", dept_code="TESTDEPT")

    result = await _run_sync(db)

    assert result["updated"] == 1
    assert result["added"] == 0

    emp = await db.get(Employee, "S00002")
    assert emp.name == "새이름"
    # 권한 필드는 유지
    assert emp.is_admin is True
    assert emp.is_room_manager is True
    # 비밀번호 유지
    assert emp.password_hash == "$test$OldPass1"


@pytest.mark.asyncio
async def test_sync_update_history_recorded(db: AsyncSession):
    """변경 동기화 시 EmployeeHistory(UPDATE) 기록."""
    await _add_employee(db, "S00011", name="원래이름")
    await _add_staging(db, "S00011", name="바뀐이름")

    await _run_sync(db)

    result = await db.execute(
        select(EmployeeHistory).where(EmployeeHistory.target_id == "S00011")
    )
    histories = result.scalars().all()
    assert len(histories) == 1
    assert histories[0].change_type == "UPDATE"
    assert histories[0].before_data["name"] == "원래이름"
    assert histories[0].after_data["name"] == "바뀐이름"


@pytest.mark.asyncio
async def test_sync_no_change_skipped(db: AsyncSession):
    """내용 동일 → 아무 변경 없음 (skipped)."""
    await _add_employee(db, "S00003", name="동일직원", dept_code="TESTDEPT")
    await _add_staging(db, "S00003", name="동일직원", dept_code="TESTDEPT")

    result = await _run_sync(db)

    assert result["skipped"] == 1
    assert result["updated"] == 0
    assert result["added"] == 0

    result_hist = await db.execute(
        select(EmployeeHistory).where(EmployeeHistory.target_id == "S00003")
    )
    assert len(result_hist.scalars().all()) == 0


@pytest.mark.asyncio
async def test_sync_retire_employee(db: AsyncSession):
    """퇴직 처리 → status=RETIRED, EmployeeHistory(DELETE) 기록."""
    # staging에는 S00005만 있고, S00004는 없음 (staging에 최소 1명은 있어야 안전장치 우회)
    await _add_employee(db, "S00004", name="퇴직예정직원")
    await _add_employee(db, "S00005", name="유지직원")
    await _add_staging(db, "S00005", name="유지직원")

    result = await _run_sync(db)

    assert result["retired"] == 1
    assert result["skipped"] == 1  # S00005는 동일

    emp = await db.get(Employee, "S00004")
    assert emp.status == "RETIRED"

    result_hist = await db.execute(
        select(EmployeeHistory).where(EmployeeHistory.target_id == "S00004")
    )
    histories = result_hist.scalars().all()
    assert len(histories) == 1
    assert histories[0].change_type == "DELETE"


@pytest.mark.asyncio
async def test_sync_staging_empty_aborts(db: AsyncSession):
    """스테이징 비어있을 때 → 실행 중단, 직원 퇴직 처리 없음."""
    # ACTIVE 직원 존재
    await _add_employee(db, "S00006", name="안전직원")

    # staging 비어있음 (아무것도 추가 안 함)
    result = await _run_sync(db)

    assert result == {"added": 0, "updated": 0, "retired": 0, "skipped": 0}

    # 직원이 RETIRED로 바뀌지 않아야 함
    emp = await db.get(Employee, "S00006")
    assert emp.status == "ACTIVE"


@pytest.mark.asyncio
async def test_sync_restore_retired_employee(db: AsyncSession):
    """이미 퇴직한 직원이 스테이징에 재등장 → 재직 복원, 비밀번호 초기화."""
    await _add_employee(
        db, "S00007", name="복직직원", status="RETIRED",
        password_hash="$test$OldPass1",
    )
    await _add_staging(db, "S00007", name="복직직원")

    result = await _run_sync(db)

    assert result["added"] == 1  # 복원은 added로 카운트

    emp = await db.get(Employee, "S00007")
    assert emp.status == "ACTIVE"
    assert emp.is_initial_password is True
    assert emp.password_hash == "$test$S00007"  # 행번으로 초기화


@pytest.mark.asyncio
async def test_sync_restore_history_recorded(db: AsyncSession):
    """복원 시 EmployeeHistory(UPDATE) 기록."""
    await _add_employee(db, "S00012", name="복직이력", status="RETIRED")
    await _add_staging(db, "S00012", name="복직이력")

    await _run_sync(db)

    result = await db.execute(
        select(EmployeeHistory).where(EmployeeHistory.target_id == "S00012")
    )
    histories = result.scalars().all()
    assert len(histories) == 1
    assert histories[0].change_type == "UPDATE"
    assert histories[0].before_data["status"] == "RETIRED"
    assert histories[0].after_data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_sync_password_not_overwritten(db: AsyncSession):
    """동기화로 기존 직원의 비밀번호가 덮어씌워지지 않음."""
    await _add_employee(
        db, "S00008", name="비번테스트", dept_code="TESTDEPT",
        password_hash="$test$MySecurePass1",
    )
    await _add_staging(db, "S00008", name="비번테스트변경")

    await _run_sync(db)

    emp = await db.get(Employee, "S00008")
    assert emp.password_hash == "$test$MySecurePass1"
    assert emp.name == "비번테스트변경"


@pytest.mark.asyncio
async def test_sync_permissions_not_overwritten(db: AsyncSession):
    """동기화로 기존 직원의 권한 필드가 덮어씌워지지 않음."""
    await _add_employee(
        db, "S00009", name="권한테스트", dept_code="TESTDEPT",
        is_admin=True, is_room_manager=True,
    )
    await _add_staging(db, "S00009", name="권한테스트변경")

    await _run_sync(db)

    emp = await db.get(Employee, "S00009")
    assert emp.is_admin is True
    assert emp.is_room_manager is True


@pytest.mark.asyncio
async def test_sync_already_retired_skipped(db: AsyncSession):
    """employee에만 있고 status=RETIRED인 경우 → 퇴직 처리 스킵."""
    await _add_employee(db, "S00013", name="이미퇴직", status="RETIRED")
    # staging에 다른 직원 하나 (빈 staging 안전장치 방지)
    await _add_staging(db, "S00014", name="다른직원")
    await _add_employee(db, "S00014", name="다른직원")

    result = await _run_sync(db)

    # S00013은 이미 RETIRED이므로 retired 카운트 증가 없음
    assert result["retired"] == 0


@pytest.mark.asyncio
async def test_sync_admin_api_forbidden_without_auth(client):
    """POST /api/admin/sync/run이 admin 권한 없이 호출되면 401 반환."""
    response = await client.post("/api/admin/sync/run")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sync_admin_api_requires_admin(client, active_employee, db: AsyncSession):
    """POST /api/admin/sync/run이 일반 직원 토큰으로 호출되면 403 반환."""
    from app.services.auth_service import create_access_token

    token = await create_access_token(
        active_employee.emp_no,
        is_admin=False,
        extra={"is_initial_password": False, "is_room_manager": False, "name": "테스트"},
    )
    response = await client.post(
        "/api/admin/sync/run",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sync_admin_api_success(client, test_admin, db: AsyncSession):
    """POST /api/admin/sync/run이 admin 토큰으로 성공."""
    from app.services.auth_service import create_access_token

    # staging에 직원 추가
    staging = EmployeeStaging(
        emp_no="S00099",
        name="API테스트직원",
        dept_code="TESTDEPT",
    )
    db.add(staging)
    await db.flush()

    token = await create_access_token(
        "admin",
        is_admin=True,
        extra={"is_initial_password": False, "is_room_manager": True, "name": "관리자"},
    )
    response = await client.post(
        "/api/admin/sync/run",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "added" in data
    assert data["triggered_by"] == "admin"
