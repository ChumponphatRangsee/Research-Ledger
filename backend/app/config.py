from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Research Ledger"
    debug: bool = False

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

    backend_cors_origins: str = "http://localhost:3000"

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
