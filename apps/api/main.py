from fastapi import FastAPI
from sqlalchemy import text

from apps.api.config import get_settings
from apps.api.routes import (
    appointments,
    dev,
    escalations,
    faq,
    intake,
    metrics,
    patients,
    sessions,
)
from db.session import get_db_session

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)


app.include_router(sessions.router)
app.include_router(patients.router)
app.include_router(appointments.router)
app.include_router(faq.router)
app.include_router(escalations.router)
app.include_router(intake.router)
app.include_router(metrics.router)

if settings.environment == "development":
    app.include_router(dev.router)


@app.get("/health")
async def health() -> dict[str, str]:
    database_status = "unavailable"

    session = get_db_session()

    try:
        session.execute(text("SELECT 1"))
        database_status = "ok"
    finally:
        session.close()

    return {
        "status": "ok",
        "service": "api",
        "database": database_status,
    }
