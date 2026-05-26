from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.dependencies import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


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
