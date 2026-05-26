from __future__ import annotations

import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.room import (
    MeetingRoom,
    MeetingRoomHistory,
    RoomEquipment,
    RoomEquipmentHistory,
)
from app.models.meeting import Meeting


# ── helpers ───────────────────────────────────────────────────────────────────


def _room_to_dict(room: MeetingRoom) -> dict:
    return {
        "id": room.id,
        "name": room.name,
        "location": room.location,
        "status": room.status,
        "dept_code": room.dept_code,
    }


def _equip_to_dict(eq: RoomEquipment) -> dict:
    return {
        "id": eq.id,
        "room_id": eq.room_id,
        "name": eq.name,
        "quantity": eq.quantity,
        "note": eq.note,
    }


# ── MeetingRoom ───────────────────────────────────────────────────────────────


async def get_meeting_rooms(
    db: AsyncSession,
    status_filter: list[str] | None = None,
) -> list[MeetingRoom]:
    q = select(MeetingRoom).options(selectinload(MeetingRoom.equipment))
    if status_filter:
        q = q.where(MeetingRoom.status.in_(status_filter))
    q = q.order_by(MeetingRoom.name)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_meeting_room(room_id: str, db: AsyncSession) -> MeetingRoom | None:
    result = await db.execute(
        select(MeetingRoom)
        .options(selectinload(MeetingRoom.equipment))
        .where(MeetingRoom.id == room_id)
    )
    return result.scalar_one_or_none()


async def create_meeting_room(
    data: dict, changed_by: str, db: AsyncSession
) -> MeetingRoom:
    room = MeetingRoom(
        name=data["name"],
        location=data["location"],
        dept_code=data["dept_code"],
    )
    db.add(room)
    await db.flush()

    history = MeetingRoomHistory(
        target_id=room.id,
        change_type="CREATE",
        before_data=None,
        after_data=_room_to_dict(room),
        changed_by=changed_by,
    )
    db.add(history)
    await db.commit()
    await db.refresh(room)
    # reload equipment relationship
    result = await db.execute(
        select(MeetingRoom)
        .options(selectinload(MeetingRoom.equipment))
        .where(MeetingRoom.id == room.id)
    )
    return result.scalar_one()


async def update_meeting_room(
    room_id: str,
    data: dict,
    changed_by: str,
    db: AsyncSession,
    is_admin: bool = False,
) -> tuple[MeetingRoom, list[str]]:
    room = await get_meeting_room(room_id, db)
    if room is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의실을 찾을 수 없습니다"}},
        )

    new_status = data.get("status")

    # CLOSED → NORMAL/TEMP_CLOSED: admin only
    if room.status == "CLOSED" and new_status in ("NORMAL", "TEMP_CLOSED"):
        if not is_admin:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "폐쇄 상태에서 복원은 관리자만 가능합니다",
                    }
                },
            )

    before = _room_to_dict(room)
    for field, value in data.items():
        if value is not None:
            setattr(room, field, value)
    await db.flush()

    warnings: list[str] = []
    # If status changed away from NORMAL, warn about existing SCHEDULED meetings
    if new_status and new_status != "NORMAL":
        count = await db.scalar(
            select(func.count()).where(
                Meeting.room_id == room_id,
                Meeting.status == "SCHEDULED",
            )
        )
        if count and count > 0:
            warnings.append(
                f"해당 회의실에 예정된 회의가 {count}건 있습니다. 직접 처리해 주세요."
            )

    history = MeetingRoomHistory(
        target_id=room.id,
        change_type="UPDATE",
        before_data=before,
        after_data=_room_to_dict(room),
        changed_by=changed_by,
    )
    db.add(history)
    await db.commit()

    result = await db.execute(
        select(MeetingRoom)
        .options(selectinload(MeetingRoom.equipment))
        .where(MeetingRoom.id == room.id)
    )
    refreshed = result.scalar_one()
    return refreshed, warnings


async def delete_meeting_room(
    room_id: str, changed_by: str, db: AsyncSession
) -> None:
    room = await get_meeting_room(room_id, db)
    if room is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의실을 찾을 수 없습니다"}},
        )

    equip_count = await db.scalar(
        select(func.count()).where(RoomEquipment.room_id == room_id)
    )
    if equip_count and equip_count > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": "집기가 등록된 회의실은 삭제할 수 없습니다. 먼저 집기를 삭제해 주세요.",
                }
            },
        )

    meeting_count = await db.scalar(
        select(func.count()).where(Meeting.room_id == room_id)
    )
    if meeting_count and meeting_count > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": "연결된 회의가 있는 회의실은 삭제할 수 없습니다.",
                }
            },
        )

    before = _room_to_dict(room)
    history = MeetingRoomHistory(
        target_id=room.id,
        change_type="DELETE",
        before_data=before,
        after_data=None,
        changed_by=changed_by,
    )
    db.add(history)
    await db.delete(room)
    await db.commit()


# ── RoomEquipment ─────────────────────────────────────────────────────────────


async def get_equipment_list(room_id: str, db: AsyncSession) -> list[RoomEquipment]:
    result = await db.execute(
        select(RoomEquipment)
        .where(RoomEquipment.room_id == room_id)
        .order_by(RoomEquipment.name)
    )
    return list(result.scalars().all())


async def get_equipment(eq_id: str, db: AsyncSession) -> RoomEquipment | None:
    result = await db.execute(
        select(RoomEquipment).where(RoomEquipment.id == eq_id)
    )
    return result.scalar_one_or_none()


async def create_equipment(
    room_id: str, data: dict, changed_by: str, db: AsyncSession
) -> RoomEquipment:
    # Check room exists
    room = await get_meeting_room(room_id, db)
    if room is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의실을 찾을 수 없습니다"}},
        )

    # Check duplicate name
    existing = await db.scalar(
        select(func.count()).where(
            RoomEquipment.room_id == room_id,
            RoomEquipment.name == data["name"],
        )
    )
    if existing and existing > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": "같은 이름의 집기가 이미 등록되어 있습니다",
                }
            },
        )

    eq = RoomEquipment(
        room_id=room_id,
        name=data["name"],
        quantity=data["quantity"],
        note=data.get("note"),
    )
    db.add(eq)
    await db.flush()

    history = RoomEquipmentHistory(
        target_id=eq.id,
        change_type="CREATE",
        before_data=None,
        after_data=_equip_to_dict(eq),
        changed_by=changed_by,
    )
    db.add(history)
    await db.commit()
    await db.refresh(eq)
    return eq


async def update_equipment(
    eq_id: str, data: dict, changed_by: str, db: AsyncSession
) -> RoomEquipment:
    eq = await get_equipment(eq_id, db)
    if eq is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "집기를 찾을 수 없습니다"}},
        )

    before = _equip_to_dict(eq)
    for field, value in data.items():
        if value is not None:
            setattr(eq, field, value)
    await db.flush()

    history = RoomEquipmentHistory(
        target_id=eq.id,
        change_type="UPDATE",
        before_data=before,
        after_data=_equip_to_dict(eq),
        changed_by=changed_by,
    )
    db.add(history)
    await db.commit()
    await db.refresh(eq)
    return eq


async def delete_equipment(eq_id: str, changed_by: str, db: AsyncSession) -> None:
    eq = await get_equipment(eq_id, db)
    if eq is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "집기를 찾을 수 없습니다"}},
        )

    before = _equip_to_dict(eq)
    history = RoomEquipmentHistory(
        target_id=eq.id,
        change_type="DELETE",
        before_data=before,
        after_data=None,
        changed_by=changed_by,
    )
    db.add(history)
    await db.delete(eq)
    await db.commit()


# ── Schedule ──────────────────────────────────────────────────────────────────


async def get_room_schedule(
    room_id: str, date: datetime.date, db: AsyncSession
) -> list[dict]:
    result = await db.execute(
        select(Meeting)
        .where(
            Meeting.room_id == room_id,
            Meeting.date == date,
            Meeting.status == "SCHEDULED",
        )
        .order_by(Meeting.start_time)
    )
    meetings = list(result.scalars().all())
    return [
        {
            "meeting_id": m.id,
            "title": m.title,
            "start_time": m.start_time.strftime("%H:%M"),
            "end_time": m.end_time.strftime("%H:%M"),
        }
        for m in meetings
    ]
