from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import StressEpisode
from app.schemas import StressEpisodeOut
from app.routers.verify_token import verify_token

router = APIRouter(prefix="/api", tags=["episodes"])


@router.get("/stress-episodes/{client_id}", response_model=list[StressEpisodeOut])
async def get_stress_episodes(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    """Получить все стресс-эпизоды клиента (завершённые и открытые)."""
    result = await db.execute(
        select(StressEpisode)
        .where(StressEpisode.client_id == client_id)
        .order_by(StressEpisode.started_at.desc())
    )
    episodes = result.scalars().all()
    return [_episode_to_out(ep) for ep in episodes]


@router.get("/stress-episodes/{client_id}/active", response_model=StressEpisodeOut)
async def get_active_episode(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    """Получить текущий открытый эпизод (если есть)."""
    result = await db.execute(
        select(StressEpisode).where(
            StressEpisode.client_id == client_id,
            StressEpisode.ended_at.is_(None),
        )
    )
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Нет активного эпизода")
    return _episode_to_out(episode)


@router.get("/stress-episodes/{client_id}/{episode_id}", response_model=StressEpisodeOut)
async def get_stress_episode(
    client_id: str,
    episode_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    """Получить конкретный эпизод по ID."""
    result = await db.execute(
        select(StressEpisode).where(
            StressEpisode.id == episode_id,
            StressEpisode.client_id == client_id,
        )
    )
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Эпизод не найден")
    return _episode_to_out(episode)


@router.patch("/stress-episodes/{episode_id}", response_model=StressEpisodeOut)
async def update_episode(
    episode_id: int,
    user_description: str | None = None,
    approved_status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    """
    Обновить эпизод: добавить описание и/или изменить статус.
    Оба поля опциональны — можно отправить одно или оба.
    approved_status: pending / confirmed / dismissed
    """
    result = await db.execute(
        select(StressEpisode).where(StressEpisode.id == episode_id)
    )
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Эпизод не найден")

    if approved_status is not None:
        if approved_status not in ("pending", "confirmed", "dismissed"):
            raise HTTPException(
                status_code=400,
                detail="Статус должен быть: pending, confirmed, dismissed",
            )
        episode.approved_status = approved_status

    if user_description is not None:
        episode.user_description = user_description

    await db.commit()
    await db.refresh(episode)
    return _episode_to_out(episode)


def _episode_to_out(ep: StressEpisode) -> StressEpisodeOut:
    return StressEpisodeOut(
        id=ep.id,
        client_id=ep.client_id,
        started_at=ep.started_at.isoformat(),
        ended_at=ep.ended_at.isoformat() if ep.ended_at else None,
        duration_minutes=ep.duration_minutes,
        peak_stress=ep.peak_stress,
        peak_hr=ep.peak_hr,
        avg_hr=ep.avg_hr,
        avg_stress=ep.avg_stress,
        user_description=ep.user_description,
        approved_status=ep.approved_status,
    )
