from enum import StrEnum

from pydantic import BaseModel


class HealthStatus(StrEnum):
    """Possible states of the service."""

    OK = "ok"


class HealthResponse(BaseModel):
    """Response body of the health endpoints."""

    status: HealthStatus
