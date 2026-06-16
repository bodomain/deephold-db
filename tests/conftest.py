"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from finance_data.utils.config import get_settings


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Reset the pydantic-settings lru_cache around each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_fred_observations() -> dict:
    return {
        "observations": [
            {"date": "2024-01-02", "value": "5.02"},
            {"date": "2024-01-03", "value": "."},
            {"date": "2024-01-04", "value": "5.05"},
        ]
    }


@pytest.fixture
def fake_fred_releases() -> dict:
    return {"releases": [{"id": 1, "name": "Test"}]}
