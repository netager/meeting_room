from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import require_active_user, require_admin
from app.repositories import org_repo
from app.schemas.org import EmployeeResponse, EmployeeSearchItem, EmployeeUpdate, PaginatedResponse

router = APIRouter(prefix="/api/employees", tags=["employees"])


def _actor_id(user) -> str:
    from app.models import AdminAccount
    if isinstance(user, AdminAccount):
        return "admin"
    return user.emp_no


@router.get("", response_model=PaginatedResponse[EmployeeResponse])
async def list_employees(
    page: int = 1,
    size: int = 20,
    status: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_admin),
):
    if size > 100:
        size = 100
    items, total = await org_repo.get_employees(db, page=page, size=size, status=status, search=search)
    pages = math.ceil(total / size) if size else 0
    return {
        "items": [EmployeeResponse.model_validate(e) for e in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.get("/search", response_model=list[EmployeeSearchItem])
async def search_employees(
    q: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_active_user),
):
    if not q:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_REQUEST", "message": "검색어를 입력하세요"}},
        )
    results = await org_repo.search_employees_for_attendee(q, db)
    return results


@router.get("/{emp_no}", response_model=EmployeeResponse)
async def get_employee(
    emp_no: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_admin),
):
    emp = await org_repo.get_employee(emp_no, db)
    if emp is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "직원을 찾을 수 없습니다"}},
        )
    return EmployeeResponse.model_validate(emp)


@router.put("/{emp_no}", response_model=EmployeeResponse)
async def update_employee(
    emp_no: str,
    body: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    emp = await org_repo.update_employee(
        emp_no, body.model_dump(exclude_none=True), _actor_id(user), db
    )
    return EmployeeResponse.model_validate(emp)


@router.delete("/{emp_no}")
async def retire_employee(
    emp_no: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    await org_repo.retire_employee(emp_no, _actor_id(user), db)
    return JSONResponse(content={"message": "퇴직 처리되었습니다"})
