from __future__ import annotations

import math
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.dependencies import require_admin
from app.repositories import audit_repo, org_repo
from app.schemas.admin import AuditLogResponse, PaginatedAuditLogs

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _actor_id(user) -> str:
    from app.models import AdminAccount
    if isinstance(user, AdminAccount):
        return "admin"
    return user.emp_no


# ── 직원 권한 관리 ─────────────────────────────────────────────────────────────


class PermissionsUpdate(BaseModel):
    is_admin: bool
    is_room_manager: bool


@router.put("/employees/{emp_no}/permissions")
async def update_employee_permissions(
    emp_no: str,
    body: PermissionsUpdate,
    user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    직원 is_admin / is_room_manager 권한 변경.
    AuditLog(UPDATE, Employee) 기록은 org_repo.update_permissions 에서 처리.
    """
    from app.schemas.org import EmployeeResponse

    emp = await org_repo.update_permissions(
        emp_no, body.is_admin, body.is_room_manager, _actor_id(user), db
    )
    return EmployeeResponse.model_validate(emp)


# ── 감사 로그 조회 ─────────────────────────────────────────────────────────────


@router.get("/audit-logs", response_model=PaginatedAuditLogs)
async def list_audit_logs(
    action: Optional[str] = Query(None, description="LOGIN / LOGIN_FAIL / CREATE / UPDATE / DELETE / DOWNLOAD / BATCH_RUN"),
    resource_type: Optional[str] = Query(None, description="대상 테이블명 (예: Meeting, Employee)"),
    actor_emp_no: Optional[str] = Query(None, description="행위자 행번 또는 admin"),
    date_from: Optional[date] = Query(None, description="조회 시작일 (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="조회 종료일 (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    _user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """감사 로그 목록 조회 (admin 전용). 최신순 정렬."""
    items, total = await audit_repo.get_audit_logs(
        db,
        action=action,
        resource_type=resource_type,
        actor_emp_no=actor_emp_no,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )
    pages = math.ceil(total / size) if total else 0
    return PaginatedAuditLogs(
        items=[AuditLogResponse.from_log(log, actor_name) for log, actor_name in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/audit-logs/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: int,
    _user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """감사 로그 단건 조회 (detail JSONB 포함, admin 전용)."""
    row = await audit_repo.get_audit_log(log_id, db)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "감사 로그를 찾을 수 없습니다"}},
        )
    log, actor_name = row
    return AuditLogResponse.from_log(log, actor_name)


# ── ETL 동기화 ─────────────────────────────────────────────────────────────────


@router.post("/sync/run")
async def run_sync(
    _user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services import sync_service

    result = await sync_service.run(db, triggered_by="admin")
    return {**result, "triggered_by": "admin"}


# ── 개발 환경 전용: 임시원장 직접 조작 ───────────────────────────────────────


def _check_dev_env() -> None:
    if settings.app_env != "development":
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "개발 환경에서만 사용 가능합니다"}},
        )


class StagingRecord(BaseModel):
    emp_no: str
    name: str
    dept_code: str
    team_code: Optional[str] = None
    rank: Optional[str] = None


@router.get("/staging")
async def list_staging(
    _user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_dev_env()
    from app.repositories import staging_repo

    records = await staging_repo.get_all_staging(db)
    return [
        {
            "emp_no": r.emp_no,
            "name": r.name,
            "dept_code": r.dept_code,
            "team_code": r.team_code,
            "rank": r.rank,
        }
        for r in records
    ]


@router.post("/staging")
async def upsert_staging(
    record: StagingRecord,
    _user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_dev_env()
    from app.repositories import staging_repo

    await staging_repo.upsert_staging([record.model_dump()], db)
    return {"status": "ok"}


@router.delete("/staging/{emp_no}")
async def delete_staging(
    emp_no: str,
    _user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _check_dev_env()
    from app.repositories import staging_repo

    existing = await staging_repo.get_staging_record(emp_no, db)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "스테이징 레코드를 찾을 수 없습니다"}},
        )
    await staging_repo.delete_staging_record(emp_no, db)
    return {"status": "ok"}
