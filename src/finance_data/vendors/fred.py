"""FRED (Federal Reserve Economic Data) vendor adapter.

API docs: https://fred.stlouisfed.org/docs/api/api_key.html
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import polars as pl

from finance_data.utils.config import get_settings
from finance_data.utils.logging import get_logger
from finance_data.utils.rate_limit import limit
from finance_data.utils.retry import http_retry
from finance_data.vendors.base import Vendor

log = get_logger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"
FRED_RATE_PER_MIN = 120
FRED_BURST = 30


class FredVendor(Vendor):
    """FRED adapter. Yields one (date, value) row per observation.

    Missing observations are returned as None (FRED uses ".").
    """

    code = "fred"
    base_url = FRED_BASE

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or get_settings().fred_api_key
        if not self.api_key:
            raise ValueError("FRED_API_KEY is required (set in .env)")

    @http_retry()
    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        with limit(self.code, FRED_RATE_PER_MIN, FRED_BURST):
            q = {**params, "api_key": self.api_key, "file_type": "json"}
            r = httpx.get(f"{FRED_BASE}{path}", params=q, timeout=30.0)
            r.raise_for_status()
            return r.json()

    def healthcheck(self) -> bool:
        try:
            data = self._get("/releases", {"limit": 1})
            return "releases" in data
        except Exception as e:
            log.error("fred.healthcheck_failed", error=str(e))
            return False

    def fetch(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        """Fetch a FRED series as polars DataFrame with columns {date, value}."""
        data = self._get(
            "/series/observations",
            {
                "series_id": symbol,
                "observation_start": start.isoformat(),
                "observation_end": end.isoformat(),
            },
        )
        observations = data.get("observations", [])
        if not observations:
            log.warning("fred.empty", symbol=symbol)
            return pl.DataFrame(schema={"date": pl.Date, "value": pl.Float64})

        rows = [
            {"date": date.fromisoformat(obs["date"]), "value": _parse_value(obs["value"])}
            for obs in observations
        ]
        return pl.DataFrame(rows, schema={"date": pl.Date, "value": pl.Float64})


def _parse_value(s: str) -> float | None:
    """FRED uses '.' for missing. Return None for those."""
    if s in (".", "", None):
        return None
    return float(s)


__all__ = ["FredVendor"]
