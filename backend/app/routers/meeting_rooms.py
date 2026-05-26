from __future__ import annotations

import datetime
from typing import Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import require_active_user, require_admin, require_room_manager
from app.models import AdminAccount, Employee
from app.repositories import room_repo
from app.schemas.room import (
    MeetingRoomCreate,
    MeetingRoomResponse,
    MeetingRoomUpdate,
    MeetingRoomUpdateResponse,
    RoomEquipmentCreate,
    RoomEquipmentResponse,
    RoomEquipmentUpdate,
    ScheduleSlot,
)

router = APIRouter(prefix="/api/meeting-rooms", tags=["meeting-rooms"])


def _actor_id(user: Union[Employee, AdminAccount]) -> str:
    if isinstance(user, AdminAccount):
        return "admin"
    return user.emp_no


def _is_admin(user: Union[Employee, AdminAccount]) -> bool:
    if isinstance(user, AdminAccount):
        return True
    return bool(user.is_admin)


def _check_room_dept_access(
    user: Union[Employee, AdminAccount], room_dept_code: str
) -> None:
    """room_manager 권한 검사: 담당 부서 일치 여부 확인. admin은 예외."""
    if _is_admin(user):
        return
    if isinstance(user, Employee) and user.dept_code != room_dept_code:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "담당 부서의 회의실만 관리할 수 있습니다",
                }
            },
        )


# ── Meeting Rooms ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[MeetingRoomResponse])
async def list_meeting_rooms(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_active_user),
):
    status_filter = None
    if status:
        status_filter = [s.strip() for s in status.split(",")]
    rooms = await room_repo.get_meeting_rooms(db, status_filter=status_filter)
    return [MeetingRoomResponse.model_validate(r) for r in rooms]


@router.post("", response_model=MeetingRoomResponse, status_code=201)
async def create_meeting_room(
    body: MeetingRoomCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_room_manager),
):
    _check_room_dept_access(user, body.dept_code)
    room = await room_repo.create_meeting_room(body.model_dump(), _actor_id(user), db)
    return MeetingRoomResponse.model_validate(room)


@router.get("/{room_id}", response_model=MeetingRoomResponse)
async def get_meeting_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_active_user),
):
    room = await room_repo.get_meeting_room(room_id, db)
    if room is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의실을 찾을 수 없습니다"}},
        )
    return MeetingRoomResponse.model_validate(room)


@router.put("/{room_id}", response_model=MeetingRoomUpdateResponse)
async def update_meeting_room(
    room_id: str,
    body: MeetingRoomUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_room_manager),
):
    room = await room_repo.get_meeting_room(room_id, db)
    if room is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의실을 찾을 수 없습니다"}},
        )
    _check_room_dept_access(user, room.dept_code)

    updated_room, warnings = await room_repo.update_meeting_room(
        room_id,
        body.model_dump(exclude_none=True),
        _actor_id(user),
        db,
        is_admin=_is_admin(user),
    )
    return MeetingRoomUpdateResponse(
        room=MeetingRoomResponse.model_validate(updated_room),
        warnings=warnings,
    )


@router.delete("/{room_id}")
async def delete_meeting_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin),
):
    await room_repo.delete_meeting_room(room_id, _actor_id(user), db)
    return JSONResponse(content={"message": "회의실이 삭제되었습니다"})


@router.get("/{room_id}/schedule", response_model=list[ScheduleSlot])
async def get_room_schedule(
    room_id: str,
    date: datetime.date | None = None,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_active_user),
):
    if date is None:
        date = datetime.date.today()
    room = await room_repo.get_meeting_room(room_id, db)
    if room is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의실을 찾을 수 없습니다"}},
        )
    slots = await room_repo.get_room_schedule(room_id, date, db)
    return slots


# ── Equipment ─────────────────────────────────────────────────────────────────


@router.post("/{room_id}/equipment", response_model=RoomEquipmentResponse, status_code=201)
async def create_equipment(
    room_id: str,
    body: RoomEquipmentCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_room_manager),
):
    room = await room_repo.get_meeting_room(room_id, db)
    if room is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의실을 찾을 수 없습니다"}},
        )
    _check_room_dept_access(user, room.dept_code)
    eq = await room_repo.create_equipment(room_id, body.model_dump(), _actor_id(user), db)
    return RoomEquipmentResponse.model_validate(eq)


@router.put("/{room_id}/equipment/{eq_id}", response_model=RoomEquipmentResponse)
async def update_equipment(
    room_id: str,
    eq_id: str,
    body: RoomEquipmentUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_room_manager),
):
    room = await room_repo.get_meeting_room(room_id, db)
    if room is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의실을 찾을 수 없습니다"}},
        )
    _check_room_dept_access(user, room.dept_code)
    eq = await room_repo.update_equipment(
        eq_id, body.model_dump(exclude_none=True), _actor_id(user), db
    )
    return RoomEquipmentResponse.model_validate(eq)


@router.delete("/{room_id}/equipment/{eq_id}")
async def delete_equipment(
    room_id: str,
    eq_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_room_manager),
):
    room = await room_repo.get_meeting_room(room_id, db)
    if room is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의실을 찾을 수 없습니다"}},
        )
    _check_room_dept_access(user, room.dept_code)
    await room_repo.delete_equipment(eq_id, _actor_id(user), db)
    return JSONResponse(content={"message": "집기가 삭제되었습니다"})
