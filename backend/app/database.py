import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://psychmonitor:psychmonitor_secret@localhost:5432/psychmonitor"
)

_engine = None
_async_session = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, echo=False)
    return _engine


def _get_session():
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(_get_engine(), expire_on_commit=False)
    return _async_session


def override_engine(url: str):
    """Для тестов: пересоздать engine с другим URL."""
    global _engine, _async_session
    _engine = create_async_engine(url, echo=False)
    _async_session = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


# Обратная совместимость: модули, которые импортируют engine / async_session напрямую
class _EngineProxy:
    def __getattr__(self, name):
        return getattr(_get_engine(), name)

class _SessionProxy:
    def __call__(self, *args, **kwargs):
        return _get_session()(*args, **kwargs)
    def __getattr__(self, name):
        return getattr(_get_session(), name)

engine = _EngineProxy()
async_session = _SessionProxy()


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with _get_session()() as session:
        yield session
