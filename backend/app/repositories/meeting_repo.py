from __future__ import annotations

import datetime

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.meeting import Meeting, MeetingAttendee, MeetingHistory
from app.models.org import Employee
from app.models.room import MeetingRoom


# ── helpers ───────────────────────────────────────────────────────────────────


def _snapshot(meeting: Meeting) -> dict:
    return {
        "id": meeting.id,
        "title": meeting.title,
        "date": str(meeting.date),
        "start_time": str(meeting.start_time),
        "end_time": str(meeting.end_time),
        "room_id": meeting.room_id,
        "content": meeting.content,
        "status": meeting.status,
        "dept_code": meeting.dept_code,
        "created_by": meeting.created_by,
    }


async def _load(meeting_id: str, db: AsyncSession) -> Meeting | None:
    result = await db.execute(
        select(Meeting)
        .options(
            selectinload(Meeting.room),
            selectinload(Meeting.creator),
            selectinload(Meeting.attendees).selectinload(MeetingAttendee.employee),
        )
        .where(Meeting.id == meeting_id)
    )
    return result.scalar_one_or_none()


async def _lock_room(room_id: str, db: AsyncSession) -> MeetingRoom:
    """Acquire row-level lock on meeting_room. Raises 409 if lock unavailable."""
    try:
        result = await db.execute(
            select(MeetingRoom)
            .where(MeetingRoom.id == room_id)
            .with_for_update(nowait=True)
        )
        room = result.scalar_one_or_none()
    except OperationalError:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": "예약 처리 중입니다. 잠시 후 다시 시도하세요.",
                }
            },
        )
    if room is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의실을 찾을 수 없습니다"}},
        )
    return room


async def _check_conflict(
    room_id: str,
    meeting_date: datetime.date,
    start_time: datetime.time,
    end_time: datetime.time,
    db: AsyncSession,
    exclude_meeting_id: str | None = None,
) -> None:
    """Raise 409 if any non-cancelled meeting overlaps with the given slot."""
    q = select(Meeting).where(
        Meeting.room_id == room_id,
        Meeting.date == meeting_date,
        Meeting.status != "CANCELLED",
        Meeting.start_time < end_time,
        Meeting.end_time > start_time,
    )
    if exclude_meeting_id:
        q = q.where(Meeting.id != exclude_meeting_id)
    q = q.limit(1)

    result = await db.execute(q)
    conflict = result.scalar_one_or_none()
    if conflict:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "ROOM_BOOKING_CONFLICT",
                    "message": "해당 시간대에 이미 예약된 회의가 있습니다",
                    "detail": {
                        "conflicting_meeting": {
                            "id": conflict.id,
                            "title": conflict.title,
                            "start_time": conflict.start_time.strftime("%H:%M"),
                            "end_time": conflict.end_time.strftime("%H:%M"),
                        }
                    },
                }
            },
        )


# ── Query ─────────────────────────────────────────────────────────────────────


async def get_meetings(
    db: AsyncSession,
    emp_no: str | None = None,
    room_id: str | None = None,
    status: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Meeting], int]:
    base_q = select(Meeting).options(
        selectinload(Meeting.room),
        selectinload(Meeting.attendees).selectinload(MeetingAttendee.employee),
    )

    if emp_no:
        attendee_subq = select(MeetingAttendee.meeting_id).where(
            MeetingAttendee.emp_no == emp_no
        )
        base_q = base_q.where(
            or_(Meeting.created_by == emp_no, Meeting.id.in_(attendee_subq))
        )
    if room_id:
        base_q = base_q.where(Meeting.room_id == room_id)
    if status:
        base_q = base_q.where(Meeting.status == status)
    if date_from:
        base_q = base_q.where(Meeting.date >= date_from)
    if date_to:
        base_q = base_q.where(Meeting.date <= date_to)

    # Count with the same filters (without pagination options)
    count_q = select(func.count(Meeting.id))
    if emp_no:
        attendee_subq2 = select(MeetingAttendee.meeting_id).where(
            MeetingAttendee.emp_no == emp_no
        )
        count_q = count_q.where(
            or_(Meeting.created_by == emp_no, Meeting.id.in_(attendee_subq2))
        )
    if room_id:
        count_q = count_q.where(Meeting.room_id == room_id)
    if status:
        count_q = count_q.where(Meeting.status == status)
    if date_from:
        count_q = count_q.where(Meeting.date >= date_from)
    if date_to:
        count_q = count_q.where(Meeting.date <= date_to)

    total = await db.scalar(count_q) or 0

    base_q = base_q.order_by(Meeting.date.desc(), Meeting.start_time.asc())
    base_q = base_q.offset((page - 1) * size).limit(size)

    result = await db.execute(base_q)
    return list(result.scalars().all()), total


async def get_meeting(meeting_id: str, db: AsyncSession) -> Meeting | None:
    return await _load(meeting_id, db)


# ── Mutations ─────────────────────────────────────────────────────────────────


async def create_meeting(data: dict, created_by: str, db: AsyncSession) -> Meeting:
    room_id = data["room_id"]
    meeting_date: datetime.date = data["meeting_date"]
    start_time: datetime.time = data["start_time"]
    end_time: datetime.time = data["end_time"]

    room = await _lock_room(room_id, db)

    if room.status != "NORMAL":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "ROOM_NOT_AVAILABLE",
                    "message": "회의실이 사용 불가 상태입니다",
                }
            },
        )

    await _check_conflict(room_id, meeting_date, start_time, end_time, db)

    creator_result = await db.execute(
        select(Employee).where(Employee.emp_no == created_by)
    )
    creator = creator_result.scalar_one()

    meeting = Meeting(
        title=data["title"],
        date=meeting_date,
        start_time=start_time,
        end_time=end_time,
        room_id=room_id,
        content=data.get("agenda"),
        status="SCHEDULED",
        dept_code=creator.dept_code,
        created_by=created_by,
    )
    db.add(meeting)
    await db.flush()

    db.add(MeetingAttendee(meeting_id=meeting.id, emp_no=created_by))
    await db.flush()

    db.add(
        MeetingHistory(
            target_id=meeting.id,
            change_type="CREATE",
            before_data=None,
            after_data=_snapshot(meeting),
            changed_by=created_by,
        )
    )
    await db.commit()

    loaded = await _load(meeting.id, db)
    assert loaded is not None
    return loaded


async def update_meeting(
    meeting_id: str,
    data: dict,
    updated_by: str,
    db: AsyncSession,
    is_admin: bool = False,
) -> Meeting:
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의를 찾을 수 없습니다"}},
        )

    if not is_admin and meeting.created_by != updated_by:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "회의 수정 권한이 없습니다"}},
        )

    if meeting.status != "SCHEDULED":
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "MEETING_ALREADY_CLOSED",
                    "message": "완료 또는 취소된 회의는 수정할 수 없습니다",
                }
            },
        )

    before = _snapshot(meeting)

    new_room_id = data.get("room_id", meeting.room_id)
    new_date = data.get("meeting_date", meeting.date)
    new_start = data.get("start_time", meeting.start_time)
    new_end = data.get("end_time", meeting.end_time)

    needs_conflict_check = (
        new_room_id != meeting.room_id
        or new_date != meeting.date
        or new_start != meeting.start_time
        or new_end != meeting.end_time
    )

    if needs_conflict_check:
        await _lock_room(new_room_id, db)
        new_room_result = await db.execute(
            select(MeetingRoom).where(MeetingRoom.id == new_room_id)
        )
        new_room = new_room_result.scalar_one_or_none()
        if new_room and new_room.status != "NORMAL":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "ROOM_NOT_AVAILABLE",
                        "message": "회의실이 사용 불가 상태입니다",
                    }
                },
            )
        await _check_conflict(
            new_room_id, new_date, new_start, new_end, db, exclude_meeting_id=meeting_id
        )

    if "title" in data and data["title"] is not None:
        meeting.title = data["title"]
    if "room_id" in data and data["room_id"] is not None:
        meeting.room_id = data["room_id"]
    if "meeting_date" in data and data["meeting_date"] is not None:
        meeting.date = data["meeting_date"]
    if "start_time" in data and data["start_time"] is not None:
        meeting.start_time = data["start_time"]
    if "end_time" in data and data["end_time"] is not None:
        meeting.end_time = data["end_time"]
    if "agenda" in data:
        meeting.content = data["agenda"]

    await db.flush()

    db.add(
        MeetingHistory(
            target_id=meeting.id,
            change_type="UPDATE",
            before_data=before,
            after_data=_snapshot(meeting),
            changed_by=updated_by,
        )
    )
    await db.commit()

    loaded = await _load(meeting.id, db)
    assert loaded is not None
    return loaded


async def cancel_meeting(
    meeting_id: str,
    cancelled_by: str,
    db: AsyncSession,
    is_admin: bool = False,
) -> Meeting:
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의를 찾을 수 없습니다"}},
        )

    if not is_admin and meeting.created_by != cancelled_by:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "회의 취소 권한이 없습니다"}},
        )

    if meeting.status != "SCHEDULED":
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "MEETING_ALREADY_CLOSED",
                    "message": "이미 완료 또는 취소된 회의입니다",
                }
            },
        )

    before = _snapshot(meeting)
    meeting.status = "CANCELLED"
    await db.flush()

    db.add(
        MeetingHistory(
            target_id=meeting.id,
            change_type="UPDATE",
            before_data=before,
            after_data=_snapshot(meeting),
            changed_by=cancelled_by,
        )
    )
    await db.commit()

    loaded = await _load(meeting.id, db)
    assert loaded is not None
    return loaded


async def complete_meeting(
    meeting_id: str,
    completed_by: str,
    db: AsyncSession,
) -> Meeting:
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의를 찾을 수 없습니다"}},
        )

    if meeting.status != "SCHEDULED":
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "MEETING_ALREADY_CLOSED",
                    "message": "이미 완료 또는 취소된 회의입니다",
                }
            },
        )

    before = _snapshot(meeting)
    meeting.status = "COMPLETED"
    await db.flush()

    db.add(
        MeetingHistory(
            target_id=meeting.id,
            change_type="UPDATE",
            before_data=before,
            after_data=_snapshot(meeting),
            changed_by=completed_by,
        )
    )
    await db.commit()

    loaded = await _load(meeting.id, db)
    assert loaded is not None
    return loaded


# ── Attendees ─────────────────────────────────────────────────────────────────


async def get_attendees(meeting_id: str, db: AsyncSession) -> list[MeetingAttendee]:
    result = await db.execute(
        select(MeetingAttendee)
        .options(selectinload(MeetingAttendee.employee))
        .where(MeetingAttendee.meeting_id == meeting_id)
    )
    return list(result.scalars().all())


async def add_attendee(
    meeting_id: str, emp_no: str, added_by: str, db: AsyncSession
) -> MeetingAttendee:
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의를 찾을 수 없습니다"}},
        )

    if meeting.status != "SCHEDULED":
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "MEETING_ALREADY_CLOSED",
                    "message": "완료 또는 취소된 회의에는 참석자를 추가할 수 없습니다",
                }
            },
        )

    existing = await db.scalar(
        select(func.count()).where(
            MeetingAttendee.meeting_id == meeting_id,
            MeetingAttendee.emp_no == emp_no,
        )
    )
    if existing and existing > 0:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "CONFLICT", "message": "이미 참석자로 등록된 직원입니다"}},
        )

    attendee = MeetingAttendee(meeting_id=meeting_id, emp_no=emp_no)
    db.add(attendee)
    await db.commit()
    await db.refresh(attendee)

    result = await db.execute(
        select(MeetingAttendee)
        .options(selectinload(MeetingAttendee.employee))
        .where(
            MeetingAttendee.meeting_id == meeting_id,
            MeetingAttendee.emp_no == emp_no,
        )
    )
    return result.scalar_one()


async def remove_attendee(
    meeting_id: str, emp_no: str, removed_by: str, db: AsyncSession
) -> None:
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "회의를 찾을 수 없습니다"}},
        )

    if meeting.status != "SCHEDULED":
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "MEETING_ALREADY_CLOSED",
                    "message": "완료 또는 취소된 회의에서는 참석자를 삭제할 수 없습니다",
                }
            },
        )

    if meeting.created_by == emp_no:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "회의 주최자는 참석자에서 삭제할 수 없습니다",
                }
            },
        )

    result = await db.execute(
        select(MeetingAttendee).where(
            MeetingAttendee.meeting_id == meeting_id,
            MeetingAttendee.emp_no == emp_no,
        )
    )
    attendee = result.scalar_one_or_none()
    if attendee is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "참석자를 찾을 수 없습니다"}},
        )

    await db.delete(attendee)
    await db.commit()
