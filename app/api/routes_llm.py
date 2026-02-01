"""Routes for LLM smoke testing."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.services.llm.client import LLMClient, LLMError

MAX_PROMPT_LEN = 2000

router = APIRouter(prefix="/llm", tags=["llm"])


class SmokeRequest(BaseModel):
    prompt: str = Field(..., max_length=MAX_PROMPT_LEN)
    model: str | None = Field(default=None, description="Optional model override")


class SmokeResponse(BaseModel):
    ok: bool
    model: str
    text: str


def _build_client(settings: Settings) -> LLMClient:
    base_url = settings.g4f_base_url or None
    return LLMClient(
        base_url=base_url,
        api_key=settings.g4f_api_key,
        default_model=settings.g4f_model,
        provider=settings.g4f_provider,
    )


@router.post("/smoke", response_model=SmokeResponse, status_code=status.HTTP_200_OK)
def smoke(
    payload: SmokeRequest, settings: Annotated[Settings, Depends(get_settings)]
) -> SmokeResponse:
    """Simple endpoint to verify LLM connectivity without RAG."""
    client = _build_client(settings)
    model_name = payload.model or settings.g4f_model
    try:
        text = client.chat(
            messages=[{"role": "user", "content": payload.prompt}],
            model=model_name,
            timeout_s=20.0,
        )
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return SmokeResponse(ok=True, model=model_name, text=text)
