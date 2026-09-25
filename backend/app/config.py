"""Application settings, loaded from the environment with sane local defaults.

Every value has a default that works on a fresh clone with no ``.env`` file,
because a portfolio project that needs a configuration ritual before it starts
does not get run.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # -- app ---------------------------------------------------------------
    app_name: str = "TriageAI"
    environment: str = Field(default="development")
    debug: bool = True

    # -- database ----------------------------------------------------------
    # SQLite over MongoDB, deliberately. The data here is relational — tickets
    # own status transitions and override records, and the analytics endpoint
    # is almost entirely GROUP BY. That is a SQL-shaped problem, and SQLite
    # runs it with zero external services, which keeps a clone-and-run demo
    # genuinely clone-and-run. The async driver keeps the API non-blocking,
    # and everything goes through a service layer so swapping the store later
    # touches one module rather than every route.
    database_url: str = Field(default=f"sqlite+aiosqlite:///{BACKEND_ROOT / 'triageai.db'}")
    db_echo: bool = False

    # -- cors --------------------------------------------------------------
    # Defaults cover the Vite dev and preview servers on both hostnames.
    #
    # NoDecode is load-bearing. pydantic-settings JSON-decodes list fields read
    # from the environment, so the comma-separated form every PaaS dashboard
    # uses ("https://a.app,https://b.app") raised a SettingsError at boot,
    # before the splitting validator below ever ran.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )

    # -- demo --------------------------------------------------------------
    # Background task that injects a ticket every so often, so the live feed
    # has something to show without a human filling in the form. Off by
    # default; the dashboard toggles it through the API.
    simulator_interval_seconds: float = 12.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        """Accept a comma-separated string, which is how PaaS env vars arrive."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the environment is parsed once per process."""
    return Settings()


settings = get_settings()
