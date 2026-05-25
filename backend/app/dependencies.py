from __future__ import annotations

from typing import Union

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import AdminAccount, Employee

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _is_admin(user: Union[Employee, AdminAccount]) -> bool:
    if isinstance(user, AdminAccount):
        return True
    return bool(user.is_admin)


def _is_room_manager(user: Union[Employee, AdminAccount]) -> bool:
    if isinstance(user, AdminAccount):
        return True
    return bool(user.is_room_manager)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Union[Employee, AdminAccount]:
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "인증이 필요합니다"}},
        )

    from app.services import auth_service
    from app.repositories import auth_repo

    payload = await auth_service.verify_access_token(token)
    sub = payload.get("sub")

    if not sub:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "유효하지 않은 토큰입니다"}},
        )

    if sub == "admin":
        admin = await auth_repo.get_admin_account(db)
        if not admin:
            raise HTTPException(
                status_code=401,
                detail={"error": {"code": "INVALID_CREDENTIALS", "message": "admin 계정을 찾을 수 없습니다"}},
            )
        return admin

    emp = await auth_repo.get_employee_by_emp_no(sub, db)
    if not emp:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "사용자를 찾을 수 없습니다"}},
        )
    if emp.status == "RETIRED":
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "ACCOUNT_DISABLED", "message": "퇴직 처리된 계정입니다"}},
        )

    return emp


async def require_active_user(
    user: Union[Employee, AdminAccount] = Depends(get_current_user),
) -> Union[Employee, AdminAccount]:
    if user.is_initial_password:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "FORCE_PASSWORD_CHANGE", "message": "보안을 위해 비밀번호를 변경해 주세요"}},
        )
    return user


async def require_admin(
    user: Union[Employee, AdminAccount] = Depends(require_active_user),
) -> Union[Employee, AdminAccount]:
    if not _is_admin(user):
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "관리자 권한이 필요합니다"}},
        )
    return user


async def require_room_manager(
    user: Union[Employee, AdminAccount] = Depends(require_active_user),
) -> Union[Employee, AdminAccount]:
    if not _is_room_manager(user):
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "회의실 담당자 권한이 필요합니다"}},
        )
    return user
