from datetime import datetime, date, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HealthPoint, StressPoint, AdditionalDailyInfo, DailyAnalytics


async def build_daily_analytics(
    db: AsyncSession,
    client_id: str,
    target_date: date,
) -> DailyAnalytics:

    day_start = int(datetime.combine(target_date, datetime.min.time(),
                                      tzinfo=timezone.utc).timestamp())
    day_end = int(datetime.combine(target_date + timedelta(days=1),
                                    datetime.min.time(),
                                    tzinfo=timezone.utc).timestamp())

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