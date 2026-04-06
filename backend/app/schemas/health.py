from pydantic import BaseModel
from typing import Optional


class StressPointIn(BaseModel):
    ts: int
    value: int


class HealthPointIn(BaseModel):
    client_id: str
    ts: int
    hr: Optional[int] = None
    body_battery: Optional[int] = None
    stress_points: list[StressPointIn] = []


class HealthPointsRequest(BaseModel):
    health_points: list[HealthPointIn]


class StressPointOut(BaseModel):
    id: int
    timestamp: int
    value: int

    class Config:
        from_attributes = True


class HealthPointOut(BaseModel):
    id: int
    client_id: str
    timestamp: int
    hr: Optional[int]
    body_battery: Optional[int]
    stress_points: list[StressPointOut] = []

    class Config:
        from_attributes = True
