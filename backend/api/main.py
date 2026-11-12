from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.src.settings.envManager import EnvKeyName, EnvManager


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(title="EVA-VR API", version="0.1.0")

    # The frontend calls the API straight from the browser, from another origin.
    origins = EnvManager.get_env_variable(EnvKeyName.KEY_CORS_ORIGINS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins.split(",") if o.strip()],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    app.include_router(api_router)
    return app


app = create_app()
