"""Application configuration with project-root-relative path handling."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="FPL_OPTIMIZER_",
        extra="ignore",
    )

    database_url: str = "sqlite:///data/fpl_optimizer.db"
    cache_dir: Path = Path("data/cache")
    cache_ttl_seconds: int = Field(default=900, ge=0)
    http_timeout_seconds: float = Field(default=15.0, gt=0)
    log_level: str = "INFO"
    fpl_base_url: str = "https://fantasy.premierleague.com/api"
    odds_provider: str = "odds_api_io"
    odds_api_key: str = Field(default="", repr=False)
    odds_api_base_url: str = "https://api.odds-api.io/v3"
    odds_bookmakers: str = "Bet365,Unibet,Pinnacle"
    odds_cache_ttl_seconds: int = Field(default=3600, ge=900)
    odds_stale_after_seconds: int = Field(default=7200, ge=900)

    @field_validator("cache_dir", mode="after")
    @classmethod
    def resolve_cache_dir(cls, value: Path) -> Path:
        """Resolve a relative cache path against the project root."""

        return value if value.is_absolute() else PROJECT_ROOT / value

    @field_validator("database_url", mode="after")
    @classmethod
    def resolve_database_url(cls, value: str) -> str:
        """Resolve a relative SQLite URL against the project root."""

        prefix = "sqlite:///"
        if not value.startswith(prefix):
            return value
        path_text = value[len(prefix) :]
        path = Path(path_text)
        if path.is_absolute():
            return value
        return f"{prefix}{PROJECT_ROOT / path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide validated settings instance."""

    return Settings()
