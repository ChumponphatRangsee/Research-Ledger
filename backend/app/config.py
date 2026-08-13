from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Research Ledger"
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/investflow"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_secret: str = ""

    openai_api_key: str = ""
    anthropic_api_key: str = ""

    backend_cors_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:3001,"
        "http://127.0.0.1:3001"
    )

    screener_cron_hour: int = 6
    screener_cron_minute: int = 0
    screener_min_market_cap: int = 1_000_000_000
    screener_min_score: float = 55.0
    screener_min_confidence: float = Field(default=60.0, ge=0.0, le=100.0)
    screener_top_n_candidates: int = 20
    # Retained for environment-file compatibility; valuation and ROE are now scored
    # within each strategy rather than used as universal hard filters.
    screener_max_pe: float = 25.0
    screener_min_roe: float = 0.15

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
