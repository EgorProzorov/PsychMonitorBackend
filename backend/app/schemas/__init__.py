from pydantic import BaseModel
from typing import Optional


# --- Входящие данные с мобильного приложения ---

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


class DailySummaryIn(BaseModel):
    client_id: str
    ts: int
    steps: Optional[int] = None
    calories: Optional[int] = None
    distance_cm: Optional[int] = None
    active_minutes: Optional[int] = None


class DailySummariesRequest(BaseModel):
    daily_summaries: list[DailySummaryIn]


# --- Ответы ---

class StressPointOut(BaseModel):
    id: int
    ts: int
    value: int

    class Config:
        from_attributes = True


class HealthPointOut(BaseModel):
    id: int
    client_id: str
    ts: int
    hr: Optional[int]
    body_battery: Optional[int]
    stress_points: list[StressPointOut] = []

    class Config:
        from_attributes = True


class DailySummaryOut(BaseModel):
    id: int
    client_id: str
    ts: int
    steps: Optional[int]
    calories: Optional[int]
    distance: Optional[int]
    active_minutes: Optional[int]

    class Config:
        from_attributes = True


class StatusResponse(BaseModel):
    status: str
    saved_health_points: int = 0
    saved_stress_points: int = 0
    saved_daily_summaries: int = 0
