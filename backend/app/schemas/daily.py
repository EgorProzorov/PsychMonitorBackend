from pydantic import BaseModel
from typing import Optional


class DailySummaryIn(BaseModel):
    client_id: str
    ts: int
    steps: Optional[int] = None
    calories: Optional[int] = None
    distance_cm: Optional[int] = None
    active_minutes: Optional[int] = None


class DailySummariesRequest(BaseModel):
    daily_summaries: list[DailySummaryIn]


class DailySummaryOut(BaseModel):
    id: int
    client_id: str
    timestamp: int
    steps: Optional[int]
    calories: Optional[int]
    distance: Optional[int]
    active_minutes: Optional[int]

    class Config:
        from_attributes = True
