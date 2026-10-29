from fastapi import APIRouter

from backend.api.routes import healthchecks

api_router = APIRouter()
api_router.include_router(healthchecks.router)
