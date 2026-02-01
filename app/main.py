"""FastAPI entrypoint for the QA Checklist Generator."""

from fastapi import FastAPI

from app.api.routes_health import router as health_router
from app.api.routes_llm import router as llm_router
from app.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title="Avto.pro QA Checklist Generator",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    application.include_router(health_router)
    application.include_router(llm_router)

    # Store settings on state for future use.
    application.state.settings = settings
    return application


app = create_app()
