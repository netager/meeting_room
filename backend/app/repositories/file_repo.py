from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.meeting import MeetingFile


async def get_files(meeting_id: str, db: AsyncSession) -> list[MeetingFile]:
    result = await db.execute(
        select(MeetingFile)
        .options(selectinload(MeetingFile.uploader))
        .where(MeetingFile.meeting_id == meeting_id)
        .order_by(MeetingFile.uploaded_at.asc())
    )
    return list(result.scalars().all())


async def get_file(file_id: str, db: AsyncSession) -> MeetingFile | None:
    result = await db.execute(
        select(MeetingFile)
        .options(selectinload(MeetingFile.uploader))
        .where(MeetingFile.id == file_id)
    )
    return result.scalar_one_or_none()


async def create_file(meeting_id: str, data: dict, db: AsyncSession) -> MeetingFile:
    file = MeetingFile(
        meeting_id=meeting_id,
        original_name=data["original_name"],
        stored_name=data["stored_name"],
        file_size=data["file_size"],
        mime_type=data["mime_type"],
        uploaded_by=data["uploaded_by"],
    )
    db.add(file)
    await db.commit()
    await db.refresh(file)

    result = await db.execute(
        select(MeetingFile)
        .options(selectinload(MeetingFile.uploader))
        .where(MeetingFile.id == file.id)
    )
    return result.scalar_one()


async def delete_file(file_id: str, db: AsyncSession) -> None:
    result = await db.execute(select(MeetingFile).where(MeetingFile.id == file_id))
    file = result.scalar_one_or_none()
    if file:
        await db.delete(file)
        await db.commit()
