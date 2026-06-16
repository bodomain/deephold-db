"""Configuration: pydantic-settings for .env + YAML loaders for config/."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "config"


class Settings(BaseSettings):
    """Settings from .env (or environment)."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Database ----------------------------------------------------------
    database_url: str = Field(
        default="postgresql+psycopg://finance:finance@localhost:5432/finance",
        alias="DATABASE_URL",
    )

    # --- App ---------------------------------------------------------------
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    env: str = Field(default="dev", alias="ENV")

    # --- Vendors -----------------------------------------------------------
    fred_api_key: str = Field(default="", alias="FRED_API_KEY")
    ecb_sdmx_base: str = Field(
        default="https://data-api.ecb.europa.eu/service",
        alias="ECB_SDMX_BASE",
    )
    bundesbank_sdmx_base: str = Field(
        default="https://api.statistiken.bundesbank.de/rest",
        alias="BUNDESBANK_SDMX_BASE",
    )
    yahoo_enabled: bool = Field(default=True, alias="YAHOO_ENABLED")
    stooq_enabled: bool = Field(default=True, alias="STOOQ_ENABLED")

    # --- Prefect -----------------------------------------------------------
    prefect_api_url: str = Field(
        default="http://localhost:4200/api",
        alias="PREFECT_API_URL",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def _load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_tickers() -> dict[str, Any]:
    """Inventory of equity tickers (config/tickers.yaml)."""
    return _load_yaml("tickers.yaml")


def load_vendors() -> dict[str, Any]:
    """Vendor configuration (config/vendors.yaml)."""
    return _load_yaml("vendors.yaml")


def load_series_registry() -> dict[str, Any]:
    """Series registry (config/series_registry.yaml)."""
    return _load_yaml("series_registry.yaml")
