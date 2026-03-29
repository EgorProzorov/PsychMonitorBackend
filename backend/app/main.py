from fastapi import FastAPI
from app.routers import health, daily

app = FastAPI(
    title="PsychMonitor API",
    description="Биометрические данные с Garmin Forerunner 55 для психиатрического анализа",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(daily.router)


@app.get("/")
async def root():
    return {"service": "PsychMonitor API", "status": "running"}


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}
