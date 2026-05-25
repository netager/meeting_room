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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

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
    __tablename__ = "message_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sender: Mapped[str] = mapped_column(String(20), nullable=False)
    recipients: Mapped[list] = mapped_column(JSONB, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    ref_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ref_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("SENT", "FAILED", "MOCK", name="message_status_enum"),
        server_default="MOCK",
        nullable=False,
    )
    retry_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
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
