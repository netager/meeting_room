from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from .base import Base


class AuditLog(Base):
    """Immutable audit trail. No UPDATE or DELETE at the ORM level."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(
        Enum(
            "LOGIN",
            "LOGIN_FAIL",
            "LOGOUT",
            "CREATE",
            "UPDATE",
            "DELETE",
            "DOWNLOAD",
            "BATCH_RUN",
            name="audit_action_enum",
        ),
        nullable=False,
    )
    target_table: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_audit_actor_ts", "actor", "created_at"),
        Index("idx_audit_target", "target_table", "target_id"),
    )


class MessageLog(Base):
    """Per-recipient notification log. Created as PENDING, sent asynchronously."""

    __tablename__ = "message_log"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    meeting_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient_emp_no: Mapped[str] = mapped_column(String(6), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "SENDING", "SENT", "FAILED", name="message_status_enum"),
        server_default="PENDING",
        nullable=False,
    )
    retry_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_message_log_recipient", "recipient_emp_no", "created_at"),
    )


class AdminAccount(Base):
    """Separate admin account, not linked to Employee ledger."""

    __tablename__ = "admin_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_initial_password: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UsedToken(Base):
    """Refresh token jti blacklist for one-time-use enforcement."""

    __tablename__ = "used_token"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
