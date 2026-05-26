from __future__ import annotations

import os
import urllib.parse
import uuid
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.dependencies import require_active_user
from app.models import AdminAccount, Employee
from app.models.meeting import Meeting, MeetingAttendee
from app.repositories import file_repo
from app.schemas.meeting import MeetingFileResponse

router = APIRouter(prefix="/api/meetings", tags=["files"])


def _actor_id(user: Union[Employee, AdminAccount]) -> str:
    return "admin" if isinstance(user, AdminAccount) else user.emp_no


def _is_admin(user: Union[Employee, AdminAccount]) -> bool:
    return isinstance(user, AdminAccount) or bool(user.is_admin)


def _file_response(f) -> MeetingFileResponse:
    return MeetingFileResponse(
        id=f.id,
        original_name=f.original_name,
        mime_type=f.mime_type,
        size=f.file_size,
        uploaded_by=f.uploaded_by,
        uploaded_by_name=f.uploader.name if f.uploader else "",
        created_at=f.uploaded_at,
    )


async def _get_meeting_or_404(meeting_id: str, db: AsyncSession) -> Meeting:
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의를 찾을 수 없습니다"}},
        )
    return meeting


async def _check_is_attendee_or_creator(
    meeting: Meeting, user: Union[Employee, AdminAccount], db: AsyncSession
) -> None:
    if _is_admin(user):
        return
    if isinstance(user, Employee):
        if meeting.created_by == user.emp_no:
            return
        result = await db.execute(
            select(MeetingAttendee).where(
                MeetingAttendee.meeting_id == meeting.id,
                MeetingAttendee.emp_no == user.emp_no,
            )
        )
        if result.scalar_one_or_none() is not None:
            return
    raise HTTPException(
        status_code=403,
        detail={"error": {"code": "FORBIDDEN", "message": "이 회의의 참석자 또는 주최자만 접근할 수 있습니다"}},
    )


@router.post("/{meeting_id}/files", response_model=MeetingFileResponse, status_code=201)
async def upload_file(
    meeting_id: str,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_active_user),
):
    meeting = await _get_meeting_or_404(meeting_id, db)

    if meeting.status != "SCHEDULED":
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "MEETING_ALREADY_CLOSED",
                    "message": "예정 상태인 회의에만 파일을 추가할 수 있습니다",
                }
            },
        )

    await _check_is_attendee_or_creator(meeting, user, db)

    original_name = file.filename or "unknown"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=415,
            detail={
                "error": {
                    "code": "UNSUPPORTED_MEDIA_TYPE",
                    "message": f"허용되지 않는 파일 형식입니다. 허용: {', '.join(sorted(settings.allowed_extensions))}",
                }
            },
        )

    content = await file.read()
    if len(content) > settings.max_file_size:
        raise HTTPException(
            status_code=413,
            detail={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": f"파일 크기가 제한을 초과했습니다 (최대 {settings.max_upload_size_mb}MB)",
                }
            },
        )

    dir_path = os.path.join(settings.upload_dir, meeting_id)
    os.makedirs(dir_path, exist_ok=True)

    stored_name = f"{uuid.uuid4()}_{original_name}"
    file_path = os.path.join(dir_path, stored_name)

    try:
        with open(file_path, "wb") as fp:
            fp.write(content)
    except OSError as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "INTERNAL_ERROR", "message": "파일 저장 중 오류가 발생했습니다"}},
        ) from e

    mime_type = file.content_type or "application/octet-stream"

    try:
        meeting_file = await file_repo.create_file(
            meeting_id=meeting_id,
            data={
                "original_name": original_name,
                "stored_name": stored_name,
                "file_size": len(content),
                "mime_type": mime_type,
                "uploaded_by": _actor_id(user),
            },
            db=db,
        )
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    return _file_response(meeting_file)


@router.get("/{meeting_id}/files", response_model=list[MeetingFileResponse])
async def list_files(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_active_user),
):
    await _get_meeting_or_404(meeting_id, db)
    files = await file_repo.get_files(meeting_id, db)
    return [_file_response(f) for f in files]


@router.get("/{meeting_id}/files/{file_id}")
async def download_file(
    meeting_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_active_user),
):
    meeting = await _get_meeting_or_404(meeting_id, db)
    await _check_is_attendee_or_creator(meeting, user, db)

    meeting_file = await file_repo.get_file(file_id, db)
    if meeting_file is None or meeting_file.meeting_id != meeting_id:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "파일을 찾을 수 없습니다"}},
        )

    file_path = os.path.join(settings.upload_dir, meeting_id, meeting_file.stored_name)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "파일을 찾을 수 없습니다"}},
        )

    encoded_name = urllib.parse.quote(meeting_file.original_name, safe="")
    content_disposition = f"attachment; filename*=UTF-8''{encoded_name}"

    return FileResponse(
        path=file_path,
        media_type=meeting_file.mime_type,
        filename=meeting_file.original_name,
        headers={"Content-Disposition": content_disposition},
    )


@router.delete("/{meeting_id}/files/{file_id}")
async def delete_file(
    meeting_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_active_user),
):
    await _get_meeting_or_404(meeting_id, db)

    meeting_file = await file_repo.get_file(file_id, db)
    if meeting_file is None or meeting_file.meeting_id != meeting_id:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "파일을 찾을 수 없습니다"}},
        )

    if not _is_admin(user):
        actor = _actor_id(user)
        if meeting_file.uploaded_by != actor:
            raise HTTPException(
                status_code=403,
                detail={"error": {"code": "FORBIDDEN", "message": "파일을 삭제할 권한이 없습니다"}},
            )

    result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting and meeting.status != "SCHEDULED":
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "MEETING_ALREADY_CLOSED",
                    "message": "예정 상태인 회의에서만 파일을 삭제할 수 있습니다",
                }
            },
        )

    file_path = os.path.join(settings.upload_dir, meeting_id, meeting_file.stored_name)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass  # best-effort

    await file_repo.delete_file(file_id, db)

    return JSONResponse(content={"message": "파일이 삭제되었습니다"})
