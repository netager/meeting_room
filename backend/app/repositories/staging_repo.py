from __future__ import annotations

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmployeeStaging


async def get_all_staging(db: AsyncSession) -> list[EmployeeStaging]:
    result = await db.execute(select(EmployeeStaging).order_by(EmployeeStaging.emp_no))
    return list(result.scalars().all())


async def count_staging(db: AsyncSession) -> int:
    result = await db.execute(select(EmployeeStaging))
    return len(result.scalars().all())


async def truncate_staging(db: AsyncSession) -> None:
    await db.execute(text("TRUNCATE TABLE employee_staging"))


async def upsert_staging(records: list[dict], db: AsyncSession) -> None:
    """Mock용: Admin UI에서 스테이징 직접 편집."""
    for record in records:
        stmt = (
            pg_insert(EmployeeStaging)
            .values(
                emp_no=record["emp_no"],
                name=record["name"],
                dept_code=record["dept_code"],
                team_code=record.get("team_code"),
                rank=record.get("rank"),
            )
            .on_conflict_do_update(
                index_elements=["emp_no"],
                set_={
                    "name": record["name"],
                    "dept_code": record["dept_code"],
                    "team_code": record.get("team_code"),
                    "rank": record.get("rank"),
                },
            )
        )
        await db.execute(stmt)
    await db.commit()


async def get_staging_record(emp_no: str, db: AsyncSession) -> EmployeeStaging | None:
    result = await db.execute(
        select(EmployeeStaging).where(EmployeeStaging.emp_no == emp_no)
    )
    return result.scalar_one_or_none()


async def delete_staging_record(emp_no: str, db: AsyncSession) -> None:
    await db.execute(
        delete(EmployeeStaging).where(EmployeeStaging.emp_no == emp_no)
    )
    await db.commit()
