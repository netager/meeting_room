from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import require_active_user, require_admin
from app.repositories import org_repo
from app.schemas.org import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    TeamCreate,
    TeamResponse,
    TeamUpdate,
)

router = APIRouter(tags=["departments"])


def _actor_id(user) -> str:
    from app.models import AdminAccount
    if isinstance(user, AdminAccount):
        return "admin"
    return user.emp_no


# ── Departments ───────────────────────────────────────────────────────────────


@router.get("/api/departments", response_model=list[DepartmentResponse])
async def list_departments(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_active_user),
):
    depts = await org_repo.get_departments(db, include_inactive=include_inactive)
    return [DepartmentResponse.model_validate(d) for d in depts]


@router.post("/api/departments", response_model=DepartmentResponse, status_code=201)
async def create_department(
    body: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    existing = await org_repo.get_department(body.code, db)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "CONFLICT", "message": "이미 존재하는 부서 코드입니다"}},
        )
    dept = await org_repo.create_department(body.model_dump(), _actor_id(user), db)
    return DepartmentResponse.model_validate(dept)


@router.put("/api/departments/{code}", response_model=DepartmentResponse)
async def update_department(
    code: str,
    body: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    dept = await org_repo.update_department(code, body.model_dump(exclude_none=True), _actor_id(user), db)
    return DepartmentResponse.model_validate(dept)


@router.delete("/api/departments/{code}")
async def delete_department(
    code: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    await org_repo.delete_department(code, _actor_id(user), db)
    return JSONResponse(content={"message": "부서가 삭제되었습니다"})


@router.get("/api/departments/{code}/teams", response_model=list[TeamResponse])
async def list_teams(
    code: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_active_user),
):
    dept = await org_repo.get_department(code, db)
    if dept is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "부서를 찾을 수 없습니다"}},
        )
    teams = await org_repo.get_teams(code, db)
    return [TeamResponse.model_validate(t) for t in teams]


# ── Teams ─────────────────────────────────────────────────────────────────────


@router.post("/api/teams", response_model=TeamResponse, status_code=201)
async def create_team(
    body: TeamCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    dept = await org_repo.get_department(body.dept_code, db)
    if dept is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "부서를 찾을 수 없습니다"}},
        )
    existing = await org_repo.get_team(body.code, db)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "CONFLICT", "message": "이미 존재하는 팀 코드입니다"}},
        )
    team = await org_repo.create_team(body.model_dump(), _actor_id(user), db)
    return TeamResponse.model_validate(team)


@router.put("/api/teams/{code}", response_model=TeamResponse)
async def update_team(
    code: str,
    body: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    team = await org_repo.update_team(code, body.model_dump(exclude_none=True), _actor_id(user), db)
    return TeamResponse.model_validate(team)


@router.delete("/api/teams/{code}")
async def delete_team(
    code: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    await org_repo.delete_team(code, _actor_id(user), db)
    return JSONResponse(content={"message": "팀이 삭제되었습니다"})
