from fastapi import APIRouter

from backend.api.routes import healthchecks, speech

api_router = APIRouter()
api_router.include_router(healthchecks.router)
api_router.include_router(speech.router)
