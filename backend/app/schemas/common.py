from pydantic import BaseModel


class StatusResponse(BaseModel):
    status: str
    saved_health_points: int = 0
    saved_stress_points: int = 0
    saved_daily_summaries: int = 0
