"""
Org backend tests.

Covers:
- 부서 생성 → DepartmentHistory(CREATE) 기록
- 부서 삭제 시 소속 직원 있으면 409
- 팀 삭제 시 소속 직원 있으면 409
- 직원 검색: 재직 직원만, 최대 50건, 이름 부분 일치
- admin이 아닌 사용자 → 부서 생성 403
- 직원 퇴직 처리 → status=RETIRED, EmployeeHistory(DELETE) 기록
- GET /api/employees 페이지네이션 응답 형식
- EmployeeResponse에 password_hash 미포함
- GET /api/departments 로그인 필요
- 팀 CRUD + TeamHistory 기록
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AdminAccount, Department, Employee, Team
from app.models.org import DepartmentHistory, EmployeeHistory, TeamHistory


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_token(sub: str, is_admin: bool = False) -> str:
    import datetime

    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    payload = {
        "sub": sub,
        "is_admin": is_admin,
        "exp": now + datetime.timedelta(minutes=30),
        "iat": now,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def _admin_headers(admin: AdminAccount) -> dict:
    token = _make_token("admin", is_admin=True)
    return {"Authorization": f"Bearer {token}"}


def _employee_headers(emp: Employee) -> dict:
    token = _make_token(emp.emp_no, is_admin=False)
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def active_emp_no_init(db: AsyncSession, test_admin: AdminAccount) -> Employee:
    """Active employee with is_initial_password=False."""
    emp = Employee(
        emp_no="E00010",
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


# ── Department tests ───────────────────────────────────────────────────────────


async def test_create_department_records_history(
    client: AsyncClient, db: AsyncSession, test_admin: AdminAccount
):
    """부서 생성 시 DepartmentHistory(CREATE) 기록."""
    resp = await client.post(
        "/api/departments",
        json={"code": "NEWDEPT", "name": "새부서"},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "NEWDEPT"
    assert data["name"] == "새부서"

    result = await db.execute(
        select(DepartmentHistory).where(DepartmentHistory.target_id == "NEWDEPT")
    )
    history = result.scalar_one_or_none()
    assert history is not None
    assert history.change_type == "CREATE"
    assert history.before_data is None
    assert history.after_data["code"] == "NEWDEPT"


async def test_delete_department_with_employee_raises_409(
    client: AsyncClient, db: AsyncSession, test_admin: AdminAccount
):
    """부서 삭제 시 소속 직원 있으면 409."""
    dept = Department(code="BUSY_DEPT", name="유직원부서")
    db.add(dept)
    emp = Employee(
        emp_no="E00020",
        name="부서직원",
        dept_code="BUSY_DEPT",
        password_hash="$test$x",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()

    resp = await client.delete(
        "/api/departments/BUSY_DEPT",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


async def test_delete_department_with_team_raises_409(
    client: AsyncClient, db: AsyncSession, test_admin: AdminAccount
):
    """부서 삭제 시 소속 팀 있으면 409."""
    dept = Department(code="TEAM_DEPT", name="팀있는부서")
    db.add(dept)
    team = Team(code="TEAM01", name="팀", dept_code="TEAM_DEPT")
    db.add(team)
    await db.flush()

    resp = await client.delete(
        "/api/departments/TEAM_DEPT",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 409


async def test_non_admin_create_department_returns_403(
    client: AsyncClient, active_emp_no_init: Employee
):
    """admin이 아닌 사용자가 부서 생성 시도 → 403."""
    resp = await client.post(
        "/api/departments",
        json={"code": "FORBIDDEN_DEPT", "name": "금지부서"},
        headers=_employee_headers(active_emp_no_init),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_list_departments_requires_login(client: AsyncClient):
    """GET /api/departments는 인증 필요."""
    resp = await client.get("/api/departments")
    assert resp.status_code == 401


async def test_list_departments_active_user(
    client: AsyncClient, active_emp_no_init: Employee, test_admin: AdminAccount
):
    """로그인한 일반 직원도 부서 목록 조회 가능."""
    await client.post(
        "/api/departments",
        json={"code": "LISTDEPT", "name": "목록부서"},
        headers=_admin_headers(test_admin),
    )
    resp = await client.get(
        "/api/departments",
        headers=_employee_headers(active_emp_no_init),
    )
    assert resp.status_code == 200
    codes = [d["code"] for d in resp.json()]
    assert "LISTDEPT" in codes


async def test_update_department_records_history(
    client: AsyncClient, db: AsyncSession, test_admin: AdminAccount
):
    """부서 수정 시 DepartmentHistory(UPDATE) 기록."""
    await client.post(
        "/api/departments",
        json={"code": "UPDDEPT", "name": "수정전"},
        headers=_admin_headers(test_admin),
    )
    resp = await client.put(
        "/api/departments/UPDDEPT",
        json={"name": "수정후"},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "수정후"

    result = await db.execute(
        select(DepartmentHistory)
        .where(DepartmentHistory.target_id == "UPDDEPT")
        .where(DepartmentHistory.change_type == "UPDATE")
    )
    history = result.scalar_one_or_none()
    assert history is not None
    assert history.before_data["name"] == "수정전"
    assert history.after_data["name"] == "수정후"


# ── Team tests ────────────────────────────────────────────────────────────────


async def test_create_team_records_history(
    client: AsyncClient, db: AsyncSession, test_admin: AdminAccount
):
    """팀 생성 시 TeamHistory(CREATE) 기록."""
    resp = await client.post(
        "/api/teams",
        json={"code": "TEAM99", "name": "신규팀", "dept_code": "TESTDEPT"},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 201

    result = await db.execute(
        select(TeamHistory).where(TeamHistory.target_id == "TEAM99")
    )
    history = result.scalar_one_or_none()
    assert history is not None
    assert history.change_type == "CREATE"


async def test_delete_team_with_employee_raises_409(
    client: AsyncClient, db: AsyncSession, test_admin: AdminAccount
):
    """팀 삭제 시 소속 직원 있으면 409."""
    team = Team(code="BUSY_TEAM", name="바쁜팀", dept_code="TESTDEPT")
    db.add(team)
    emp = Employee(
        emp_no="E00030",
        name="팀직원",
        dept_code="TESTDEPT",
        team_code="BUSY_TEAM",
        password_hash="$test$x",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()

    resp = await client.delete(
        "/api/teams/BUSY_TEAM",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


# ── Employee tests ────────────────────────────────────────────────────────────


async def test_employee_list_pagination(
    client: AsyncClient, db: AsyncSession, test_admin: AdminAccount
):
    """GET /api/employees 페이지네이션 필드 포함."""
    resp = await client.get(
        "/api/employees",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data


async def test_employee_response_no_password_hash(
    client: AsyncClient, db: AsyncSession, test_admin: AdminAccount
):
    """EmployeeResponse에 password_hash 미포함."""
    emp = Employee(
        emp_no="E00040",
        name="비번테스트",
        dept_code="TESTDEPT",
        password_hash="$test$secret",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()

    resp = await client.get(
        "/api/employees/E00040",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "password_hash" not in data
    assert "login_fail_count" not in data
    assert "locked_until" not in data


async def test_retire_employee(
    client: AsyncClient, db: AsyncSession, test_admin: AdminAccount
):
    """직원 퇴직 처리 → status=RETIRED, EmployeeHistory(DELETE) 기록."""
    emp = Employee(
        emp_no="E00050",
        name="퇴직예정자",
        dept_code="TESTDEPT",
        password_hash="$test$x",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()

    resp = await client.delete(
        "/api/employees/E00050",
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200

    await db.refresh(emp)
    assert emp.status == "RETIRED"

    result = await db.execute(
        select(EmployeeHistory)
        .where(EmployeeHistory.target_id == "E00050")
        .where(EmployeeHistory.change_type == "DELETE")
    )
    history = result.scalar_one_or_none()
    assert history is not None
    assert history.before_data["status"] == "ACTIVE"
    assert history.after_data["status"] == "RETIRED"


async def test_employee_search_active_only(
    client: AsyncClient, db: AsyncSession, active_emp_no_init: Employee
):
    """직원 검색: 재직 직원만 반환, 퇴직 직원 제외."""
    retired = Employee(
        emp_no="E00060",
        name="퇴직검색테스트",
        dept_code="TESTDEPT",
        password_hash="$test$x",
        status="RETIRED",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(retired)
    active = Employee(
        emp_no="E00061",
        name="재직검색테스트",
        dept_code="TESTDEPT",
        password_hash="$test$x",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(active)
    await db.flush()

    resp = await client.get(
        "/api/employees/search?q=검색테스트",
        headers=_employee_headers(active_emp_no_init),
    )
    assert resp.status_code == 200
    results = resp.json()
    emp_nos = [r["emp_no"] for r in results]
    assert "E00061" in emp_nos
    assert "E00060" not in emp_nos


async def test_employee_search_korean_partial_match(
    client: AsyncClient, db: AsyncSession, active_emp_no_init: Employee
):
    """한글 이름 부분 일치 검색."""
    emp = Employee(
        emp_no="E00070",
        name="홍길동",
        dept_code="TESTDEPT",
        password_hash="$test$x",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()

    resp = await client.get(
        "/api/employees/search?q=홍길",
        headers=_employee_headers(active_emp_no_init),
    )
    assert resp.status_code == 200
    results = resp.json()
    emp_nos = [r["emp_no"] for r in results]
    assert "E00070" in emp_nos


async def test_employee_search_includes_dept_name(
    client: AsyncClient, db: AsyncSession, active_emp_no_init: Employee
):
    """검색 결과에 dept_name 포함."""
    emp = Employee(
        emp_no="E00080",
        name="부서명확인",
        dept_code="TESTDEPT",
        password_hash="$test$x",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()

    resp = await client.get(
        "/api/employees/search?q=부서명확인",
        headers=_employee_headers(active_emp_no_init),
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) > 0
    assert "dept_name" in results[0]
    assert results[0]["dept_name"] == "테스트부서"


async def test_employee_update(
    client: AsyncClient, db: AsyncSession, test_admin: AdminAccount
):
    """직원 정보 수정 (이름, 직급) — 권한 필드는 변경 불가."""
    emp = Employee(
        emp_no="E00090",
        name="수정전이름",
        dept_code="TESTDEPT",
        password_hash="$test$x",
        status="ACTIVE",
        is_initial_password=False,
        is_admin=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()

    resp = await client.put(
        "/api/employees/E00090",
        json={"name": "수정후이름", "rank": "대리"},
        headers=_admin_headers(test_admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "수정후이름"
    assert data["rank"] == "대리"
    assert data["is_admin"] is False
