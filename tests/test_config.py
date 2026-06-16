"""Tests for config loading."""

from __future__ import annotations

import pytest

from finance_data.utils.config import (
    CONFIG_DIR,
    PROJECT_ROOT,
    get_settings,
    load_vendors,
)


def test_project_root_exists() -> None:
    assert PROJECT_ROOT.exists()
    assert (PROJECT_ROOT / "pyproject.toml").exists()


def test_config_dir_exists() -> None:
    assert CONFIG_DIR.exists()
    assert (CONFIG_DIR / "vendors.yaml").exists()


def test_get_settings_caches() -> None:
    get_settings.cache_clear()
    a = get_settings()
    b = get_settings()
    assert a is b


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "abc123")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    get_settings.cache_clear()
    s = get_settings()
    assert s.fred_api_key == "abc123"
    assert s.log_level == "DEBUG"


def test_load_vendors_has_fred() -> None:
    v = load_vendors()
    assert "fred" in v["vendors"]
    assert v["vendors"]["fred"]["code"] == "fred"
    assert "rate_limit" in v["vendors"]["fred"]


def test_settings_default_database_url() -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.database_url.startswith("postgresql+psycopg://")
    finally:
        monkeypatch.undo()
