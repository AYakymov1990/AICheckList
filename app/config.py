"""Application configuration via environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", case_sensitive=False)

    app_port: int = Field(8000, alias="APP_PORT")
    scrape_base_url: str = Field("https://avto.pro/helpcenter/", alias="SCRAPE_BASE_URL")
    scrape_rate_limit_seconds: float = Field(1.0, alias="SCRAPE_RATE_LIMIT_SECONDS")
    kb_persist_dir: Path = Field(
        default_factory=lambda: Path("data/chroma"), alias="KB_PERSIST_DIR"
    )
    embedding_model: str = Field(
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        alias="EMBEDDING_MODEL",
    )
    rag_top_k: int = Field(5, alias="RAG_TOP_K")
    g4f_base_url: str = Field("http://localhost:1337/v1", alias="G4F_BASE_URL")
    g4f_model: str = Field("gpt-4o-mini", alias="G4F_MODEL")
    ocr_engine: str = Field("tesseract", alias="OCR_ENGINE")
    vision_enabled: bool = Field(True, alias="VISION_ENABLED")

    @property
    def kb_path_exists(self) -> bool:
        """Return True if the KB persistence directory exists."""
        return self.kb_persist_dir.exists()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
