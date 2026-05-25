from __future__ import annotations

import datetime
import re
import uuid
from typing import Union

import bcrypt
import structlog
from fastapi import HTTPException
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AdminAccount, AuditLog, Employee
from app.repositories import auth_repo

logger = structlog.get_logger(__name__)

ALGORITHM = "HS256"
_UTC = datetime.timezone.utc


def _utcnow() -> datetime.datetime:
    """Current UTC time as timezone-naive datetime (matches DB DateTime(timezone=False))."""
    return datetime.datetime.now(_UTC).replace(tzinfo=None)


# ── Password helpers ─────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _validate_password_policy(new_pw: str, emp_no: str) -> None:
    errors = []
    if len(new_pw) < 8:
        errors.append("8자 이상이어야 합니다")
    if not any(c.isalpha() for c in new_pw):
        errors.append("영문자를 포함해야 합니다")
    if not any(c.isdigit() for c in new_pw):
        errors.append("숫자를 포함해야 합니다")
    if new_pw == emp_no:
        errors.append("행번과 동일한 비밀번호는 사용할 수 없습니다")
    if re.search(r"(.)\1{3}", new_pw):
        errors.append("연속된 동일 문자 4자 이상은 사용할 수 없습니다")
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "INVALID_PASSWORD_POLICY", "message": " / ".join(errors)}},
        )


# ── Audit log (separate session, best-effort) ────────────────────────────────


async def _log_audit(
    actor: str,
    action: str,
    target_table: str | None = None,
    target_id: str | None = None,
    detail: str | None = None,
    ip: str | None = None,
    ua: str | None = None,
) -> None:
    try:
        from app.db import AsyncSessionLocal

        async with AsyncSessionLocal() as audit_db:
            log = AuditLog(
                actor=actor,
                action=action,
                target_table=target_table,
                target_id=target_id,
                detail=detail,
                ip_address=ip,
                user_agent=ua[:500] if ua else None,
            )
            audit_db.add(log)
            await audit_db.commit()
    except Exception:
        pass  # best-effort: audit failure must not break main flow


# ── JWT helpers ───────────────────────────────────────────────────────────────


async def create_access_token(subject: str, is_admin: bool, extra: dict = {}) -> str:
    now = _utcnow()
    expire = now + datetime.timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "is_admin": is_admin,
        "exp": expire,
        "iat": now,
        **extra,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


async def create_refresh_token(subject: str) -> tuple[str, str]:
    jti = str(uuid.uuid4())
    now = _utcnow()
    expire = now + datetime.timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": subject,
        "jti": jti,
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return token, jti


async def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "토큰이 만료되었습니다"}},
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "유효하지 않은 토큰입니다"}},
        )


# ── Auth flows ────────────────────────────────────────────────────────────────


async def login(
    emp_no: str, password: str, db: AsyncSession, ip: str, ua: str
) -> dict:
    """
    Returns {"access_token", "token_type", "is_initial_password", "_refresh_token"}.
    Caller (router) must extract _refresh_token and set it as HttpOnly cookie.
    """
    emp = await auth_repo.get_employee_by_emp_no(emp_no, db)

    if emp is None:
        # Don't reveal whether emp_no exists
        await _log_audit("unknown", "LOGIN_FAIL", detail=f"emp_no={emp_no}", ip=ip, ua=ua)
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "행번 또는 비밀번호가 올바르지 않습니다"}},
        )

    if emp.status == "RETIRED":
        await _log_audit(emp_no, "LOGIN_FAIL", detail="RETIRED", ip=ip, ua=ua)
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "ACCOUNT_DISABLED", "message": "퇴직 처리된 계정입니다"}},
        )

    now = _utcnow()
    if emp.locked_until and emp.locked_until > now:
        remaining = emp.locked_until - now
        total_seconds = int(remaining.total_seconds())
        await _log_audit(emp_no, "LOGIN_FAIL", detail="LOCKED", ip=ip, ua=ua)
        raise HTTPException(
            status_code=423,
            detail={
                "error": {
                    "code": "ACCOUNT_LOCKED",
                    "message": f"계정이 잠겼습니다. {total_seconds // 60}분 {total_seconds % 60}초 후 해제됩니다",
                }
            },
            headers={"X-Unlock-At": emp.locked_until.isoformat()},
        )

    if not verify_password(password, emp.password_hash):
        fail_count = await auth_repo.increment_login_fail(emp_no, db)
        await _log_audit(emp_no, "LOGIN_FAIL", detail=f"fail_count={fail_count}", ip=ip, ua=ua)
        if fail_count >= settings.login_max_attempts:
            lock_until = _utcnow() + datetime.timedelta(
                minutes=settings.login_lock_minutes
            )
            await auth_repo.lock_account(emp_no, lock_until, db)
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "행번 또는 비밀번호가 올바르지 않습니다"}},
        )

    await auth_repo.reset_login_fail(emp_no, db)

    at = await create_access_token(
        emp_no,
        is_admin=emp.is_admin,
        extra={"is_initial_password": emp.is_initial_password},
    )
    rt, _jti = await create_refresh_token(emp_no)

    await _log_audit(emp_no, "LOGIN", ip=ip, ua=ua)

    return {
        "access_token": at,
        "token_type": "bearer",
        "is_initial_password": emp.is_initial_password,
        "_refresh_token": rt,
    }


async def admin_login(
    username: str, password: str, db: AsyncSession, ip: str, ua: str
) -> dict:
    admin = await auth_repo.get_admin_account(db)
    if admin is None or admin.username != username:
        await _log_audit("admin", "LOGIN_FAIL", detail="not_found", ip=ip, ua=ua)
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "아이디 또는 비밀번호가 올바르지 않습니다"}},
        )

    if not verify_password(password, admin.password_hash):
        await _log_audit("admin", "LOGIN_FAIL", detail="wrong_password", ip=ip, ua=ua)
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "아이디 또는 비밀번호가 올바르지 않습니다"}},
        )

    at = await create_access_token(
        "admin",
        is_admin=True,
        extra={"is_initial_password": admin.is_initial_password},
    )
    rt, _jti = await create_refresh_token("admin")

    await _log_audit("admin", "LOGIN", ip=ip, ua=ua)

    return {
        "access_token": at,
        "token_type": "bearer",
        "is_initial_password": admin.is_initial_password,
        "_refresh_token": rt,
    }


async def refresh_access_token(refresh_token: str, db: AsyncSession) -> str:
    try:
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "리프레시 토큰이 만료되었습니다"}},
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "유효하지 않은 토큰입니다"}},
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "유효하지 않은 토큰 타입입니다"}},
        )

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "잘못된 토큰 형식입니다"}},
        )

    if await auth_repo.is_token_used(jti, db):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "이미 사용된 토큰입니다"}},
        )

    sub = payload.get("sub")
    exp = payload.get("exp")
    expires_at = datetime.datetime.fromtimestamp(exp, _UTC).replace(tzinfo=None) if exp else _utcnow()
    await auth_repo.mark_token_used(jti, expires_at, db)

    is_admin = sub == "admin"
    new_at = await create_access_token(sub, is_admin=is_admin)
    return new_at


async def change_password(
    user: Union[Employee, AdminAccount],
    current_pw: str,
    new_pw: str,
    db: AsyncSession,
) -> None:
    if not verify_password(current_pw, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "현재 비밀번호가 올바르지 않습니다"}},
        )

    if isinstance(user, Employee):
        _validate_password_policy(new_pw, user.emp_no)

    user.password_hash = hash_password(new_pw)
    user.is_initial_password = False
    await db.commit()
