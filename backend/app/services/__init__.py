from datetime import datetime, date, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HealthPoint, StressPoint, AdditionalDailyInfo, DailyAnalytics, StressEpisode


async def build_daily_analytics(
    db: AsyncSession,
    client_id: str,
    target_date: date,
) -> DailyAnalytics:

    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())

    # HR и Body Battery
    hp_result = await db.execute(
        select(
            func.avg(HealthPoint.hr).label("hr_avg"),
            func.min(HealthPoint.hr).label("hr_min"),
            func.max(HealthPoint.hr).label("hr_max"),
            func.avg(HealthPoint.body_battery).label("bb_avg"),
            func.min(HealthPoint.body_battery).label("bb_min"),
            func.max(HealthPoint.body_battery).label("bb_max"),
        ).where(
            HealthPoint.client_id == client_id,
            HealthPoint.timestamp >= day_start,
            HealthPoint.timestamp < day_end,
            HealthPoint.hr.is_not(None),
        )
    )
    hp_row = hp_result.one()

    # Стресс
    sp_result = await db.execute(
        select(
            func.avg(StressPoint.value).label("stress_avg"),
            func.min(StressPoint.value).label("stress_min"),
            func.max(StressPoint.value).label("stress_max"),
        ).where(
            StressPoint.client_id == client_id,
            StressPoint.timestamp >= day_start,
            StressPoint.timestamp < day_end,
        )
    )
    sp_row = sp_result.one()

    # Зоны стресса
    MINUTES_PER_POINT = 3
    zones = {"rest": 0, "low": 0, "med": 0, "high": 0}
    zone_result = await db.execute(
        select(StressPoint.value).where(
            StressPoint.client_id == client_id,
            StressPoint.timestamp >= day_start,
            StressPoint.timestamp < day_end,
        )
    )
    for (value,) in zone_result:
        if value <= 25:
            zones["rest"] += MINUTES_PER_POINT
        elif value <= 50:
            zones["low"] += MINUTES_PER_POINT
        elif value <= 75:
            zones["med"] += MINUTES_PER_POINT
        else:
            zones["high"] += MINUTES_PER_POINT

    # Суточные данные
    ds_result = await db.execute(
        select(AdditionalDailyInfo).where(
            AdditionalDailyInfo.client_id == client_id,
            AdditionalDailyInfo.timestamp >= day_start,
            AdditionalDailyInfo.timestamp < day_end,
        ).order_by(AdditionalDailyInfo.timestamp.desc()).limit(1)
    )
    ds = ds_result.scalar_one_or_none()

    # Аномалии
    anomalies = 0
    high_hr = await db.execute(
        select(func.count()).where(
            HealthPoint.client_id == client_id,
            HealthPoint.timestamp >= day_start,
            HealthPoint.timestamp < day_end,
            HealthPoint.hr > 120,
        )
    )
    anomalies += high_hr.scalar() or 0

    high_stress = await db.execute(
        select(func.count()).where(
            StressPoint.client_id == client_id,
            StressPoint.timestamp >= day_start,
            StressPoint.timestamp < day_end,
            StressPoint.value > 75,
        )
    )
    anomalies += high_stress.scalar() or 0

    # Создаём или обновляем
    existing = await db.execute(
        select(DailyAnalytics).where(
            DailyAnalytics.client_id == client_id,
            DailyAnalytics.date == target_date,
        )
    )
    analytics = existing.scalar_one_or_none()

    if analytics is None:
        analytics = DailyAnalytics(client_id=client_id, date=target_date)
        db.add(analytics)

    analytics.hr_avg = round(hp_row.hr_avg, 1) if hp_row.hr_avg else None
    analytics.hr_min = hp_row.hr_min
    analytics.hr_max = hp_row.hr_max
    analytics.bb_avg = round(hp_row.bb_avg, 1) if hp_row.bb_avg else None
    analytics.bb_min = hp_row.bb_min
    analytics.bb_max = hp_row.bb_max
    analytics.stress_avg = round(sp_row.stress_avg, 1) if sp_row.stress_avg else None
    analytics.stress_min = sp_row.stress_min
    analytics.stress_max = sp_row.stress_max
    analytics.stress_rest_time = zones["rest"]
    analytics.stress_low_time = zones["low"]
    analytics.stress_med_time = zones["med"]
    analytics.stress_high_time = zones["high"]

    if ds:
        analytics.steps = ds.steps
        analytics.calories = ds.calories
        analytics.distance = ds.distance
        analytics.active_minutes = ds.active_minutes

    analytics.anomalies_count = anomalies

    await db.commit()
    await db.refresh(analytics)
    return analytics


# ── Конфигурация детекции стресс-эпизодов ──
STRESS_THRESHOLD = 75          # порог: значение >= этого = повышенный стресс
MIN_CONSECUTIVE_POINTS = 2     # сколько точек подряд для открытия эпизода
MIN_EPISODE_DURATION_MIN = 1  # минимальная длительность (минуты) для сохранения


async def process_stress_realtime(
    db: AsyncSession,
    client_id: str,
    stress_threshold: int = STRESS_THRESHOLD,
    min_consecutive: int = MIN_CONSECUTIVE_POINTS,
    min_duration_minutes: int = MIN_EPISODE_DURATION_MIN,
) -> dict:
    """
    Реалтайм-обработка стресс-эпизодов. Вызывается после каждого POST /health-points.

    Логика:
    1. Есть ли открытый эпизод (ended_at IS NULL)?
       - Да → смотрим последнюю стресс-точку:
         - Если >= порога → обновляем peak/avg метрики эпизода
         - Если < порога → ЗАКРЫВАЕМ эпизод, проверяем длительность
           - Если длительность < минимума → удаляем эпизод
           - Если >= минимума → оставляем, статус pending
       - Нет → смотрим последние N точек:
         - Если все N >= порога → ОТКРЫВАЕМ новый эпизод

    Возвращает dict с информацией о произведённых действиях.
    """
    result = {"action": "none", "episode_id": None}

    # Проверяем, есть ли открытый эпизод
    open_ep_result = await db.execute(
        select(StressEpisode).where(
            StressEpisode.client_id == client_id,
            StressEpisode.ended_at.is_(None),
        )
    )
    open_episode = open_ep_result.scalar_one_or_none()

    # Последние точки стресса (для анализа)
    recent_result = await db.execute(
        select(StressPoint)
        .where(StressPoint.client_id == client_id)
        .order_by(StressPoint.timestamp.desc())
        .limit(min_consecutive + 1)
    )
    recent_points = list(reversed(recent_result.scalars().all()))

    if not recent_points:
        return result

    latest_point = recent_points[-1]
    is_above = latest_point.value >= stress_threshold

    if open_episode:
        if is_above:
            # Эпизод продолжается — обновляем метрики
            await _update_episode_metrics(db, open_episode, client_id)
            result = {"action": "episode_updated", "episode_id": open_episode.id}
        else:
            # Эпизод завершён — закрываем
            result = await _close_episode(
                db, open_episode, client_id, min_duration_minutes
            )
    else:
        # Нет открытого эпизода — проверяем, нужно ли открыть
        if len(recent_points) >= min_consecutive:
            last_n = recent_points[-min_consecutive:]
            all_above = all(p.value >= stress_threshold for p in last_n)

            if all_above:
                # Открываем новый эпизод
                episode_start = last_n[0].timestamp
                stress_values = [p.value for p in last_n]

                new_episode = StressEpisode(
                    client_id=client_id,
                    started_at=episode_start,
                    peak_stress=max(stress_values),
                    avg_stress=round(sum(stress_values) / len(stress_values), 1),
                )
                db.add(new_episode)
                await db.commit()
                await db.refresh(new_episode)

                # Подтягиваем HR за период
                await _update_episode_metrics(db, new_episode, client_id)

                result = {"action": "episode_opened", "episode_id": new_episode.id}

    return result


async def _update_episode_metrics(
    db: AsyncSession,
    episode: StressEpisode,
    client_id: str,
) -> None:
    """Пересчитываем peak/avg метрики открытого эпизода по всем точкам внутри него."""

    # Стресс-точки за период эпизода
    sp_result = await db.execute(
        select(StressPoint)
        .where(
            StressPoint.client_id == client_id,
            StressPoint.timestamp >= episode.started_at,
        )
        .order_by(StressPoint.timestamp.asc())
    )
    sp_points = sp_result.scalars().all()

    if sp_points:
        values = [p.value for p in sp_points]
        episode.peak_stress = max(values)
        episode.avg_stress = round(sum(values) / len(values), 1)

    # HR за период
    hr_result = await db.execute(
        select(HealthPoint)
        .where(
            HealthPoint.client_id == client_id,
            HealthPoint.timestamp >= episode.started_at,
            HealthPoint.hr.is_not(None),
        )
        .order_by(HealthPoint.timestamp.asc())
    )
    hr_points = hr_result.scalars().all()

    if hr_points:
        hr_values = [hp.hr for hp in hr_points]
        episode.peak_hr = max(hr_values)
        episode.avg_hr = round(sum(hr_values) / len(hr_values), 1)

    await db.commit()


async def _close_episode(
    db: AsyncSession,
    episode: StressEpisode,
    client_id: str,
    min_duration_minutes: int,
) -> dict:
    """Закрываем эпизод: ставим ended_at, считаем длительность, фильтруем по минимуму."""

    # Последняя точка >= порога — конец эпизода
    last_high_result = await db.execute(
        select(StressPoint)
        .where(
            StressPoint.client_id == client_id,
            StressPoint.timestamp >= episode.started_at,
            StressPoint.value >= STRESS_THRESHOLD,
        )
        .order_by(StressPoint.timestamp.desc())
        .limit(1)
    )
    last_high = last_high_result.scalar_one_or_none()

    if last_high:
        episode.ended_at = last_high.timestamp
    else:
        episode.ended_at = episode.started_at

    duration = (episode.ended_at - episode.started_at).total_seconds() / 60.0
    episode.duration_minutes = round(duration, 1)

    # Финальный пересчёт метрик
    await _update_episode_metrics(db, episode, client_id)

    if duration < min_duration_minutes:
        # Слишком короткий — удаляем
        await db.delete(episode)
        await db.commit()
        return {"action": "episode_discarded", "episode_id": episode.id, "duration_minutes": round(duration, 1)}
    else:
        # Сохраняем — готов к пуш-уведомлению
        await db.commit()
        await db.refresh(episode)
        return {"action": "episode_closed", "episode_id": episode.id, "duration_minutes": round(duration, 1)}