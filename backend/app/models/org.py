from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CHANGE_TYPE_ENUM, TimestampMixin

if TYPE_CHECKING:
    from .room import MeetingRoom


class Department(Base):
    __tablename__ = "department"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("ACTIVE", "INACTIVE", name="dept_status_enum"),
        server_default="ACTIVE",
        nullable=False,
    )

    teams: Mapped[list[Team]] = relationship("Team", back_populates="department")
    employees: Mapped[list[Employee]] = relationship(
        "Employee", back_populates="department"
    )
    meeting_rooms: Mapped[list[MeetingRoom]] = relationship(
        "MeetingRoom", back_populates="department"
    )


class Team(Base):
    __tablename__ = "team"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    dept_code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("department.code", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum("ACTIVE", "INACTIVE", name="team_status_enum"),
        server_default="ACTIVE",
        nullable=False,
    )

    department: Mapped[Department] = relationship("Department", back_populates="teams")
    employees: Mapped[list[Employee]] = relationship(
        "Employee", back_populates="team"
    )


class Employee(Base, TimestampMixin):
    __tablename__ = "employee"

    emp_no: Mapped[str] = mapped_column(String(6), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    dept_code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("department.code", ondelete="RESTRICT"),
        nullable=False,
    )
    team_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        ForeignKey("team.code", ondelete="SET NULL"),
        nullable=True,
    )
    rank: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("ACTIVE", "RETIRED", name="employee_status_enum"),
        server_default="ACTIVE",
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    is_room_manager: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    is_initial_password: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    login_fail_count: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    locked_until: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    department: Mapped[Department] = relationship(
        "Department", back_populates="employees"
    )
    team: Mapped[Optional[Team]] = relationship("Team", back_populates="employees")

    __table_args__ = (
        Index(
            "idx_employee_status",
            "status",
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "idx_employee_name",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class EmployeeStaging(Base):
    """ETL staging table: ETL tool truncates and inserts daily."""

    __tablename__ = "employee_staging"

    emp_no: Mapped[str] = mapped_column(String(6), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    dept_code: Mapped[str] = mapped_column(String(20), nullable=False)
    team_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    rank: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)


# ── History tables ──────────────────────────────────────────────────────────


class DepartmentHistory(Base):
    __tablename__ = "department_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target_id: Mapped[str] = mapped_column(String(20), nullable=False)
    change_type: Mapped[str] = mapped_column(CHANGE_TYPE_ENUM, nullable=False)
    before_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    changed_by: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False),
        server_default="now()",
        nullable=False,
    )

    __table_args__ = (
        Index("idx_dept_history_target", "target_id", "changed_at"),
    )


class TeamHistory(Base):
    __tablename__ = "team_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target_id: Mapped[str] = mapped_column(String(20), nullable=False)
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
        Index("idx_team_history_target", "target_id", "changed_at"),
    )


class EmployeeHistory(Base):
    __tablename__ = "employee_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target_id: Mapped[str] = mapped_column(String(6), nullable=False)
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
        Index("idx_employee_history_target", "target_id", "changed_at"),
    )
