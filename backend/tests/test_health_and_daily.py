"""
Тесты для POST /api/health-points и POST /api/daily-summaries.

Запуск:
  cd backend
  source venv/bin/activate
  python -m pytest tests/test_health_and_daily.py -v
"""
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_health_daily.db"
os.environ["API_TOKEN"] = "test-token"

import pytest
import pytest_asyncio
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import event, select

from app.database import Base, get_db
from app.main import app
from app.models import HealthPoint, StressPoint, AdditionalDailyInfo, DailyAnalytics

# Тестовый engine (SQLite)
test_engine = create_async_engine("sqlite+aiosqlite:///./test_health_daily.db", echo=False)
test_session = async_sessionmaker(test_engine, expire_on_commit=False)


@event.listens_for(test_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


async def override_get_db():
    async with test_session() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db

AUTH_HEADERS = {"Authorization": "Bearer test-token"}
CLIENT_ID = "test-client-001"
# 5 апреля 2026 10:00 UTC
BASE_TS = int(datetime(2026, 4, 5, 10, 0, 0).timestamp())


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    if os.path.exists("./test_health_daily.db"):
        os.remove("./test_health_daily.db")


# ═══════════════════════════════════════════
#  POST /api/health-points
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_point_saves_correctly():
    """
    Проверяем базовый сценарий сохранения одной health point с двумя stress points.
    Отправляем POST /api/health-points с hr=72, body_battery=85 и двумя стресс-точками (35, 42).
    Убеждаемся, что:
    - Ответ 200 с корректными счётчиками (1 health point, 2 stress points)
    - В БД записался HealthPoint с правильными hr и body_battery
    - В БД записались 2 StressPoint с правильными value и привязкой к client_id
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "health_points": [
                {
                    "client_id": CLIENT_ID,
                    "ts": BASE_TS,
                    "hr": 72,
                    "body_battery": 85,
                    "stress_points": [
                        {"ts": BASE_TS, "value": 35},
                        {"ts": BASE_TS + 180, "value": 42},
                    ],
                }
            ]
        }
        resp = await client.post("/api/health-points", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["saved_health_points"] == 1
        assert data["saved_stress_points"] == 2

    # Проверяем в БД
    async with test_session() as s:
        hp = (await s.execute(
            select(HealthPoint).where(HealthPoint.client_id == CLIENT_ID)
        )).scalar_one()
        assert hp.hr == 72
        assert hp.body_battery == 85

        sps = (await s.execute(
            select(StressPoint).where(StressPoint.client_id == CLIENT_ID)
            .order_by(StressPoint.timestamp.asc())
        )).scalars().all()
        assert len(sps) == 2
        assert sps[0].value == 35
        assert sps[1].value == 42


@pytest.mark.asyncio
async def test_multiple_health_points_batch():
    """
    Проверяем, что батч-отправка (несколько health points в одном запросе) работает корректно.
    Отправляем 5 health points с интервалом 3 мин, каждый с одной stress point.
    Убеждаемся, что:
    - Ответ 200, saved_health_points=5, saved_stress_points=5
    - В БД записались все 5 HealthPoint для данного client_id
    Это имитирует реальный сценарий: iOS-приложение накапливает буфер и шлёт пачкой.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "health_points": [
                {
                    "client_id": CLIENT_ID,
                    "ts": BASE_TS + i * 180,
                    "hr": 70 + i,
                    "body_battery": 80 - i,
                    "stress_points": [{"ts": BASE_TS + i * 180, "value": 30 + i * 5}],
                }
                for i in range(5)
            ]
        }
        resp = await client.post("/api/health-points", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["saved_health_points"] == 5
        assert resp.json()["saved_stress_points"] == 5

    async with test_session() as s:
        count = len((await s.execute(
            select(HealthPoint).where(HealthPoint.client_id == CLIENT_ID)
        )).scalars().all())
        assert count == 5


@pytest.mark.asyncio
async def test_health_points_without_auth():
    """
    Проверяем, что эндпоинт /api/health-points защищён Bearer-токеном.
    Отправляем корректный payload, но без заголовка Authorization.
    Ожидаем 403 Forbidden — сервер не должен принимать данные без авторизации.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "health_points": [
                {
                    "client_id": CLIENT_ID,
                    "ts": BASE_TS,
                    "hr": 72,
                    "body_battery": 85,
                    "stress_points": [],
                }
            ]
        }
        resp = await client.post("/api/health-points", json=payload)
        assert resp.status_code == 403


# ═══════════════════════════════════════════
#  POST /api/daily-summaries + daily analytics
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_daily_summary_saves_and_builds_analytics():
    """
    Проверяем полный цикл: health points + daily summary → автоматическое построение DailyAnalytics.
    
    Сценарий:
    1. Отправляем 5 health points: hr=[70,72,74,76,78], bb=[90,87,84,81,78], stress=[20,30,40,50,60]
    2. Отправляем daily summary: steps=8500, calories=1900, distance=650000, active_minutes=45
    3. POST /api/daily-summaries автоматически вызывает build_daily_analytics
    
    Проверяем в DailyAnalytics:
    - HR: avg=74.0, min=70, max=78
    - BB: avg=84.0, min=78, max=90
    - Stress: avg=40.0, min=20, max=60
    - Шаги, калории и active_minutes подтянулись из daily summary
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Сначала отправляем health points за этот день (нужны для аналитики)
        hp_payload = {
            "health_points": [
                {
                    "client_id": CLIENT_ID,
                    "ts": BASE_TS + i * 180,
                    "hr": 70 + i * 2,  # 70, 72, 74, 76, 78
                    "body_battery": 90 - i * 3,  # 90, 87, 84, 81, 78
                    "stress_points": [
                        {"ts": BASE_TS + i * 180, "value": 20 + i * 10}  # 20, 30, 40, 50, 60
                    ],
                }
                for i in range(5)
            ]
        }
        resp = await client.post("/api/health-points", json=hp_payload, headers=AUTH_HEADERS)
        assert resp.status_code == 200

        # Теперь отправляем daily summary
        daily_payload = {
            "daily_summaries": [
                {
                    "client_id": CLIENT_ID,
                    "ts": BASE_TS,
                    "steps": 8500,
                    "calories": 1900,
                    "distance_cm": 650000,
                    "active_minutes": 45,
                }
            ]
        }
        resp = await client.post("/api/daily-summaries", json=daily_payload, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["saved_daily_summaries"] == 1

    # Проверяем daily info в БД
    async with test_session() as s:
        info = (await s.execute(
            select(AdditionalDailyInfo).where(AdditionalDailyInfo.client_id == CLIENT_ID)
        )).scalar_one()
        assert info.steps == 8500
        assert info.calories == 1900
        assert info.distance == 650000
        assert info.active_minutes == 45

    # Проверяем что аналитика сформировалась
    async with test_session() as s:
        analytics = (await s.execute(
            select(DailyAnalytics).where(DailyAnalytics.client_id == CLIENT_ID)
        )).scalar_one()

        # HR: avg из [70, 72, 74, 76, 78] = 74.0
        assert analytics.hr_avg == 74.0
        assert analytics.hr_min == 70
        assert analytics.hr_max == 78

        # BB: avg из [90, 87, 84, 81, 78] = 84.0
        assert analytics.bb_avg == 84.0
        assert analytics.bb_min == 78
        assert analytics.bb_max == 90

        # Stress: avg из [20, 30, 40, 50, 60] = 40.0
        assert analytics.stress_avg == 40.0
        assert analytics.stress_min == 20
        assert analytics.stress_max == 60

        # Шаги и т.д. подтянулись из daily summary
        assert analytics.steps == 8500
        assert analytics.calories == 1900
        assert analytics.active_minutes == 45


@pytest.mark.asyncio
async def test_daily_analytics_stress_zones():
    """
    Проверяем корректный подсчёт зон стресса в DailyAnalytics.
    Каждая стресс-точка соответствует 3-минутному интервалу (MINUTES_PER_POINT=3).
    
    Отправляем 5 точек по зонам:
    - Rest (<=25):  15, 20  → 2 точки × 3 мин = 6 мин
    - Low (26-50):  40      → 1 точка × 3 мин = 3 мин
    - Med (51-75):  60      → 1 точка × 3 мин = 3 мин
    - High (>75):   85      → 1 точка × 3 мин = 3 мин
    
    Убеждаемся, что stress_rest_time=6, stress_low_time=3, stress_med_time=3, stress_high_time=3.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 2 точки rest (<=25), 1 low (26-50), 1 med (51-75), 1 high (>75)
        stress_values = [15, 20, 40, 60, 85]
        hp_payload = {
            "health_points": [
                {
                    "client_id": CLIENT_ID,
                    "ts": BASE_TS + i * 180,
                    "hr": 75,
                    "body_battery": 80,
                    "stress_points": [{"ts": BASE_TS + i * 180, "value": v}],
                }
                for i, v in enumerate(stress_values)
            ]
        }
        await client.post("/api/health-points", json=hp_payload, headers=AUTH_HEADERS)

        daily_payload = {
            "daily_summaries": [
                {
                    "client_id": CLIENT_ID,
                    "ts": BASE_TS,
                    "steps": 5000,
                    "calories": 1200,
                    "distance_cm": 400000,
                    "active_minutes": 30,
                }
            ]
        }
        await client.post("/api/daily-summaries", json=daily_payload, headers=AUTH_HEADERS)

    async with test_session() as s:
        analytics = (await s.execute(
            select(DailyAnalytics).where(DailyAnalytics.client_id == CLIENT_ID)
        )).scalar_one()

        # 2 точки rest × 3 мин = 6
        assert analytics.stress_rest_time == 6
        # 1 точка low × 3 мин = 3
        assert analytics.stress_low_time == 3
        # 1 точка med × 3 мин = 3
        assert analytics.stress_med_time == 3
        # 1 точка high × 3 мин = 3
        assert analytics.stress_high_time == 3


@pytest.mark.asyncio
async def test_daily_summaries_without_auth():
    """
    Проверяем, что эндпоинт /api/daily-summaries защищён Bearer-токеном.
    Отправляем корректный payload, но без заголовка Authorization.
    Ожидаем 403 Forbidden — сервер не должен принимать данные без авторизации.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "daily_summaries": [
                {
                    "client_id": CLIENT_ID,
                    "ts": BASE_TS,
                    "steps": 5000,
                    "calories": 1200,
                    "distance_cm": 400000,
                    "active_minutes": 30,
                }
            ]
        }
        resp = await client.post("/api/daily-summaries", json=payload)
        assert resp.status_code == 403
