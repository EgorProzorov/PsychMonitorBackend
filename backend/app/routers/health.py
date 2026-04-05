from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import HealthPoint, StressPoint
from app.schemas import HealthPointsRequest, StatusResponse
from app.services import process_stress_realtime

from app.routers.verify_token import verify_token

router = APIRouter(prefix="/api", tags=["health"])


def ts_to_datetime(ts: int) -> datetime:
    return datetime.utcfromtimestamp(ts)

@router.post("/health-points", response_model=StatusResponse)
async def receive_health_points(
    request: HealthPointsRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token)
):
    hp_count = 0
    sp_count = 0

    for hp_in in request.health_points:
        # Пропускаем пустые точки
        if hp_in.hr is None and hp_in.body_battery is None:
            continue

    for hp_in in request.health_points:
        hp = HealthPoint(
            client_id=hp_in.client_id,
            timestamp=ts_to_datetime(hp_in.ts),
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
                timestamp=ts_to_datetime(sp_in.ts),
                value=sp_in.value,
            )
            db.add(sp)
            sp_count += 1

    await db.commit()

    # Реалтайм-детекция стресс-эпизодов для каждого клиента
    client_ids = set(hp_in.client_id for hp_in in request.health_points)
    episode_results = []
    for cid in client_ids:
        ep_result = await process_stress_realtime(db, cid)
        if ep_result["action"] != "none":
            episode_results.append(ep_result)
            print(f"=== stress episode: {ep_result} ===")

    return StatusResponse(
        status="ok",
        saved_health_points=hp_count,
        saved_stress_points=sp_count,
    )


"""
Данные для теста
{
  "health_points": [
    {
      "client_id": "test-client-001",
      "ts": 1743282000,
      "hr": 72,
      "body_battery": 85,
      "stress_points": [
        {"ts": 1743281880, "value": 22},
        {"ts": 1743282060, "value": 28}
      ]
    },
    {
      "client_id": "test-client-001",
      "ts": 1743282300,
      "hr": 78,
      "body_battery": 82,
      "stress_points": [
        {"ts": 1743282180, "value": 35},
        {"ts": 1743282360, "value": 42}
      ]
    },
    {
      "client_id": "test-client-001",
      "ts": 1743282600,
      "hr": 95,
      "body_battery": 74,
      "stress_points": [
        {"ts": 1743282480, "value": 68},
        {"ts": 1743282660, "value": 78}
      ]
    },
    {
      "client_id": "test-client-001",
      "ts": 1743282900,
      "hr": 125,
      "body_battery": 65,
      "stress_points": [
        {"ts": 1743282780, "value": 82},
        {"ts": 1743282960, "value": 91}
      ]
    },
    {
      "client_id": "test-client-001",
      "ts": 1743283200,
      "hr": 68,
      "body_battery": 70,
      "stress_points": [
        {"ts": 1743283080, "value": 45},
        {"ts": 1743283260, "value": 18}
      ]
    }
  ]
}
"""