from __future__ import annotations

import math
from typing import Union

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import require_active_user, require_admin
from app.models import AdminAccount, Employee
from app.repositories import meeting_repo
from app.schemas.meeting import (
    AttendeeAdd,
    AttendeeItem,
    MeetingCreate,
    MeetingListItem,
    MeetingResponse,
    MeetingUpdate,
    PaginatedMeetings,
)
from app.services import notification_service

import datetime

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


def _actor_id(user: Union[Employee, AdminAccount]) -> str:
    if isinstance(user, AdminAccount):
        return "admin"
    return user.emp_no


def _is_admin(user: Union[Employee, AdminAccount]) -> bool:
    if isinstance(user, AdminAccount):
        return True
    return bool(user.is_admin)


def _meeting_response(meeting) -> MeetingResponse:
    return MeetingResponse(
        id=meeting.id,
        title=meeting.title,
        room_id=meeting.room_id,
        room_name=meeting.room.name if meeting.room else "",
        meeting_date=meeting.date,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        status=meeting.status,
        agenda=meeting.content,
        created_by=meeting.created_by,
        created_by_name=meeting.creator.name if meeting.creator else "",
        attendees=[
            AttendeeItem(
                emp_no=a.emp_no,
                name=a.employee.name if a.employee else "",
                dept_code=a.employee.dept_code if a.employee else "",
                rank=a.employee.rank if a.employee else None,
            )
            for a in meeting.attendees
        ],
    )


def _list_item(meeting) -> MeetingListItem:
    return MeetingListItem(
        id=meeting.id,
        title=meeting.title,
        room_name=meeting.room.name if meeting.room else "",
        meeting_date=meeting.date,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        status=meeting.status,
        attendee_count=len(meeting.attendees),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedMeetings)
async def list_meetings(
    my: bool = False,
    status: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    room_id: str | None = None,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_active_user),
):
    size = min(size, 100)
    filter_emp_no: str | None = None
    if my and isinstance(user, Employee):
        filter_emp_no = user.emp_no

    meetings, total = await meeting_repo.get_meetings(
        db,
        emp_no=filter_emp_no,
        room_id=room_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )
    pages = math.ceil(total / size) if total > 0 else 0
    return PaginatedMeetings(
        items=[_list_item(m) for m in meetings],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.post("", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    body: MeetingCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_active_user),
):
    if isinstance(user, AdminAccount):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "관리자 계정으로는 회의를 생성할 수 없습니다. 직원 계정을 사용해 주세요.",
                }
            },
        )
    meeting = await meeting_repo.create_meeting(
        body.model_dump(),
        created_by=user.emp_no,
        db=db,
    )
    # Notify all attendees except the creator
    recipients = [
        a.emp_no for a in meeting.attendees if a.emp_no != user.emp_no
    ]
    if recipients:
        background_tasks.add_task(
            notification_service.send_meeting_notification,
            meeting.id,
            "CREATED",
            recipients,
            db,
        )
    return _meeting_response(meeting)


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_active_user),
):
    meeting = await meeting_repo.get_meeting(meeting_id, db)
    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의를 찾을 수 없습니다"}},
        )
    return _meeting_response(meeting)


@router.put("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: str,
    body: MeetingUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_active_user),
):
    meeting = await meeting_repo.update_meeting(
        meeting_id,
        body.model_dump(exclude_none=True),
        updated_by=_actor_id(user),
        db=db,
        is_admin=_is_admin(user),
    )
    # Notify all current attendees about the update
    recipients = [a.emp_no for a in meeting.attendees]
    if recipients:
        background_tasks.add_task(
            notification_service.send_meeting_notification,
            meeting.id,
            "UPDATED",
            recipients,
            db,
        )
    return _meeting_response(meeting)


@router.delete("/{meeting_id}", response_model=MeetingResponse)
async def cancel_meeting(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_active_user),
):
    meeting = await meeting_repo.cancel_meeting(
        meeting_id,
        cancelled_by=_actor_id(user),
        db=db,
        is_admin=_is_admin(user),
    )
    # Notify all attendees (including the canceller) about cancellation
    recipients = [a.emp_no for a in meeting.attendees]
    if recipients:
        background_tasks.add_task(
            notification_service.send_meeting_notification,
            meeting.id,
            "CANCELLED",
            recipients,
            db,
        )
    return _meeting_response(meeting)


@router.post("/{meeting_id}/complete", response_model=MeetingResponse)
async def complete_meeting(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    meeting = await meeting_repo.complete_meeting(
        meeting_id,
        completed_by=_actor_id(user),
        db=db,
    )
    # Notify attendees about completion (per PRD: no notification for completion)
    # PRD §6: 상태 예정→완료: 알림 없음
    return _meeting_response(meeting)


# ── Attendees ─────────────────────────────────────────────────────────────────


@router.post("/{meeting_id}/attendees", response_model=AttendeeItem, status_code=201)
async def add_attendee(
    meeting_id: str,
    body: AttendeeAdd,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_active_user),
):
    attendee = await meeting_repo.add_attendee(meeting_id, body.emp_no, _actor_id(user), db)
    return AttendeeItem(
        emp_no=attendee.emp_no,
        name=attendee.employee.name if attendee.employee else "",
        dept_code=attendee.employee.dept_code if attendee.employee else "",
        rank=attendee.employee.rank if attendee.employee else None,
    )


@router.delete("/{meeting_id}/attendees/{emp_no}")
async def remove_attendee(
    meeting_id: str,
    emp_no: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_active_user),
):
    await meeting_repo.remove_attendee(meeting_id, emp_no, _actor_id(user), db)
    return JSONResponse(content={"message": "참석자가 삭제되었습니다"})
