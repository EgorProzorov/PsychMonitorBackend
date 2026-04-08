from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Date, DateTime, Index

from app.config import TIMEZONE
from app.database import Base


class AdditionalDailyInfo(Base):
    __tablename__ = "additional_daily_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)
    steps = Column(Integer, nullable=True)
    calories = Column(Integer, nullable=True)
    distance = Column(Integer, nullable=True)
    active_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(TIMEZONE).replace(tzinfo=None))

    __table_args__ = (
        Index("ix_additional_daily_info_client_ts", "client_id", "timestamp"),
    )


class DailyAnalytics(Base):
    __tablename__ = "daily_analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)

    hr_avg = Column(Float, nullable=True)
    hr_min = Column(Integer, nullable=True)
    hr_max = Column(Integer, nullable=True)

    bb_avg = Column(Float, nullable=True)
    bb_min = Column(Integer, nullable=True)
    bb_max = Column(Integer, nullable=True)

    stress_avg = Column(Float, nullable=True)
    stress_min = Column(Integer, nullable=True)
    stress_max = Column(Integer, nullable=True)

    stress_rest_time = Column(Integer, nullable=True, default=0)
    stress_low_time = Column(Integer, nullable=True, default=0)
    stress_med_time = Column(Integer, nullable=True, default=0)
    stress_high_time = Column(Integer, nullable=True, default=0)

    steps = Column(Integer, nullable=True)
    calories = Column(Integer, nullable=True)
    distance = Column(Integer, nullable=True)
    active_minutes = Column(Integer, nullable=True)

    anomalies_count = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(TIMEZONE).replace(tzinfo=None))

    __table_args__ = (
        Index("ix_daily_analytics_client_date", "client_id", "date", unique=True),
    )
