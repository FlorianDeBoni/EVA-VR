from fastapi import FastAPI

from backend.api.router import api_router


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(title="EVA-VR API", version="0.1.0")
    app.include_router(api_router)
    return app


app = create_app()
