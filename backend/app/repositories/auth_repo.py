from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminAccount, AuditLog, Employee, UsedToken


async def get_employee_by_emp_no(emp_no: str, db: AsyncSession) -> Optional[Employee]:
    result = await db.execute(select(Employee).where(Employee.emp_no == emp_no))
    return result.scalar_one_or_none()


async def get_admin_account(db: AsyncSession) -> Optional[AdminAccount]:
    result = await db.execute(select(AdminAccount))
    return result.scalar_one_or_none()


async def create_admin_account_if_not_exists(db: AsyncSession) -> None:
    from app.services.auth_service import hash_password

    existing = await get_admin_account(db)
    if existing is None:
        admin = AdminAccount(
            username="admin",
            password_hash=hash_password("admin123"),
            is_initial_password=True,
        )
        db.add(admin)
        await db.commit()


async def increment_login_fail(emp_no: str, db: AsyncSession) -> int:
    emp = await get_employee_by_emp_no(emp_no, db)
    if emp is None:
        return 0
    emp.login_fail_count = (emp.login_fail_count or 0) + 1
    await db.commit()
    return emp.login_fail_count


async def lock_account(emp_no: str, until: datetime.datetime, db: AsyncSession) -> None:
    emp = await get_employee_by_emp_no(emp_no, db)
    if emp:
        emp.locked_until = until
        await db.commit()


async def reset_login_fail(emp_no: str, db: AsyncSession) -> None:
    emp = await get_employee_by_emp_no(emp_no, db)
    if emp:
        emp.login_fail_count = 0
        emp.locked_until = None
        await db.commit()


async def record_audit(log: AuditLog, db: AsyncSession) -> None:
    db.add(log)
    await db.commit()


async def is_token_used(jti: str, db: AsyncSession) -> bool:
    result = await db.execute(select(UsedToken).where(UsedToken.jti == jti))
    return result.scalar_one_or_none() is not None


async def mark_token_used(jti: str, expires_at: datetime.datetime, db: AsyncSession) -> None:
    token = UsedToken(jti=jti, expires_at=expires_at)
    db.add(token)
    await db.commit()
