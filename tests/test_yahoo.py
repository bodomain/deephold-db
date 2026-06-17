"""Tests for Yahoo vendor adapter (no DB, mocked yfinance)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import polars as pl
import pytest

from deephold_db.vendors.yahoo import YahooVendor, _yahoo_to_polars

# --- Fixtures --------------------------------------------------------------


def _make_yf_df() -> pd.DataFrame:
    """Mimic a yfinance .history() return: tz-aware DatetimeIndex + OHLCV."""
    idx = pd.DatetimeIndex(
        [
            "2024-06-03 00:00:00",
            "2024-06-04 00:00:00",
            "2024-06-05 00:00:00",
        ],
        tz="America/New_York",
        name="Date",
    )
    return pd.DataFrame(
        {
            "Open": [192.90, 194.64, 195.30],
            "High": [194.99, 195.32, 196.00],
            "Low": [192.10, 193.50, 194.20],
            "Close": [194.20, 195.10, 195.80],
            "Adj Close": [194.20, 195.10, 195.80],  # no splits/dividends in fixture
            "Volume": [50_000_000, 45_000_000, 38_000_000],
        },
        index=idx,
    )


@pytest.fixture
def mock_ticker() -> MagicMock:
    t = MagicMock()
    t.history.return_value = _make_yf_df()
    return t


# --- Parser unit tests -----------------------------------------------------


def test_yahoo_to_polars_shape() -> None:
    df = _yahoo_to_polars(_make_yf_df())
    assert df.height == 3
    assert df.columns == ["date", "open", "high", "low", "close", "adjusted_close", "volume"]
    assert df.schema == {
        "date": pl.Date,
        "open": pl.Float64,
        "high": pl.Float64,
        "low": pl.Float64,
        "close": pl.Float64,
        "adjusted_close": pl.Float64,
        "volume": pl.Int64,
    }


def test_yahoo_to_polars_dates() -> None:
    df = _yahoo_to_polars(_make_yf_df())
    assert df["date"].to_list() == [date(2024, 6, 3), date(2024, 6, 4), date(2024, 6, 5)]


def test_yahoo_to_polars_values() -> None:
    df = _yahoo_to_polars(_make_yf_df())
    assert df["close"][0] == pytest.approx(194.20)
    assert df["volume"][0] == 50_000_000
    assert df["open"][1] == pytest.approx(194.64)


def test_yahoo_to_polars_drops_dividends_splits() -> None:
    pdf = _make_yf_df()
    pdf["Dividends"] = 0.0
    pdf["Stock Splits"] = 0.0
    df = _yahoo_to_polars(pdf)
    assert "Dividends" not in df.columns
    assert "Stock Splits" not in df.columns


def test_yahoo_to_polars_empty() -> None:
    empty_pdf = pd.DataFrame(
        columns=["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    ).astype(
        {
            "Open": float,
            "High": float,
            "Low": float,
            "Close": float,
            "Adj Close": float,
            "Volume": "int64",
        }
    )
    df = _yahoo_to_polars(empty_pdf)
    assert df.is_empty()
    assert set(df.columns) == {"date", "open", "high", "low", "close", "adjusted_close", "volume"}


# --- Vendor tests ----------------------------------------------------------


def test_yahoo_fetch_parses_response(mock_ticker: MagicMock) -> None:
    v = YahooVendor()
    v._ticker = MagicMock(return_value=mock_ticker)  # type: ignore[method-assign]

    df = v.fetch("AAPL", date(2024, 6, 1), date(2024, 6, 10))

    mock_ticker.history.assert_called_once()
    kwargs = mock_ticker.history.call_args.kwargs
    assert kwargs["start"] == "2024-06-01"
    assert kwargs["end"] == "2024-06-11"  # +1 day (yfinance end is exclusive)
    assert kwargs["auto_adjust"] is False
    assert kwargs["actions"] is False

    assert df.height == 3
    assert df["close"][0] == pytest.approx(194.20)


def test_yahoo_fetch_index_ticker(mock_ticker: MagicMock) -> None:
    v = YahooVendor()
    v._ticker = MagicMock(return_value=mock_ticker)  # type: ignore[method-assign]

    df = v.fetch("^GSPC", date(2024, 6, 1), date(2024, 6, 10))
    assert df.height == 3


def test_yahoo_fetch_empty_response() -> None:
    t = MagicMock()
    t.history.return_value = pd.DataFrame()
    v = YahooVendor()
    v._ticker = MagicMock(return_value=t)  # type: ignore[method-assign]

    df = v.fetch("NOSUCH", date(2024, 1, 1), date(2024, 12, 31))
    assert df.is_empty()


def test_yahoo_healthcheck_ok(mock_ticker: MagicMock) -> None:
    v = YahooVendor()
    v._ticker = MagicMock(return_value=mock_ticker)  # type: ignore[method-assign]
    assert v.healthcheck() is True


def test_yahoo_healthcheck_fail_on_exception() -> None:
    v = YahooVendor()
    v._ticker = MagicMock(side_effect=Exception("network down"))  # type: ignore[method-assign]
    assert v.healthcheck() is False
