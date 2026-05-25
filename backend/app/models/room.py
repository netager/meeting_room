from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from .base import Base

if TYPE_CHECKING:
    from .org import Department
    from .meeting import Meeting


class MeetingRoom(Base):
    __tablename__ = "meeting_room"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("NORMAL", "TEMP_CLOSED", "CLOSED", name="room_status_enum"),
        server_default="NORMAL",
        nullable=False,
    )
    dept_code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("department.code", ondelete="RESTRICT"),
        nullable=False,
    )

    department: Mapped[Department] = relationship(
        "Department", back_populates="meeting_rooms"
    )
    equipment: Mapped[list[RoomEquipment]] = relationship(
        "RoomEquipment", back_populates="room", cascade="all, delete-orphan"
    )
    meetings: Mapped[list[Meeting]] = relationship(
        "Meeting", back_populates="room"
    )


class RoomEquipment(Base):
    __tablename__ = "room_equipment"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    room_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("meeting_room.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    room: Mapped[MeetingRoom] = relationship("MeetingRoom", back_populates="equipment")

    __table_args__ = (
        UniqueConstraint("room_id", "name", name="uq_room_equipment_name"),
        CheckConstraint("quantity >= 1", name="ck_room_equipment_quantity"),
    )


# ── History tables ──────────────────────────────────────────────────────────


class MeetingRoomHistory(Base):
    __tablename__ = "meeting_room_history"

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
        Index("idx_room_history_target", "target_id", "changed_at"),
    )


class RoomEquipmentHistory(Base):
    __tablename__ = "room_equipment_history"

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
        Index("idx_equip_history_target", "target_id", "changed_at"),
    )
