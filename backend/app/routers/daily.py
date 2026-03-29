from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AdditionalDailyInfo
from app.schemas import DailySummariesRequest, StatusResponse
from app.services import build_daily_analytics

router = APIRouter(prefix="/api", tags=["daily"])


@router.post("/daily-summaries", response_model=StatusResponse)
async def receive_daily_summaries(
    request: DailySummariesRequest,
    db: AsyncSession = Depends(get_db)
):
    count = 0

    for ds_in in request.daily_summaries:
        ds = AdditionalDailyInfo(
            client_id=ds_in.client_id,
            timestamp=ds_in.ts,
            steps=ds_in.steps,
            calories=ds_in.calories,
            distance=ds_in.distance_cm,
            active_minutes=ds_in.active_minutes,
        )
        db.add(ds)
        count += 1

    await db.commit()

    for ds_in in request.daily_summaries:
        target_date = datetime.fromtimestamp(ds_in.ts, tz=timezone.utc).date()
        analytics = await build_daily_analytics(db, ds_in.client_id, target_date)
        print(f"=== daily_analytics for {ds_in.client_id} on {target_date}: "
              f"hr_avg={analytics.hr_avg} stress_avg={analytics.stress_avg} "
              f"anomalies={analytics.anomalies_count} ===")

    return StatusResponse(
        status="ok",
        saved_daily_summaries=count,
    )