"""Settings loaded once from the environment / .env file.

pydantic-settings validates env vars at startup (fail fast on a missing
DATABASE_URL, not on the first request that touches the DB). @lru_cache
turns get_settings() into a process-wide singleton without a module-level
global or a DI container -- stdlib functools already solves this.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "fast-mcp-template"
    environment: str = "development"  # development | staging | production
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    # Pool sizing is a real trade-off, not a magic number: too small and
    # requests queue for a connection under load; too large and you can
    # exhaust the DB's own max_connections. Tune per deployment, don't guess.
    db_pool_size: int = 5
    db_max_overflow: int = 10

    cors_origins: list[str] = []

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
