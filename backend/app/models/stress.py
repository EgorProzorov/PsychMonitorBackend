from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class StressPoint(Base):
    __tablename__ = "stress_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String, nullable=False, index=True)
    health_point_id = Column(Integer, ForeignKey("health_points.id"), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    value = Column(Integer, nullable=False)

    health_point = relationship("HealthPoint", back_populates="stress_points")
    __table_args__ = (
        Index("ix_stress_points_client_ts", "client_id", "timestamp"),
        UniqueConstraint("client_id", "timestamp", name="uq_stress_client_ts"),
    )
