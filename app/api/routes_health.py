"""Health and readiness routes."""

from fastapi import APIRouter, HTTPException

from app.config import get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, str]:
    """
    Readiness probe.

    Checks for the presence of the KB persistence directory defined in settings.
    """
    settings = get_settings()
    if not settings.kb_path_exists:
        raise HTTPException(
            status_code=503,
            detail=f"KB directory missing: {settings.kb_persist_dir}",
        )
    return {"status": "ok"}
