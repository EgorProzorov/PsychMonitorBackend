from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Text, DateTime, Index

from app.config import TIMEZONE
from app.database import Base


class StressEpisode(Base):
    __tablename__ = "stress_episodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String, nullable=False, index=True)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)  # NULL = эпизод ещё открыт
    duration_minutes = Column(Float, nullable=True)  # заполняется при закрытии
    peak_stress = Column(Integer, nullable=False)
    peak_hr = Column(Integer, nullable=True)
    avg_hr = Column(Float, nullable=True)
    avg_stress = Column(Float, nullable=False)
    user_description = Column(Text, nullable=True)
    approved_status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.now(TIMEZONE))

    __table_args__ = (
        Index("ix_stress_episodes_client_started", "client_id", "started_at"),
    )
