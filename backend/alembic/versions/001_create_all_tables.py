"""create all tables

Revision ID: 001
Revises:
Create Date: 2026-03-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "health_points",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String, nullable=False, index=True),
        sa.Column("timestamp", sa.BigInteger, nullable=False),
        sa.Column("hr", sa.Integer, nullable=True),
        sa.Column("body_battery", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_health_points_client_ts", "health_points", ["client_id", "timestamp"])

    op.create_table(
        "stress_points",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String, nullable=False, index=True),
        sa.Column("health_point_id", sa.Integer, sa.ForeignKey("health_points.id"), nullable=True),
        sa.Column("timestamp", sa.BigInteger, nullable=False),
        sa.Column("value", sa.Integer, nullable=False),
    )
    op.create_index("ix_stress_points_client_ts", "stress_points", ["client_id", "timestamp"])

    op.create_table(
        "additional_daily_info",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String, nullable=False, index=True),
        sa.Column("timestamp", sa.BigInteger, nullable=False),
        sa.Column("steps", sa.Integer, nullable=True),
        sa.Column("calories", sa.Integer, nullable=True),
        sa.Column("distance", sa.Integer, nullable=True),
        sa.Column("active_minutes", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_additional_daily_info_client_ts", "additional_daily_info", ["client_id", "timestamp"])

    op.create_table(
        "daily_analytics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String, nullable=False, index=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("hr_avg", sa.Float, nullable=True),
        sa.Column("hr_min", sa.Integer, nullable=True),
        sa.Column("hr_max", sa.Integer, nullable=True),
        sa.Column("bb_avg", sa.Float, nullable=True),
        sa.Column("bb_min", sa.Integer, nullable=True),
        sa.Column("bb_max", sa.Integer, nullable=True),
        sa.Column("stress_avg", sa.Float, nullable=True),
        sa.Column("stress_min", sa.Integer, nullable=True),
        sa.Column("stress_max", sa.Integer, nullable=True),
        sa.Column("stress_rest_time", sa.Integer, default=0),
        sa.Column("stress_low_time", sa.Integer, default=0),
        sa.Column("stress_med_time", sa.Integer, default=0),
        sa.Column("stress_high_time", sa.Integer, default=0),
        sa.Column("steps", sa.Integer, nullable=True),
        sa.Column("calories", sa.Integer, nullable=True),
        sa.Column("distance", sa.Integer, nullable=True),
        sa.Column("active_minutes", sa.Integer, nullable=True),
        sa.Column("anomalies_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_daily_analytics_client_date", "daily_analytics", ["client_id", "date"], unique=True)


def downgrade() -> None:
    op.drop_table("daily_analytics")
    op.drop_table("additional_daily_info")
    op.drop_table("stress_points")
    op.drop_table("health_points")