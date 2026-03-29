from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import DailySummary
from app.schemas import DailySummariesRequest, StatusResponse

router = APIRouter(prefix="/api", tags=["daily"])


@router.post("/daily-summaries", response_model=StatusResponse)
async def receive_daily_summaries(
    request: DailySummariesRequest,
    db: AsyncSession = Depends(get_db)
):
    count = 0

    for ds_in in request.daily_summaries:
        ds = DailySummary(
            client_id=ds_in.client_id,
            ts=ds_in.ts,
            steps=ds_in.steps,
            calories=ds_in.calories,
            distance=ds_in.distance_cm,
            active_minutes=ds_in.active_minutes,
        )
        db.add(ds)
        count += 1

    await db.commit()

    return StatusResponse(
        status="ok",
        saved_daily_summaries=count,
    )
