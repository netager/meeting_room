import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Shared enum type for history tables — created once, reused across all *_history tables
CHANGE_TYPE_ENUM = Enum("CREATE", "UPDATE", "DELETE", name="change_type_enum")

__all__ = ["Base", "TimestampMixin", "CHANGE_TYPE_ENUM", "Optional"]
