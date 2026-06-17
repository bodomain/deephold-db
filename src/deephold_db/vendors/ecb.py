"""ECB Statistical Data Warehouse (SDMX 2.1) vendor adapter.

API: https://data-api.ecb.europa.eu/service
No API key required for the SDMX 2.1 REST endpoint.

Endpoints used (per AGENTS.md / AGENTS_Anweisungen):
    /data/{flow}/{key}?startPeriod=...&endPeriod=...&format=csvdata

Examples:
    /data/EXR/D.USD.EUR.SP00.A   - USD/EUR reference rate (daily)
    /data/ICP/M.U2.N.000000.4.ANR - HICP overall, YoY (monthly)

Licence: © European Central Bank, CC BY 4.0.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import polars as pl

from deephold_db.utils.config import get_settings
from deephold_db.utils.logging import get_logger
from deephold_db.utils.rate_limit import limit
from deephold_db.utils.retry import http_retry
from deephold_db.vendors.base import Vendor

log = get_logger(__name__)

ECB_RATE_PER_MIN = 60
ECB_BURST = 10


# Public series registry. ``fetch()`` accepts any of these IDs, or any
# ``FLOW/KEY`` string for ad-hoc queries.
ECB_SERIES: dict[str, dict[str, str]] = {
    "ECB:EXR:USD.EUR.SP00.A": {
        "flow": "EXR",
        "key": "D.USD.EUR.SP00.A",
        "name": "USD/EUR reference rate (daily)",
        "frequency": "D",
        "unit": "EUR per USD",
    },
    "ECB:EXR:GBP.EUR.SP00.A": {
        "flow": "EXR",
        "key": "D.GBP.EUR.SP00.A",
        "name": "GBP/EUR reference rate (daily)",
        "frequency": "D",
        "unit": "EUR per GBP",
    },
    "ECB:EXR:JPY.EUR.SP00.A": {
        "flow": "EXR",
        "key": "D.JPY.EUR.SP00.A",
        "name": "JPY/EUR reference rate (daily)",
        "frequency": "D",
        "unit": "EUR per 100 JPY",
    },
    "ECB:EXR:CHF.EUR.SP00.A": {
        "flow": "EXR",
        "key": "D.CHF.EUR.SP00.A",
        "name": "CHF/EUR reference rate (daily)",
        "frequency": "D",
        "unit": "EUR per CHF",
    },
    "ECB:EXR:SEK.EUR.SP00.A": {
        "flow": "EXR",
        "key": "D.SEK.EUR.SP00.A",
        "name": "SEK/EUR reference rate (daily)",
        "frequency": "D",
        "unit": "EUR per SEK",
    },
    "ECB:EXR:NOK.EUR.SP00.A": {
        "flow": "EXR",
        "key": "D.NOK.EUR.SP00.A",
        "name": "NOK/EUR reference rate (daily)",
        "frequency": "D",
        "unit": "EUR per NOK",
    },
    "ECB:EXR:CNY.EUR.SP00.A": {
        "flow": "EXR",
        "key": "D.CNY.EUR.SP00.A",
        "name": "CNY/EUR reference rate (daily)",
        "frequency": "D",
        "unit": "EUR per CNY",
    },
    "ECB:ICP:U2.N.000000.4.ANR": {
        "flow": "ICP",
        "key": "M.U2.N.000000.4.ANR",
        "name": "HICP - Overall index, annual rate of change (EA, monthly)",
        "frequency": "M",
        "unit": "% y/y",
    },
    "ECB:ICP:DE.N.000000.4.ANR": {
        "flow": "ICP",
        "key": "M.DE.N.000000.4.ANR",
        "name": "HICP - Overall index, annual rate of change (Germany, monthly)",
        "frequency": "M",
        "unit": "% y/y",
    },
    "ECB:ICP:FR.N.000000.4.ANR": {
        "flow": "ICP",
        "key": "M.FR.N.000000.4.ANR",
        "name": "HICP - Overall index, annual rate of change (France, monthly)",
        "frequency": "M",
        "unit": "% y/y",
    },
    "ECB:ICP:IT.N.000000.4.ANR": {
        "flow": "ICP",
        "key": "M.IT.N.000000.4.ANR",
        "name": "HICP - Overall index, annual rate of change (Italy, monthly)",
        "frequency": "M",
        "unit": "% y/y",
    },
    "ECB:ICP:ES.N.000000.4.ANR": {
        "flow": "ICP",
        "key": "M.ES.N.000000.4.ANR",
        "name": "HICP - Overall index, annual rate of change (Spain, monthly)",
        "frequency": "M",
        "unit": "% y/y",
    },
    "ECB:FM:B.U2.EUR.4F.KR.MRR_FR.LEV": {
        "flow": "FM",
        "key": "B.U2.EUR.4F.KR.MRR_FR.LEV",
        "name": "ECB Main Refinancing Operations Rate (MRR)",
        "frequency": "D",
        "unit": "%",
    },
    "ECB:FM:B.U2.EUR.4F.KR.DFR.LEV": {
        "flow": "FM",
        "key": "B.U2.EUR.4F.KR.DFR.LEV",
        "name": "ECB Deposit Facility Rate (DFR)",
        "frequency": "D",
        "unit": "%",
    },
}


class ECBVendor(Vendor):
    """ECB SDMX 2.1 adapter. No API key required."""

    code = "ecb"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url: str = (base_url or get_settings().ecb_sdmx_base).rstrip("/")

    @http_retry()
    def _get_csv(self, path: str, params: dict[str, Any]) -> str:
        with limit(self.code, ECB_RATE_PER_MIN, ECB_BURST):
            q = {**params, "format": "csvdata"}
            r = httpx.get(f"{self.base_url}{path}", params=q, timeout=30.0)
            r.raise_for_status()
            return r.text

    def healthcheck(self) -> bool:
        """Request a known stable series; verify the response has data rows."""
        try:
            csv = self._get_csv(
                "/data/EXR/D.USD.EUR.SP00.A",
                {"startPeriod": "2024-01-01", "endPeriod": "2024-01-31"},
            )
            # Header line + at least one data row.
            return csv.lstrip().startswith("KEY,") and len(csv.strip().splitlines()) > 1
        except Exception as e:
            log.error("ecb.healthcheck_failed", error=str(e))
            return False

    def fetch(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        """Fetch an ECB series.

        ``symbol`` is either a key from ECB_SERIES (e.g. ``"ECB:EXR:USD.EUR.SP00.A"``)
        or a raw ``"FLOW/KEY"`` string (e.g. ``"EXR/D.USD.EUR.SP00.A"``).
        """
        flow, key = self._resolve_symbol(symbol)
        if flow is None or key is None:
            log.warning("ecb.unknown_symbol", symbol=symbol)
            return pl.DataFrame(schema={"date": pl.Date, "value": pl.Float64})

        csv_text = self._get_csv(
            f"/data/{flow}/{key}",
            {"startPeriod": start.isoformat(), "endPeriod": end.isoformat()},
        )
        return _parse_ecb_csv(csv_text)

    def _resolve_symbol(self, symbol: str) -> tuple[str | None, str | None]:
        if symbol in ECB_SERIES:
            entry = ECB_SERIES[symbol]
            return entry["flow"], entry["key"]
        if "/" in symbol:
            parts = symbol.split("/", 1)
            return parts[0], parts[1]
        return None, None


def _parse_ecb_csv(csv_text: str) -> pl.DataFrame:
    """Parse ECB SDMX CSV into {date, value} polars DataFrame.

    Handles both ``YYYY-MM-DD`` (daily) and ``YYYY-MM`` (monthly) date strings.
    Uses ``pl.coalesce`` so failed parses become null instead of raising.
    """
    df = pl.read_csv(
        csv_text.encode("utf-8"),
        columns=["TIME_PERIOD", "OBS_VALUE"],
        dtypes={"TIME_PERIOD": pl.Utf8, "OBS_VALUE": pl.Float64},
    )
    if df.is_empty():
        return pl.DataFrame(schema={"date": pl.Date, "value": pl.Float64})

    df = df.with_columns(
        pl.coalesce(
            pl.col("TIME_PERIOD").str.strptime(pl.Date, format="%Y-%m-%d", strict=False),
            pl.col("TIME_PERIOD").str.strptime(pl.Date, format="%Y-%m", strict=False),
        ).alias("date")
    )
    return df.select(
        pl.col("date"),
        pl.col("OBS_VALUE").cast(pl.Float64, strict=False).alias("value"),
    )


__all__ = ["ECB_SERIES", "ECBVendor"]
