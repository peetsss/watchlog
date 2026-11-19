import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


@router.get("/health", response_class=PlainTextResponse, include_in_schema=False)
async def health() -> str:
    return "ok"


@router.get("/ready", include_in_schema=False)
async def ready(request: Request) -> JSONResponse:
    checks = await probe_dependencies(request.app)
    healthy = all(value == "ok" for value in checks.values())
    payload: dict[str, object] = {"status": "ok" if healthy else "unavailable"}
    if not request.app.state.settings.is_production:
        payload["checks"] = checks
    return JSONResponse(payload, status_code=200 if healthy else 503)


async def probe_dependencies(app: FastAPI) -> dict[str, str]:
    checks: dict[str, str] = {}
    try:
        async with app.state.sessionmaker() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.warning("Database readiness check failed", exc_info=True)
        checks["database"] = "failed"
    try:
        await app.state.redis.ping()
        checks["redis"] = "ok"
    except Exception:
        logger.warning("Redis readiness check failed", exc_info=True)
        checks["redis"] = "failed"
    return checks
