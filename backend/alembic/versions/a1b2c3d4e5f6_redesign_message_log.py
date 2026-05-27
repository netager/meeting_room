"""redesign message_log for per-recipient notification tracking

Revision ID: a1b2c3d4e5f6
Revises: 27782fc34930
Create Date: 2026-05-27 16:15:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "27782fc34930"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old message_log table and its enum
    op.drop_table("message_log")
    op.execute("DROP TYPE IF EXISTS message_status_enum;")

    # Create new message_status_enum
    op.execute(
        "CREATE TYPE message_status_enum AS ENUM ('PENDING', 'SENDING', 'SENT', 'FAILED');"
    )

    # Create new message_log table
    op.create_table(
        "message_log",
        sa.Column(
            "id",
            sa.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("meeting_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("recipient_emp_no", sa.String(length=6), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "SENDING", "SENT", "FAILED",
                name="message_status_enum",
                create_type=False,
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_message_log_recipient",
        "message_log",
        ["recipient_emp_no", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_message_log_recipient", table_name="message_log")
    op.drop_table("message_log")
    op.execute("DROP TYPE IF EXISTS message_status_enum;")

    # Restore old enum
    op.execute("CREATE TYPE message_status_enum AS ENUM ('SENT', 'FAILED', 'MOCK');")

    # Restore old message_log table
    op.create_table(
        "message_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sender", sa.String(length=20), nullable=False),
        sa.Column(
            "recipients",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("ref_type", sa.String(length=20), nullable=True),
        sa.Column("ref_id", sa.String(length=36), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "SENT", "FAILED", "MOCK",
                name="message_status_enum",
                create_type=False,
            ),
            server_default="MOCK",
            nullable=False,
        ),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
