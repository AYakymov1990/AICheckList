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
    scrape_output_dir: Path = Field(
        default_factory=lambda: Path("data/helpcenter"), alias="SCRAPE_OUTPUT_DIR"
    )
    scrape_download_assets: bool = Field(True, alias="SCRAPE_DOWNLOAD_ASSETS")
    scrape_max_pages: int = Field(0, alias="SCRAPE_MAX_PAGES")
    scrape_user_agent: str = Field("qa-checklist-bot/0.1 (local dev)", alias="SCRAPE_USER_AGENT")
    help_locales: str = Field("ru,ua,pl,es,pt", alias="HELP_LOCALES")  # legacy alias
    help_sites: dict[str, str] = Field(
        default_factory=lambda: {
            "ru": "https://avto.pro/helpcenter/",
            "ua": "https://avtopro.ua/helpcenter/",
            "pl": "https://avtopro.pl/helpcenter/",
            "es": "https://avtopro.es/helpcenter/",
            "pt": "https://avtopro.pt/helpcenter/",
        },
        alias="HELP_SITES",
    )
    help_cookies_file: str | None = Field(default=None, alias="HELP_COOKIES_FILE")
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
    g4f_api_key: str = Field("secret", alias="G4F_API_KEY")
    g4f_provider: str | None = Field(default=None, alias="G4F_PROVIDER")
    ocr_engine: str = Field("tesseract", alias="OCR_ENGINE")
    vision_enabled: bool = Field(True, alias="VISION_ENABLED")
    chunk_size_chars: int = Field(1400, alias="CHUNK_SIZE_CHARS")
    chunk_overlap_chars: int = Field(200, alias="CHUNK_OVERLAP_CHARS")
    chunk_min_chars: int = Field(300, alias="CHUNK_MIN_CHARS")
    normalize_bullets: bool = Field(True, alias="NORMALIZE_BULLETS")
    chunks_output_dir: Path = Field(
        default_factory=lambda: Path("data/helpcenter/chunks"), alias="CHUNKS_OUTPUT_DIR"
    )

    @property
    def kb_path_exists(self) -> bool:
        """Return True if the KB persistence directory exists."""
        return self.kb_persist_dir.exists()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
