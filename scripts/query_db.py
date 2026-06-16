"""Query the finance_data DB and print a few time series.

Standalone CLI. Always produces output:

  - If ``macro_observations`` is empty and FRED_API_KEY is set in .env:
    live-fetch 2-3 FRED series and insert.
  - If ``macro_observations`` is empty and no FRED_API_KEY:
    insert clearly-marked synthetic demo data so the script still
    shows something useful.
  - If ``macro_observations`` already has rows:
    read and display only.

Usage:
    python scripts/query_db.py
    python scripts/query_db.py --series DEMO:DGS3MO DEMO:UNRATE
    python scripts/query_db.py --tail 20
    python scripts/query_db.py --no-seed           # read-only
    python scripts/query_db.py --reset-demo         # drop demo rows first
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from tabulate import tabulate

from finance_data.db import (
    Instrument,
    InstrumentIdentifier,
    MacroObservation,
    MacroSeries,
    PricesDaily,
    Vendor,
    session_scope,
)
from finance_data.utils.config import get_settings
from finance_data.utils.logging import configure_logging, get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Demo content (synthetic, clearly marked, easy to remove)
# ---------------------------------------------------------------------------

DEMO_SERIES: list[dict[str, Any]] = [
    {
        "series_id": "DEMO:DGS3MO",
        "vendor_key": "DGS3MO",
        "name": "DEMO 3-Month Treasury (synthetic)",
        "source": "demo",
        "frequency": "D",
        "unit": "%",
        "start_value": 5.0,
        "drift": 0.002,
        "vol": 0.05,
    },
    {
        "series_id": "DEMO:CPIAUCSL",
        "vendor_key": "CPIAUCSL",
        "name": "DEMO CPI All Urban Consumers (synthetic)",
        "source": "demo",
        "frequency": "D",
        "unit": "Index",
        "start_value": 310.0,
        "drift": 0.10,
        "vol": 0.15,
    },
    {
        "series_id": "DEMO:UNRATE",
        "vendor_key": "UNRATE",
        "name": "DEMO Unemployment Rate (synthetic)",
        "source": "demo",
        "frequency": "D",
        "unit": "%",
        "start_value": 4.0,
        "drift": -0.001,
        "vol": 0.04,
    },
]


def _seed_demo(days: int = 200, seed: int = 42) -> int:
    """Insert ~`days` synthetic observations per demo series.

    Returns the number of rows inserted across all series.
    """
    rng = random.Random(seed)
    total = 0
    today = date.today()
    start = today - timedelta(days=days - 1)

    with session_scope() as s:
        s.merge(
            Vendor(
                code="demo",
                license="N/A (synthetic, generated at runtime)",
                homepage="",
            )
        )
        s.flush()

        for entry in DEMO_SERIES:
            s.merge(
                MacroSeries(
                    series_id=entry["series_id"],
                    name=entry["name"],
                    source=entry["source"],
                    frequency=entry["frequency"],
                    unit=entry["unit"],
                )
            )
        s.flush()

        for entry in DEMO_SERIES:
            value = entry["start_value"]
            for i in range(days):
                d = start + timedelta(days=i)
                if d.weekday() >= 5:  # skip weekends
                    continue
                value = max(0.0, value + rng.gauss(entry["drift"], entry["vol"]))
                s.merge(
                    MacroObservation(
                        series_id=entry["series_id"],
                        date=d,
                        value=round(value, 6),
                    )
                )
                total += 1
    return total


def _seed_from_fred(api_key: str, years: int = 5) -> int:
    """Fetch a small set of real FRED series and insert.

    Returns the number of rows inserted. Returns 0 if healthcheck fails.
    """
    from finance_data.vendors.fred import FredVendor

    fred = FredVendor(api_key=api_key)
    if not fred.healthcheck():
        log.error("fred_healthcheck_failed_skip_seed")
        return 0

    targets = [
        # (series_id, vendor_key, name, frequency, unit)
        ("FRED:DGS3MO", "DGS3MO", "3-Month Treasury Constant Maturity Rate", "D", "%"),
        ("FRED:DGS10", "DGS10", "10-Year Treasury Constant Maturity Rate", "D", "%"),
        ("FRED:FEDFUNDS", "FEDFUNDS", "Federal Funds Effective Rate (monthly)", "M", "%"),
        ("FRED:CPIAUCSL", "CPIAUCSL", "CPI All Urban Consumers (NSA, monthly)", "M", "Index"),
        ("FRED:UNRATE", "UNRATE", "Unemployment Rate (monthly)", "M", "%"),
    ]
    end = date.today()
    start = end - timedelta(days=int(years * 365.25))

    inserted = 0
    with session_scope() as s:
        s.merge(
            Vendor(
                code="fred",
                license="Public Domain (US Government)",
                homepage="https://fred.stlouisfed.org",
            )
        )
        s.flush()
        for sid, _vid, name, freq, unit in targets:
            s.merge(
                MacroSeries(
                    series_id=sid,
                    name=name,
                    source="fred",
                    frequency=freq,
                    unit=unit,
                )
            )
        s.flush()

        for sid, vid, *_ in targets:
            df = fred.fetch(vid, start, end)
            for row in df.iter_rows(named=True):
                if row["value"] is None:
                    continue
                s.merge(
                    MacroObservation(
                        series_id=sid,
                        date=row["date"],
                        value=float(row["value"]),
                    )
                )
                inserted += 1
    return inserted


def _seed_from_ecb(years: int = 5) -> int:
    """Fetch a small set of real ECB series and insert. No API key required.

    Returns the number of rows inserted. Returns 0 if healthcheck fails.
    """
    from finance_data.vendors.ecb import ECB_SERIES, ECBVendor

    ecb = ECBVendor()
    if not ecb.healthcheck():
        log.error("ecb_healthcheck_failed_skip_seed")
        return 0

    targets = [
        # (our series_id, name, unit, years_to_fetch)
        ("ECB:EXR:USD.EUR.SP00.A", "USD/EUR reference rate (daily)", "EUR per USD", years),
        ("ECB:EXR:GBP.EUR.SP00.A", "GBP/EUR reference rate (daily)", "EUR per GBP", years),
        ("ECB:EXR:JPY.EUR.SP00.A", "JPY/EUR reference rate (daily)", "EUR per 100 JPY", years),
        (
            "ECB:ICP:U2.N.000000.4.ANR",
            "HICP - Overall index, annual rate of change (EA, monthly)",
            "% y/y",
            years,
        ),
    ]
    end = date.today()

    inserted = 0
    with session_scope() as s:
        s.merge(
            Vendor(
                code="ecb",
                license="© European Central Bank, CC BY 4.0",
                homepage="https://data.ecb.europa.eu",
            )
        )
        s.flush()
        for sid, name, unit, _yrs in targets:
            entry = ECB_SERIES[sid]
            s.merge(
                MacroSeries(
                    series_id=sid,
                    name=name,
                    source="ecb",
                    frequency=entry["frequency"],
                    unit=unit,
                )
            )
        s.flush()

        for sid, _name, _unit, yrs in targets:
            start = end - timedelta(days=int(yrs * 365.25))
            df = ecb.fetch(sid, start, end)
            for row in df.iter_rows(named=True):
                if row["value"] is None:
                    continue
                s.merge(
                    MacroObservation(
                        series_id=sid,
                        date=row["date"],
                        value=float(row["value"]),
                    )
                )
                inserted += 1
    return inserted


def _seed_from_yahoo(years: int = 2) -> int:
    """Fetch a small set of Yahoo Finance tickers (OHLCV) and insert.

    Populates ``instruments``, ``instrument_identifiers`` and ``prices_daily``.
    Returns the number of price rows inserted.
    """
    from finance_data.vendors.yahoo import YahooVendor

    targets = [
        # (yahoo_symbol, name, asset_class, currency, exchange)
        ("AAPL", "Apple Inc.", "equity", "USD", "NASDAQ"),
        ("MSFT", "Microsoft Corp.", "equity", "USD", "NASDAQ"),
        ("^GSPC", "S&P 500 Index", "index", "USD", "INDEX"),
    ]
    end = date.today()
    start = end - timedelta(days=int(years * 365.25))

    yahoo = YahooVendor()
    try:
        yahoo.healthcheck()
    except Exception:
        log.error("yahoo_healthcheck_failed_skip_seed")
        return 0

    inserted = 0
    with session_scope() as s:
        s.merge(
            Vendor(
                code="yahoo",
                license="Yahoo ToS — privater Gebrauch, keine Weiterverteilung",
                homepage="https://finance.yahoo.com",
            )
        )
        s.flush()

        for symbol, name, asset_class, currency, _exchange in targets:
            # lookup_or_create instrument
            inst = (
                s.query(Instrument)
                .join(
                    InstrumentIdentifier,
                    InstrumentIdentifier.instrument_id == Instrument.instrument_id,
                )
                .filter(
                    InstrumentIdentifier.scheme == "YAHOO",
                    InstrumentIdentifier.value == symbol,
                )
                .one_or_none()
            )
            if inst is None:
                inst = Instrument(
                    asset_class=asset_class,
                    name=name,
                    currency=currency,
                )
                s.add(inst)
                s.flush()
                s.add(
                    InstrumentIdentifier(
                        instrument_id=inst.instrument_id,
                        scheme="YAHOO",
                        value=symbol,
                    )
                )
                s.flush()
            instrument_id = inst.instrument_id

            try:
                df = yahoo.fetch(symbol, start, end)
            except Exception as e:
                log.warning("yahoo.fetch_failed", symbol=symbol, error=str(e))
                continue

            for row in df.iter_rows(named=True):
                if row["close"] is None or row["date"] is None:
                    continue
                s.merge(
                    PricesDaily(
                        instrument_id=instrument_id,
                        date=row["date"],
                        open=row.get("open"),
                        high=row.get("high"),
                        low=row.get("low"),
                        close=row["close"],
                        adjusted_close=row.get("adjusted_close"),
                        volume=row.get("volume"),
                        vendor_id=s.query(Vendor).filter(Vendor.code == "yahoo").one().vendor_id,
                    )
                )
                inserted += 1
    return inserted


def _reset_demo() -> int:
    """Delete all demo rows (observations + series + vendor)."""
    deleted = 0
    with session_scope() as s:
        res = s.execute(delete(MacroObservation).where(MacroObservation.series_id.like("DEMO:%")))
        deleted += res.rowcount or 0
        s.execute(delete(MacroSeries).where(MacroSeries.series_id.like("DEMO:%")))
        s.execute(delete(Vendor).where(Vendor.code == "demo"))
    return deleted


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def _fetch_series(series_filter: list[str] | None) -> list[dict[str, Any]]:
    """Return one dict per series with metadata, observations, and stats."""
    with session_scope() as s:
        if series_filter:
            stmt = select(MacroSeries).where(MacroSeries.series_id.in_(series_filter))
        else:
            stmt = select(MacroSeries).order_by(MacroSeries.series_id)
        meta_rows = s.execute(stmt).scalars().all()

        results: list[dict[str, Any]] = []
        for meta in meta_rows:
            obs = (
                s.execute(
                    select(MacroObservation)
                    .where(MacroObservation.series_id == meta.series_id)
                    .order_by(MacroObservation.date)
                )
                .scalars()
                .all()
            )
            values = [float(o.value) for o in obs if o.value is not None]
            if values:
                first_val = values[0]
                last_val = values[-1]
                change = last_val - first_val
                change_pct = (change / first_val * 100.0) if first_val else 0.0
                min_v = min(values)
                max_v = max(values)
                mean_v = sum(values) / len(values)
            else:
                first_val = last_val = change = change_pct = min_v = max_v = mean_v = None

            results.append(
                {
                    "series_id": meta.series_id,
                    "name": meta.name,
                    "source": meta.source,
                    "unit": meta.unit,
                    "frequency": meta.frequency,
                    "count": len(obs),
                    "first_date": obs[0].date if obs else None,
                    "last_date": obs[-1].date if obs else None,
                    "min": min_v,
                    "max": max_v,
                    "mean": mean_v,
                    "first_value": first_val,
                    "last_value": last_val,
                    "change": change,
                    "change_pct": change_pct,
                    "_obs": obs,
                }
            )
    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _fmt(v: Any, digits: int = 4) -> str:
    if v is None:
        return "n/a"
    return f"{v:,.{digits}f}"


def _fmt_pct(v: Any) -> str:
    if v is None:
        return "n/a"
    if abs(v) > 999:
        # Clamp absurd % changes (e.g. ~0% baseline → 9350% on small moves).
        return f"{v:+,.0f}%" if abs(v) < 1_000_000 else "—"
    return f"{v:+.2f}%"


def _print_summary(series_list: list[dict[str, Any]], tail: int) -> None:
    print()
    print("=" * 80)
    print("finance_data — Time Series Query")
    print("=" * 80)

    overview = [
        [
            s["series_id"],
            (s["name"] or "")[:42],
            s["count"],
            s["first_date"].isoformat() if s["first_date"] else "n/a",
            s["last_date"].isoformat() if s["last_date"] else "n/a",
            _fmt(s["last_value"]),
            _fmt_pct(s["change_pct"]),
            _fmt(s["mean"]),
            _fmt(s["min"]),
            _fmt(s["max"]),
        ]
        for s in series_list
    ]
    print()
    print(
        tabulate(
            overview,
            headers=[
                "Series",
                "Name",
                "Count",
                "First",
                "Last",
                "Latest",
                "Δ %",
                "Mean",
                "Min",
                "Max",
            ],
            tablefmt="github",
        )
    )

    for s in series_list:
        print()
        print(f"--- {s['series_id']} — last {min(tail, s['count'])} of {s['count']} rows ---")
        obs = s["_obs"][-tail:]
        rows = [
            [o.date.isoformat(), _fmt(o.value, 6) if o.value is not None else "(missing)"]
            for o in obs
        ]
        print(tabulate(rows, headers=["date", "value"], tablefmt="github"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Query finance_data and print a few time series.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--series",
        nargs="*",
        default=None,
        help="Restrict to these series_ids (default: all in DB)",
    )
    parser.add_argument(
        "--tail",
        type=int,
        default=10,
        help="Show last N values per series (default: 10)",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Do not write demo/seed data even if table is empty",
    )
    parser.add_argument(
        "--reset-demo",
        action="store_true",
        help="Delete all DEMO:* rows before running",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    if args.reset_demo:
        n = _reset_demo()
        print(f"reset-demo: removed {n} demo observation rows")

    with session_scope() as s:
        n_obs = s.execute(select(func.count()).select_from(MacroObservation)).scalar() or 0

    if n_obs == 0 and args.no_seed:
        print("macro_observations is empty and --no-seed given → nothing to show")
        return 0

    if n_obs == 0:
        total_inserted = 0
        if settings.fred_api_key:
            print("macro_observations is empty and FRED_API_KEY is set → seeding real FRED data")
            n = _seed_from_fred(settings.fred_api_key)
            print(f"  inserted {n} FRED observations")
            total_inserted += n
        print("seeding real ECB data (no API key required)")
        n = _seed_from_ecb()
        print(f"  inserted {n} ECB observations")
        total_inserted += n
        print("seeding real Yahoo Finance data (AAPL, MSFT, ^GSPC → prices_daily)")
        n = _seed_from_yahoo()
        print(f"  inserted {n} Yahoo OHLCV rows")
        total_inserted += n
        if total_inserted == 0:
            print("ECB and FRED seeders failed → falling back to synthetic demo data")
            n = _seed_demo()
            print(f"  inserted {n} synthetic observations (DEMO:*)")
        elif not settings.fred_api_key:
            print("  (set FRED_API_KEY in .env to also seed FRED series)")
    elif n_obs == 0 and args.no_seed:
        print("macro_observations is empty and --no-seed given → nothing to show")
        return 0

    series_list = _fetch_series(args.series)
    if not series_list:
        print("No series match the filter.")
        return 1

    _print_summary(series_list, tail=args.tail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
