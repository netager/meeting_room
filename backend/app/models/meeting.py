from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .org import Department, Employee
    from .room import MeetingRoom


class Meeting(Base, TimestampMixin):
    __tablename__ = "meeting"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    start_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    room_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("meeting_room.id", ondelete="RESTRICT"),
        nullable=False,
    )
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("SCHEDULED", "COMPLETED", "CANCELLED", name="meeting_status_enum"),
        server_default="SCHEDULED",
        nullable=False,
    )
    dept_code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("department.code", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(
        String(6),
        ForeignKey("employee.emp_no", ondelete="RESTRICT"),
        nullable=False,
    )

    room: Mapped[MeetingRoom] = relationship("MeetingRoom", back_populates="meetings")
    department: Mapped[Department] = relationship("Department")
    creator: Mapped[Employee] = relationship(
        "Employee", foreign_keys=[created_by]
    )
    attendees: Mapped[list[MeetingAttendee]] = relationship(
        "MeetingAttendee", back_populates="meeting", cascade="all, delete-orphan"
    )
    files: Mapped[list[MeetingFile]] = relationship(
        "MeetingFile", back_populates="meeting", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "idx_meeting_room_date",
            "room_id",
            "date",
            "status",
            postgresql_where=text("status != 'CANCELLED'"),
        ),
        Index("idx_meeting_status_date", "status", "date"),
        Index("idx_meeting_dept", "dept_code"),
    )


class MeetingAttendee(Base):
    __tablename__ = "meeting_attendee"

    meeting_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("meeting.id", ondelete="CASCADE"),
        primary_key=True,
    )
    emp_no: Mapped[str] = mapped_column(
        String(6),
        ForeignKey("employee.emp_no", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="attendees")
    employee: Mapped[Employee] = relationship("Employee")

    __table_args__ = (
        Index("idx_attendee_employee", "emp_no"),
        Index("idx_attendee_meeting", "meeting_id"),
    )


class MeetingFile(Base):
    __tablename__ = "meeting_file"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    meeting_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("meeting.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(
        String(6),
        ForeignKey("employee.emp_no", ondelete="RESTRICT"),
        nullable=False,
    )
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="files")
    uploader: Mapped[Employee] = relationship("Employee")


# ── History table ────────────────────────────────────────────────────────────


class MeetingHistory(Base):
    __tablename__ = "meeting_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    change_type: Mapped[str] = mapped_column(
        Enum("CREATE", "UPDATE", "DELETE", name="change_type_enum", create_type=False),
        nullable=False,
    )
    before_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    changed_by: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False),
        server_default="now()",
        nullable=False,
    )

    __table_args__ = (
        Index("idx_meeting_history_target", "target_id", "changed_at"),
    )
