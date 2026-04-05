"""create stress_episodes table

Revision ID: 002
Revises: 001
Create Date: 2026-04-05
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stress_episodes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String, nullable=False, index=True),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("ended_at", sa.DateTime, nullable=True),
        sa.Column("duration_minutes", sa.Float, nullable=True),
        sa.Column("peak_stress", sa.Integer, nullable=False),
        sa.Column("peak_hr", sa.Integer, nullable=True),
        sa.Column("avg_hr", sa.Float, nullable=True),
        sa.Column("avg_stress", sa.Float, nullable=False),
        sa.Column("user_description", sa.Text, nullable=True),
        sa.Column("approved_status", sa.String, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_stress_episodes_client_started",
        "stress_episodes",
        ["client_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_table("stress_episodes")
