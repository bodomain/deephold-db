"""Yahoo Finance vendor adapter (via yfinance).

ToS / Lizenz (siehe docs/sources.md):
    - Nur für privaten Gebrauch. Keine Weiterverteilung der Roh-Daten.
    - Yahoo kann das Schema jederzeit ändern, Scraping ist eine Grauzone.
    - Rate-Limit: 30 req/min, burst 5.

Liefert tägliche OHLCV für Aktien, ETFs, Indizes, Forex-Pairs.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import polars as pl
import yfinance as yf

from deephold_db.utils.logging import get_logger
from deephold_db.utils.rate_limit import limit
from deephold_db.vendors.base import Vendor

log = get_logger(__name__)

YAHOO_RATE_PER_MIN = 30
YAHOO_BURST = 5


class YahooVendor(Vendor):
    """Yahoo Finance adapter (yfinance).

    Use ``fetch(symbol, start, end)`` with a yfinance-compatible ticker:
    - Aktien:    ``AAPL``, ``MSFT``, ``SAP.DE``
    - Indizes:   ``^GSPC`` (S&P 500), ``^GDAXI`` (DAX), ``^N225`` (Nikkei)
    - Forex:     ``EURUSD=X``, ``GBPUSD=X``
    - Rohstoffe: ``GC=F`` (Gold), ``CL=F`` (WTI)
    """

    code = "yahoo"

    def __init__(self, ticker: str | None = None) -> None:
        # The yfinance.Ticker is created per-call. We keep no state here.
        self._test_ticker = ticker

    def _ticker(self, symbol: str) -> Any:
        """Return the yfinance.Ticker. Override in tests via monkeypatch."""
        return yf.Ticker(symbol)

    def healthcheck(self) -> bool:
        try:
            self.fetch("AAPL", date.today(), date.today())
            # AAPL trades most days, so even an empty weekend day is fine.
            # We just want the yfinance call to not throw.
            return True
        except Exception as e:
            log.error("yahoo.healthcheck_failed", error=str(e))
            return False

    def fetch(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        """Fetch daily OHLCV for `symbol` in [start, end].

        Returns polars DataFrame with columns:
            date, open, high, low, close, adjusted_close, volume
        """
        with limit(self.code, YAHOO_RATE_PER_MIN, YAHOO_BURST):
            t = self._ticker(symbol)
            pdf: pd.DataFrame = t.history(
                start=start.isoformat(),
                end=_end_exclusive(end),
                auto_adjust=False,
                actions=False,
            )

        if pdf.empty:
            log.warning("yahoo.empty", symbol=symbol)
            return pl.DataFrame(schema=_YAHOO_SCHEMA)

        return _yahoo_to_polars(pdf)

    def fetch_many(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> dict[str, pl.DataFrame]:
        """Bulk-fetch daily OHLCV for many tickers in a single yfinance call.

        Uses ``yf.download()`` which is much faster than per-ticker
        requests and is rate-limit-friendly for bulk historical loads.

        Returns ``{symbol: DataFrame}`` with the same schema as ``fetch``.
        Symbols that fail or return no data are mapped to an empty
        DataFrame with the canonical schema.
        """
        if not symbols:
            return {}
        with limit(self.code, YAHOO_RATE_PER_MIN, YAHOO_BURST):
            try:
                pdf = yf.download(
                    tickers=" ".join(symbols),
                    start=start.isoformat(),
                    end=_end_exclusive(end),
                    auto_adjust=False,
                    actions=False,
                    group_by="ticker",
                    threads=True,
                    progress=False,
                )
            except Exception as e:
                log.error("yahoo.fetch_many_failed", error=str(e))
                return {s: pl.DataFrame(schema=_YAHOO_SCHEMA) for s in symbols}

        # yf.download returns MultiIndex columns when multiple tickers, e.g.
        # MultiIndex([('AAPL','Open'), ('AAPL','High'), ...])
        result: dict[str, pl.DataFrame] = {}
        for symbol in symbols:
            try:
                if isinstance(pdf.columns, pd.MultiIndex):
                    if symbol not in pdf.columns.get_level_values(0):
                        result[symbol] = pl.DataFrame(schema=_YAHOO_SCHEMA)
                        continue
                    sub = pdf[symbol].copy()
                    sub.columns.name = None
                else:
                    # Single-ticker fallback: columns are flat.
                    sub = pdf.copy()
                if sub.empty:
                    result[symbol] = pl.DataFrame(schema=_YAHOO_SCHEMA)
                    continue
                result[symbol] = _yahoo_to_polars(sub)
            except Exception as e:
                log.warning("yahoo.fetch_many_row_failed", symbol=symbol, error=str(e))
                result[symbol] = pl.DataFrame(schema=_YAHOO_SCHEMA)
        return result


def _end_exclusive(end: date) -> str:
    """yfinance `end` is exclusive, so add 1 day to make it inclusive."""
    from datetime import timedelta

    return (end + timedelta(days=1)).isoformat()


def _yahoo_to_polars(pdf: pd.DataFrame) -> pl.DataFrame:
    """Convert a yfinance pandas DataFrame to a polars DataFrame with our schema.

    Drops Dividends / Stock Splits (those go into corporate_actions separately).
    Strips timezone, normalizes to date. Coerces pandas nullable dtypes
    (Int64, Float64) to plain numpy dtypes so polars can ingest without pyarrow.
    """
    if pdf.empty or not isinstance(pdf.index, pd.DatetimeIndex):
        return pl.DataFrame(schema=_YAHOO_SCHEMA)

    # Reset index to get Date as a column
    pdf = pdf.reset_index()

    # yfinance column names
    keep = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
    pdf = pdf[[c for c in keep if c in pdf.columns]].copy()

    # Normalize date: strip tz, keep datetime64[ns] (polars will cast to Date)
    if "Date" in pdf.columns:
        pdf["Date"] = pd.to_datetime(pdf["Date"], utc=True).dt.tz_convert(None)

    # Rename to our convention
    pdf = pdf.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adjusted_close",
            "Volume": "volume",
        }
    )

    # Coerce nullable pandas dtypes to plain numpy dtypes (polars needs this).
    for col in pdf.columns:
        dt = pdf[col].dtype
        if isinstance(dt, pd.core.dtypes.base.ExtensionDtype):
            pdf[col] = pdf[col].to_numpy(na_value=0 if col == "volume" else float("nan"))

    df = pl.from_pandas(pdf)
    return df.select(
        pl.col("date").cast(pl.Date),
        pl.col("open").cast(pl.Float64, strict=False),
        pl.col("high").cast(pl.Float64, strict=False),
        pl.col("low").cast(pl.Float64, strict=False),
        pl.col("close").cast(pl.Float64, strict=False),
        pl.col("adjusted_close").cast(pl.Float64, strict=False),
        pl.col("volume").cast(pl.Int64, strict=False),
    )


_YAHOO_SCHEMA: dict[str, pl.DataType] = {
    "date": pl.Date,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "adjusted_close": pl.Float64,
    "volume": pl.Int64,
}


__all__ = ["YahooVendor"]
