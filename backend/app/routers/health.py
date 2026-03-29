from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import HealthPoint, StressPoint
from app.schemas import HealthPointsRequest, StatusResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.post("/health-points", response_model=StatusResponse)
async def receive_health_points(
    request: HealthPointsRequest,
    db: AsyncSession = Depends(get_db)
):
    hp_count = 0
    sp_count = 0

    for hp_in in request.health_points:
        hp = HealthPoint(
            client_id=hp_in.client_id,
            timestamp=hp_in.ts,
            hr=hp_in.hr,
            body_battery=hp_in.body_battery,
        )
        db.add(hp)
        await db.flush()
        hp_count += 1

        for sp_in in hp_in.stress_points:
            sp = StressPoint(
                client_id=hp_in.client_id,
                health_point_id=hp.id,
                timestamp=sp_in.ts,
                value=sp_in.value,
            )
            db.add(sp)
            sp_count += 1

    await db.commit()

    return StatusResponse(
        status="ok",
        saved_health_points=hp_count,
        saved_stress_points=sp_count,
    )