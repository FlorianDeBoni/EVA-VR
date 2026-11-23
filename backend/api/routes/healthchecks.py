from fastapi import APIRouter, HTTPException

from backend.api.schemas import HealthResponse, HealthStatus
from backend.services.databaseService import get_database_service
from backend.src.settings.LogManager import LogManager

router = APIRouter(prefix="/health", tags=["health"])
logger = LogManager.get_logger(__name__)


@router.get("/live", summary="Liveness probe")
async def live() -> HealthResponse:
    """Report that the process is running and able to serve requests."""
    return HealthResponse(status=HealthStatus.OK)


@router.get("/ready", summary="Readiness probe")
def ready() -> HealthResponse:
    """Report that the service is ready to take traffic: the database answers `SELECT 1`.

    Sync on purpose: the database call blocks, so FastAPI runs it in its threadpool.
    Answers 503 when the database is unreachable.
    """
    try:
        with get_database_service().client.connection() as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return HealthResponse(status=HealthStatus.OK)
