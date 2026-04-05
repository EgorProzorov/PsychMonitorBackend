from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AdditionalDailyInfo
from app.schemas import DailySummariesRequest, StatusResponse
from app.services import build_daily_analytics

from app.routers.verify_token import verify_token

router = APIRouter(prefix="/api", tags=["daily"])


def ts_to_datetime(ts: int) -> datetime:
    return datetime.utcfromtimestamp(ts)

@router.post("/daily-summaries", response_model=StatusResponse)
async def receive_daily_summaries(
    request: DailySummariesRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token)
):
    count = 0

    for ds_in in request.daily_summaries:
        ds = AdditionalDailyInfo(
            client_id=ds_in.client_id,
            timestamp=ts_to_datetime(ds_in.ts),
            steps=ds_in.steps,
            calories=ds_in.calories,
            distance=ds_in.distance_cm,
            active_minutes=ds_in.active_minutes,
        )
        db.add(ds)
        count += 1

    await db.commit()

    for ds_in in request.daily_summaries:
        target_date = ts_to_datetime(ds_in.ts).date()
        analytics = await build_daily_analytics(db, ds_in.client_id, target_date)
        print(f"=== daily_analytics for {ds_in.client_id} on {target_date}: "
              f"hr_avg={analytics.hr_avg} stress_avg={analytics.stress_avg} "
              f"anomalies={analytics.anomalies_count} ===")

    return StatusResponse(
        status="ok",
        saved_daily_summaries=count,
    )

"""
Данные для теста
{
  "daily_summaries": [
    {
      "client_id": "test-client-001",
      "ts": 1743289200,
      "steps": 8432,
      "calories": 1850,
      "distance_cm": 650000,
      "active_minutes": 45
    }
  ]
}
"""