from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import (
    Department,
    DepartmentHistory,
    Employee,
    EmployeeHistory,
    Team,
    TeamHistory,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _dept_to_dict(dept: Department) -> dict:
    return {"code": dept.code, "name": dept.name, "status": dept.status}


def _team_to_dict(team: Team) -> dict:
    return {
        "code": team.code,
        "name": team.name,
        "dept_code": team.dept_code,
        "status": team.status,
    }


def _emp_to_dict(emp: Employee) -> dict:
    return {
        "emp_no": emp.emp_no,
        "name": emp.name,
        "dept_code": emp.dept_code,
        "team_code": emp.team_code,
        "rank": emp.rank,
        "status": emp.status,
        "is_admin": emp.is_admin,
        "is_room_manager": emp.is_room_manager,
    }


# ── Department ────────────────────────────────────────────────────────────────


async def get_departments(
    db: AsyncSession, include_inactive: bool = False
) -> list[Department]:
    q = select(Department)
    if not include_inactive:
        q = q.where(Department.status == "ACTIVE")
    result = await db.execute(q.order_by(Department.code))
    return list(result.scalars().all())


async def get_department(dept_code: str, db: AsyncSession) -> Department | None:
    result = await db.execute(
        select(Department).where(Department.code == dept_code)
    )
    return result.scalar_one_or_none()


async def create_department(
    data: dict, changed_by: str, db: AsyncSession
) -> Department:
    dept = Department(code=data["code"], name=data["name"])
    db.add(dept)
    await db.flush()

    history = DepartmentHistory(
        target_id=dept.code,
        change_type="CREATE",
        before_data=None,
        after_data=_dept_to_dict(dept),
        changed_by=changed_by,
    )
    db.add(history)
    await db.commit()
    await db.refresh(dept)
    return dept


async def update_department(
    dept_code: str, data: dict, changed_by: str, db: AsyncSession
) -> Department:
    dept = await get_department(dept_code, db)
    if dept is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "부서를 찾을 수 없습니다"}},
        )

    before = _dept_to_dict(dept)
    for field, value in data.items():
        if value is not None:
            setattr(dept, field, value)
    await db.flush()

    history = DepartmentHistory(
        target_id=dept.code,
        change_type="UPDATE",
        before_data=before,
        after_data=_dept_to_dict(dept),
        changed_by=changed_by,
    )
    db.add(history)
    await db.commit()
    await db.refresh(dept)
    return dept


async def delete_department(
    dept_code: str, changed_by: str, db: AsyncSession
) -> None:
    dept = await get_department(dept_code, db)
    if dept is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "부서를 찾을 수 없습니다"}},
        )

    team_count = await db.scalar(
        select(func.count()).where(Team.dept_code == dept_code)
    )
    if team_count and team_count > 0:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "CONFLICT", "message": "소속 팀이 있어 삭제할 수 없습니다"}},
        )

    emp_count = await db.scalar(
        select(func.count()).where(Employee.dept_code == dept_code)
    )
    if emp_count and emp_count > 0:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "CONFLICT", "message": "소속 직원이 있어 삭제할 수 없습니다"}},
        )

    before = _dept_to_dict(dept)
    history = DepartmentHistory(
        target_id=dept.code,
        change_type="DELETE",
        before_data=before,
        after_data=None,
        changed_by=changed_by,
    )
    db.add(history)
    await db.delete(dept)
    await db.commit()


# ── Team ──────────────────────────────────────────────────────────────────────


async def get_teams(dept_code: str, db: AsyncSession) -> list[Team]:
    result = await db.execute(
        select(Team).where(Team.dept_code == dept_code).order_by(Team.code)
    )
    return list(result.scalars().all())


async def get_team(team_code: str, db: AsyncSession) -> Team | None:
    result = await db.execute(select(Team).where(Team.code == team_code))
    return result.scalar_one_or_none()


async def create_team(data: dict, changed_by: str, db: AsyncSession) -> Team:
    team = Team(
        code=data["code"], name=data["name"], dept_code=data["dept_code"]
    )
    db.add(team)
    await db.flush()

    history = TeamHistory(
        target_id=team.code,
        change_type="CREATE",
        before_data=None,
        after_data=_team_to_dict(team),
        changed_by=changed_by,
    )
    db.add(history)
    await db.commit()
    await db.refresh(team)
    return team


async def update_team(
    team_code: str, data: dict, changed_by: str, db: AsyncSession
) -> Team:
    team = await get_team(team_code, db)
    if team is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "팀을 찾을 수 없습니다"}},
        )

    before = _team_to_dict(team)
    for field, value in data.items():
        if value is not None:
            setattr(team, field, value)
    await db.flush()

    history = TeamHistory(
        target_id=team.code,
        change_type="UPDATE",
        before_data=before,
        after_data=_team_to_dict(team),
        changed_by=changed_by,
    )
    db.add(history)
    await db.commit()
    await db.refresh(team)
    return team


async def delete_team(team_code: str, changed_by: str, db: AsyncSession) -> None:
    team = await get_team(team_code, db)
    if team is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "팀을 찾을 수 없습니다"}},
        )

    emp_count = await db.scalar(
        select(func.count()).where(Employee.team_code == team_code)
    )
    if emp_count and emp_count > 0:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "CONFLICT", "message": "소속 직원이 있어 삭제할 수 없습니다"}},
        )

    before = _team_to_dict(team)
    history = TeamHistory(
        target_id=team.code,
        change_type="DELETE",
        before_data=before,
        after_data=None,
        changed_by=changed_by,
    )
    db.add(history)
    await db.delete(team)
    await db.commit()


# ── Employee ──────────────────────────────────────────────────────────────────


async def get_employees(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    status: str | None = None,
    search: str | None = None,
) -> tuple[list[Employee], int]:
    q = select(Employee)
    if status:
        q = q.where(Employee.status == status)
    if search:
        q = q.where(Employee.name.ilike(f"%{search}%"))

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(Employee.emp_no).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    return list(result.scalars().all()), total or 0


async def get_employee(emp_no: str, db: AsyncSession) -> Employee | None:
    result = await db.execute(select(Employee).where(Employee.emp_no == emp_no))
    return result.scalar_one_or_none()


async def update_employee(
    emp_no: str, data: dict, changed_by: str, db: AsyncSession
) -> Employee:
    emp = await get_employee(emp_no, db)
    if emp is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "직원을 찾을 수 없습니다"}},
        )

    # password/permission fields must not be updated here
    protected = {"password_hash", "is_admin", "is_room_manager", "login_fail_count", "locked_until"}
    before = _emp_to_dict(emp)
    for field, value in data.items():
        if field in protected:
            continue
        if value is not None:
            setattr(emp, field, value)
    await db.flush()

    history = EmployeeHistory(
        target_id=emp.emp_no,
        change_type="UPDATE",
        before_data=before,
        after_data=_emp_to_dict(emp),
        changed_by=changed_by,
    )
    db.add(history)
    await db.commit()
    await db.refresh(emp)
    return emp


async def retire_employee(emp_no: str, changed_by: str, db: AsyncSession) -> None:
    emp = await get_employee(emp_no, db)
    if emp is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "직원을 찾을 수 없습니다"}},
        )

    before = _emp_to_dict(emp)
    emp.status = "RETIRED"
    await db.flush()

    history = EmployeeHistory(
        target_id=emp.emp_no,
        change_type="DELETE",
        before_data=before,
        after_data=_emp_to_dict(emp),
        changed_by=changed_by,
    )
    db.add(history)
    await db.commit()


async def search_employees_for_attendee(
    query: str, db: AsyncSession
) -> list[dict]:
    result = await db.execute(
        select(Employee, Department)
        .join(Department, Employee.dept_code == Department.code)
        .where(Employee.status == "ACTIVE")
        .where(
            or_(
                Employee.name.ilike(f"%{query}%"),
                Employee.emp_no.ilike(f"%{query}%"),
            )
        )
        .order_by(Employee.emp_no)
        .limit(50)
    )
    rows = result.all()
    return [
        {
            "emp_no": emp.emp_no,
            "name": emp.name,
            "dept_code": emp.dept_code,
            "dept_name": dept.name,
            "rank": emp.rank,
        }
        for emp, dept in rows
    ]


async def update_permissions(
    emp_no: str,
    is_admin: bool,
    is_room_manager: bool,
    changed_by: str,
    db: AsyncSession,
) -> Employee:
    emp = await get_employee(emp_no, db)
    if emp is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "직원을 찾을 수 없습니다"}},
        )
    if emp.status == "RETIRED":
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_REQUEST", "message": "퇴직 직원에게 권한을 부여할 수 없습니다"}},
        )

    before = _emp_to_dict(emp)
    emp.is_admin = is_admin
    emp.is_room_manager = is_room_manager
    await db.flush()

    history = EmployeeHistory(
        target_id=emp.emp_no,
        change_type="UPDATE",
        before_data=before,
        after_data=_emp_to_dict(emp),
        changed_by=changed_by,
    )
    db.add(history)
    await db.commit()
    await db.refresh(emp)
    return emp
