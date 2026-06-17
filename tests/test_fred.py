"""Tests for FRED vendor adapter (no DB, mocked HTTP)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import polars as pl
import pytest

from deephold_db.vendors.fred import FredVendor, _parse_value


def test_parse_value_normal() -> None:
    assert _parse_value("5.02") == 5.02


@pytest.mark.parametrize("missing", [".", "", None])
def test_parse_value_missing(missing) -> None:
    assert _parse_value(missing) is None


def test_fred_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # pydantic-settings reads .env directly, so delenv is not enough.
    # Set to empty string in env to override.
    monkeypatch.setenv("FRED_API_KEY", "")
    with pytest.raises(ValueError, match="FRED_API_KEY"):
        FredVendor()


def test_fred_uses_provided_key() -> None:
    v = FredVendor(api_key="explicit")
    assert v.api_key == "explicit"


def test_fred_fetch_parses_response(
    monkeypatch: pytest.MonkeyPatch, fake_fred_observations: dict
) -> None:
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    v = FredVendor()
    v._get = MagicMock(return_value=fake_fred_observations)  # type: ignore[method-assign]

    df = v.fetch("DGS3MO", date(2024, 1, 1), date(2024, 1, 31))

    assert df.height == 3
    assert df.columns == ["date", "value"]
    assert df["value"][0] == 5.02
    assert df["value"][1] is None
    assert df["value"][2] == 5.05
    v._get.assert_called_once()
    args, _ = v._get.call_args
    assert args[0] == "/series/observations"
    assert args[1]["series_id"] == "DGS3MO"


def test_fred_fetch_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    v = FredVendor()
    v._get = MagicMock(return_value={"observations": []})  # type: ignore[method-assign]

    df = v.fetch("NOSUCHSERIES", date(2024, 1, 1), date(2024, 1, 31))

    assert df.is_empty()
    assert df.schema == {"date": pl.Date, "value": pl.Float64}


def test_fred_healthcheck_ok(monkeypatch: pytest.MonkeyPatch, fake_fred_releases: dict) -> None:
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    v = FredVendor()
    v._get = MagicMock(return_value=fake_fred_releases)  # type: ignore[method-assign]
    assert v.healthcheck() is True


def test_fred_healthcheck_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    v = FredVendor()
    v._get = MagicMock(side_effect=Exception("network down"))  # type: ignore[method-assign]
    assert v.healthcheck() is False
