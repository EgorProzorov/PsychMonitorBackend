"""
Тест реалтайм-детекции стресс-эпизодов.

Запуск:
  cd backend
  source venv/bin/activate
  python -m pytest tests/test_stress_episodes.py -v
"""
import os

# КРИТИЧНО: переопределяем DATABASE_URL ДО импорта app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_episodes.db"
os.environ["API_TOKEN"] = "test-token"

import pytest
import pytest_asyncio
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import event

from app.database import Base, get_db
from app.main import app

# Тестовый engine (SQLite)
test_engine = create_async_engine("sqlite+aiosqlite:///./test_episodes.db", echo=False)
test_session = async_sessionmaker(test_engine, expire_on_commit=False)


# SQLite не поддерживает схемы — нужен workaround для ON CONFLICT
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
BASE_TS = int(datetime(2026, 4, 5, 10, 0, 0).timestamp())


def make_payload(stress_values, start_ts, interval_sec=60, hr=80):
    """Генерирует payload для POST /api/health-points."""
    points = []
    for i, val in enumerate(stress_values):
        ts = start_ts + i * interval_sec
        points.append({
            "client_id": CLIENT_ID,
            "ts": ts,
            "hr": hr,
            "body_battery": 70,
            "stress_points": [{"ts": ts, "value": val}],
        })
    return {"health_points": points}


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    # Удаляем файл БД
    if os.path.exists("./test_episodes.db"):
        os.remove("./test_episodes.db")


@pytest.mark.asyncio
async def test_episode_opens_after_consecutive_high_stress():
    """Эпизод открывается после 2 точек подряд >= 51."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/health-points",
            json=make_payload([75, 80], BASE_TS),
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200

        resp = await client.get(
            f"/api/stress-episodes/{CLIENT_ID}/active",
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        ep = resp.json()
        assert ep["ended_at"] is None
        assert ep["peak_stress"] >= 75


@pytest.mark.asyncio
async def test_no_episode_on_single_high_point():
    """1 точка >= 51 НЕ открывает эпизод."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/health-points",
            json=make_payload([80], BASE_TS),
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200

        resp = await client.get(
            f"/api/stress-episodes/{CLIENT_ID}/active",
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_episode_closes_on_low_stress():
    """Эпизод закрывается при точке < 51."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/health-points",
            json=make_payload([80, 85], BASE_TS),
            headers=AUTH_HEADERS,
        )
        await client.post(
            "/api/health-points",
            json=make_payload([30], BASE_TS + 120),
            headers=AUTH_HEADERS,
        )

        resp = await client.get(
            f"/api/stress-episodes/{CLIENT_ID}/active",
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_short_episode_discarded():
    """Эпизод < 30 мин удаляется."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/health-points",
            json=make_payload([80, 85], BASE_TS, interval_sec=60),
            headers=AUTH_HEADERS,
        )
        await client.post(
            "/api/health-points",
            json=make_payload([30], BASE_TS + 120),
            headers=AUTH_HEADERS,
        )

        resp = await client.get(
            f"/api/stress-episodes/{CLIENT_ID}",
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_long_episode_kept():
    """Эпизод >= 30 мин сохраняется со статусом pending."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 35 точек × 1 мин = 34 минуты
        values = [80] * 12
        await client.post(
            "/api/health-points",
            json=make_payload(values, BASE_TS, interval_sec=180),
            headers=AUTH_HEADERS,
        )
        await client.post(
            "/api/health-points",
            json=make_payload([30], BASE_TS + 12 * 180),
            headers=AUTH_HEADERS,
        )

        resp = await client.get(
            f"/api/stress-episodes/{CLIENT_ID}",
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        episodes = resp.json()
        assert len(episodes) == 1
        assert episodes[0]["ended_at"] is not None
        assert episodes[0]["duration_minutes"] >= 30
        assert episodes[0]["approved_status"] == "pending"


@pytest.mark.asyncio
async def test_update_comment_and_status():
    """PATCH обновляет описание и статус."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        values = [80] * 35
        await client.post(
            "/api/health-points",
            json=make_payload(values, BASE_TS, interval_sec=60),
            headers=AUTH_HEADERS,
        )
        await client.post(
            "/api/health-points",
            json=make_payload([30], BASE_TS + 35 * 60),
            headers=AUTH_HEADERS,
        )

        resp = await client.get(
            f"/api/stress-episodes/{CLIENT_ID}",
            headers=AUTH_HEADERS,
        )
        episode_id = resp.json()[0]["id"]

        resp = await client.patch(
            f"/api/stress-episodes/{episode_id}",
            params={
                "user_description": "Сложный разговор",
                "approved_status": "confirmed",
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["user_description"] == "Сложный разговор"
        assert updated["approved_status"] == "confirmed"
