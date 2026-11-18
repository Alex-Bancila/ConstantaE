"""App settings, read from environment variables or from backend/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
MOCK_ANALYSIS_FILE = REPO_ROOT / "shared" / "mock-analysis.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "mock" returns fixed AI results, so you can work without models or API keys.
    ai_mode: Literal["mock", "real"] = "mock"
    # False runs every analysis inside the request; True hands it to the job queue.
    async_jobs: bool = Field(default=False, validation_alias="ASYNC")
    database_url: str | None = None
    redis_url: str | None = None
    llm_api_key: str | None = None
    result_ttl_seconds: int = Field(default=86400, validation_alias="RESULT_TTL_SECONDS")
    image_cache_ttl_seconds: int = Field(default=604800, validation_alias="IMAGE_CACHE_TTL_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
