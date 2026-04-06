from pydantic import BaseModel
from typing import Optional


class StressEpisodeOut(BaseModel):
    id: int
    client_id: str
    started_at: str
    ended_at: Optional[str]
    duration_minutes: Optional[float]
    peak_stress: int
    peak_hr: Optional[int]
    avg_hr: Optional[float]
    avg_stress: float
    user_description: Optional[str]
    approved_status: str

    class Config:
        from_attributes = True


class EpisodeDetectionConfig(BaseModel):
    stress_threshold: int = 51
    min_consecutive_points: int = 2
    min_duration_minutes: int = 30
