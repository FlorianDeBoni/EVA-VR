from fastapi import APIRouter

from backend.api.schemas import HealthResponse, HealthStatus

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", summary="Liveness probe")
async def live() -> HealthResponse:
    """Report that the process is running and able to serve requests."""
    return HealthResponse(status=HealthStatus.OK)


@router.get("/ready", summary="Readiness probe")
async def ready() -> HealthResponse:
    """Report that the service is ready to take traffic.

    Dependency checks (database, AI client) should be added here once they exist.
    """
    return HealthResponse(status=HealthStatus.OK)
