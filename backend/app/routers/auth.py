from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user
from app.repositories import auth_repo
from app.schemas.auth import LoginRequest, PasswordChangeRequest
from app.services import auth_service
from app.services.auth_service import hash_password

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    ip = _get_client_ip(request)
    ua = request.headers.get("user-agent", "")

    if body.username == "admin":
        result = await auth_service.admin_login(body.username, body.password, db, ip, ua)
    else:
        result = await auth_service.login(body.username, body.password, db, ip, ua)

    rt = result.pop("_refresh_token")
    response = JSONResponse(content=result)
    response.set_cookie(
        key="refresh_token",
        value=rt,
        httponly=True,
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        secure=settings.app_env != "development",
    )
    return response


@router.post("/logout")
async def logout() -> JSONResponse:
    response = JSONResponse(content={"message": "로그아웃 되었습니다"})
    response.delete_cookie("refresh_token", samesite="strict")
    return response


@router.post("/token/refresh")
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    rt = request.cookies.get("refresh_token")
    from fastapi import HTTPException

    if not rt:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "리프레시 토큰이 없습니다"}},
        )

    new_at = await auth_service.refresh_access_token(rt, db)
    return JSONResponse(content={"access_token": new_at, "token_type": "bearer"})


@router.post("/password/change")
async def change_password(
    body: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> JSONResponse:
    await auth_service.change_password(user, body.current_password, body.new_password, db)
    return JSONResponse(content={"message": "비밀번호가 변경되었습니다"})


@router.post("/admin/reset-password")
async def reset_admin_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    from fastapi import HTTPException

    if not settings.admin_reset_token:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_REQUEST", "message": "리셋 토큰이 설정되지 않았습니다"}},
        )

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer ") or auth_header[7:] != settings.admin_reset_token:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "잘못된 리셋 토큰입니다"}},
        )

    admin = await auth_repo.get_admin_account(db)
    if not admin:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "admin 계정이 없습니다"}},
        )

    admin.password_hash = hash_password("admin123")
    admin.is_initial_password = True
    await db.commit()

    return JSONResponse(content={"message": "admin 비밀번호가 초기화되었습니다"})
