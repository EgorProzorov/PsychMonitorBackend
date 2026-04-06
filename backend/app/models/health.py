from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, Index
from sqlalchemy.orm import relationship
from app.database import Base


class HealthPoint(Base):
    __tablename__ = "health_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)
    hr = Column(Integer, nullable=True)
    body_battery = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    stress_points = relationship("StressPoint", back_populates="health_point")

    __table_args__ = (
        Index("ix_health_points_client_ts", "client_id", "timestamp"),
    )
