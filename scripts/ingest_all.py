"""Ingest all series from config into deephold_db.

Phases:
  1. FRED: macro, bond_gov, money_market, fx, vol  (from series_registry.yaml)
  2. ECB:  fx, money_market, macro                  (from series_registry.yaml)
  3. Yahoo Non-Equity: index, commodity, fx, bond   (from series_registry.yaml)
  4. Yahoo Equities: equity OHLCV                   (from tickers.yaml)

Usage:
  python scripts/ingest_all.py                  # all phases
  python scripts/ingest_all.py --phase fred     # only FRED
  python scripts/ingest_all.py --phase ecb      # only ECB
  python scripts/ingest_all.py --phase yahoo-ne # only Yahoo non-equity
  python scripts/ingest_all.py --phase yahoo-eq # only Yahoo equities
  python scripts/ingest_all.py --full-sp500     # also fetch full S&P 500 from Wikipedia
  python scripts/ingest_all.py --years 30       # override history depth
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import yaml
from sqlalchemy import func, select, text

from deephold_db.db import (
    BondYield,
    FxRateDaily,
    Instrument,
    InstrumentIdentifier,
    MacroObservation,
    MacroSeries,
    PricesDaily,
    Vendor,
    session_scope,
)
from deephold_db.utils.config import get_settings
from deephold_db.utils.logging import configure_logging, get_logger

log = get_logger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
SERIES_REGISTRY = CONFIG_DIR / "series_registry.yaml"
TICKERS = CONFIG_DIR / "tickers.yaml"

BATCH_SIZE = 1000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _ensure_vendor(session, code: str, name: str, license_text: str, homepage: str) -> int:
    row = session.query(Vendor).filter(Vendor.code == code).one_or_none()
    if row is not None:
        return row.vendor_id
    v = Vendor(code=code, license=license_text, homepage=homepage)
    session.add(v)
    session.flush()
    return v.vendor_id


def _upsert_instrument(session, asset_class: str, name: str, currency: str) -> int:
    row = (
        session.query(Instrument)
        .filter(Instrument.name == name, Instrument.asset_class == asset_class)
        .one_or_none()
    )
    if row is not None:
        return row.instrument_id
    inst = Instrument(asset_class=asset_class, name=name, currency=currency)
    session.add(inst)
    session.flush()
    return inst.instrument_id


def _upsert_identifier(session, instrument_id: int, scheme: str, value: str) -> None:
    row = (
        session.query(InstrumentIdentifier)
        .filter(
            InstrumentIdentifier.scheme == scheme,
            InstrumentIdentifier.value == value,
        )
        .one_or_none()
    )
    if row is not None:
        return
    session.add(InstrumentIdentifier(instrument_id=instrument_id, scheme=scheme, value=value))
    session.flush()


def _upsert_macro_series(session, series_id: str, name: str, source: str, frequency: str, unit: str) -> None:
    row = session.query(MacroSeries).filter(MacroSeries.series_id == series_id).one_or_none()
    if row is not None:
        return
    session.add(MacroSeries(series_id=series_id, name=name, source=source, frequency=frequency, unit=unit))
    session.flush()


# ---------------------------------------------------------------------------
# Bulk UPSERT helpers
# ---------------------------------------------------------------------------


def _bulk_upsert_macro_observations(session, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = text("""
        INSERT INTO macro_observations (series_id, date, value)
        VALUES (:series_id, :date, :value)
        ON CONFLICT (series_id, date) DO UPDATE SET value = EXCLUDED.value
    """)
    count = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        session.execute(stmt, batch)
        count += len(batch)
    return count


def _bulk_upsert_bond_yields(session, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = text("""
        INSERT INTO bond_yields (instrument_id, date, yield)
        VALUES (:instrument_id, :date, :yield)
        ON CONFLICT (instrument_id, date) DO UPDATE SET yield = EXCLUDED.yield
    """)
    count = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        session.execute(stmt, batch)
        count += len(batch)
    return count


def _bulk_upsert_fx_rates(session, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = text("""
        INSERT INTO fx_rates_daily (ccy_from, ccy_to, date, rate, vendor_id)
        VALUES (:ccy_from, :ccy_to, :date, :rate, :vendor_id)
        ON CONFLICT (ccy_from, ccy_to, date)
        DO UPDATE SET rate = EXCLUDED.rate, vendor_id = EXCLUDED.vendor_id
    """)
    count = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        session.execute(stmt, batch)
        count += len(batch)
    return count


def _bulk_upsert_prices_daily(session, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = text("""
        INSERT INTO prices_daily (instrument_id, date, open, high, low, close, adjusted_close, volume, vendor_id)
        VALUES (:instrument_id, :date, :open, :high, :low, :close, :adjusted_close, :volume, :vendor_id)
        ON CONFLICT (instrument_id, date)
        DO UPDATE SET open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                      close = EXCLUDED.close, adjusted_close = EXCLUDED.adjusted_close,
                      volume = EXCLUDED.volume, vendor_id = EXCLUDED.vendor_id
    """)
    count = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        session.execute(stmt, batch)
        count += len(batch)
    return count


# ---------------------------------------------------------------------------
# FRED FX currency mapping
# ---------------------------------------------------------------------------

_FRED_DEX_CURRENCY_MAP = {
    "DEXUSEU": "EUR", "DEXJPUS": "JPY", "DEXUSUK": "GBP",
    "DEXCHUS": "CHF", "DEXCAUS": "CAD", "DEXNOUS": "NOK",
    "DEXSDUS": "SEK", "DEXBZUS": "BRL", "DEXKOUS": "KRW",
    "DEXMXUS": "MXN", "DEXINUS": "INR", "DEXCNUS": "CNY",
    "DEXTHUS": "THB", "DEXSZUS": "HUF",
}


# ---------------------------------------------------------------------------
# Phase 1: FRED
# ---------------------------------------------------------------------------


def ingest_fred(registry: dict, years: int) -> int:
    from deephold_db.vendors.fred import FredVendor

    settings = get_settings()
    fred = FredVendor(api_key=settings.fred_api_key)
    if not fred.healthcheck():
        log.error("fred.healthcheck_failed")
        return 0

    end = date.today()
    start = end - timedelta(days=int(years * 365.25))
    series_list = [s for s in registry["series"] if s["source"] == "fred"]
    total = 0

    for i, entry in enumerate(series_list, 1):
        series_id = entry["series_id"]
        vendor_key = entry["vendor_key"]
        asset_class = entry["asset_class"]
        name = entry["name"]
        unit = entry.get("unit", "")
        freq = entry.get("frequency", "D")
        print(f"  [{i}/{len(series_list)}] {series_id} ({asset_class}) ...", end=" ", flush=True)

        try:
            df = fred.fetch(vendor_key, start, end)
        except Exception as e:
            log.warning("fred.fetch_failed", series_id=series_id, error=str(e))
            print(f"FAILED ({e})")
            continue

        if df.is_empty():
            print("EMPTY")
            continue

        rows: list[dict] = []
        count = 0

        try:
            with session_scope() as session:
                fred_vid = _ensure_vendor(session, "fred", "Federal Reserve Economic Data", "Public Domain (US Government)", "https://fred.stlouisfed.org")

                if asset_class in ("macro", "money_market", "vol"):
                    _upsert_macro_series(session, series_id, name, "fred", freq, unit)
                    for row in df.iter_rows(named=True):
                        if row["value"] is None:
                            continue
                        rows.append({"series_id": series_id, "date": row["date"], "value": float(row["value"])})
                    count = _bulk_upsert_macro_observations(session, rows)

                elif asset_class == "bond_gov":
                    inst_id = _upsert_instrument(session, "bond_gov", name, "USD")
                    _upsert_identifier(session, inst_id, "FRED", vendor_key)
                    for row in df.iter_rows(named=True):
                        if row["value"] is None:
                            continue
                        rows.append({"instrument_id": inst_id, "date": row["date"], "yield": float(row["value"])})
                    count = _bulk_upsert_bond_yields(session, rows)

                elif asset_class == "fx":
                    ccy_from = "USD"
                    ccy_to = "XXX"
                    if vendor_key.startswith("DEX"):
                        ccy_from = "USD"
                        ccy_to = _FRED_DEX_CURRENCY_MAP.get(vendor_key, "XXX")
                    else:
                        ccy_from = unit.split(" per ")[-1].split(" ")[0] if " per " in unit else "USD"
                        ccy_to = "USD" if ccy_from != "USD" else (unit.split(" per ")[0].strip() if " per " in unit else "EUR")
                    for row in df.iter_rows(named=True):
                        if row["value"] is None:
                            continue
                        rows.append({"ccy_from": ccy_from, "ccy_to": ccy_to, "date": row["date"], "rate": float(row["value"]), "vendor_id": fred_vid})
                    count = _bulk_upsert_fx_rates(session, rows)

                else:
                    print(f"UNKNOWN_ASSET_CLASS({asset_class})")
                    continue

        except Exception as e:
            log.warning("fred.series_failed", series_id=series_id, error=str(e))
            print(f"FAILED ({e})")
            continue

        total += count
        print(f"{count} rows")

    return total


# ---------------------------------------------------------------------------
# Phase 2: ECB
# ---------------------------------------------------------------------------


def ingest_ecb(registry: dict, years: int) -> int:
    from deephold_db.vendors.ecb import ECBVendor

    ecb = ECBVendor()
    if not ecb.healthcheck():
        log.error("ecb.healthcheck_failed")
        return 0

    end = date.today()
    start = end - timedelta(days=int(years * 365.25))
    series_list = [s for s in registry["series"] if s["source"] == "ecb"]
    total = 0

    for i, entry in enumerate(series_list, 1):
        series_id = entry["series_id"]
        asset_class = entry["asset_class"]
        name = entry["name"]
        unit = entry.get("unit", "")
        freq = entry.get("frequency", "D")
        print(f"  [{i}/{len(series_list)}] {series_id} ({asset_class}) ...", end=" ", flush=True)

        try:
            df = ecb.fetch(series_id, start, end)
        except Exception as e:
            log.warning("ecb.fetch_failed", series_id=series_id, error=str(e))
            print(f"FAILED ({e})")
            continue

        if df.is_empty():
            print("EMPTY")
            continue

        rows: list[dict] = []
        count = 0

        try:
            with session_scope() as session:
                ecb_vid = _ensure_vendor(session, "ecb", "ECB Statistical Data Warehouse", "© ECB, CC BY 4.0", "https://data.ecb.europa.eu")

                if asset_class in ("macro", "money_market"):
                    _upsert_macro_series(session, series_id, name, "ecb", freq, unit)
                    for row in df.iter_rows(named=True):
                        if row["value"] is None:
                            continue
                        rows.append({"series_id": series_id, "date": row["date"], "value": float(row["value"])})
                    count = _bulk_upsert_macro_observations(session, rows)

                elif asset_class == "fx":
                    # ECB reports X/EUR where X may be "100 JPY" for JPY.
                    # Normalize: extract currency code, convert rate if needed.
                    if "100 JPY" in unit:
                        ccy_from = "JPY"
                        ccy_to = "EUR"
                        rate_divisor = 100.0
                    else:
                        rate_divisor = 1.0
                        ccy_from = unit.split(" per ")[-1].strip() if " per " in unit else "EUR"
                        ccy_to = "EUR" if ccy_from != "EUR" else "XXX"
                        if ccy_from == ccy_to:
                            ccy_from, ccy_to = "XXX", "EUR"
                    for row in df.iter_rows(named=True):
                        if row["value"] is None:
                            continue
                        rows.append({"ccy_from": ccy_from, "ccy_to": ccy_to, "date": row["date"], "rate": float(row["value"]) / rate_divisor, "vendor_id": ecb_vid})
                    count = _bulk_upsert_fx_rates(session, rows)

                elif asset_class == "bond_gov":
                    inst_id = _upsert_instrument(session, "bond_gov", name, "EUR")
                    _upsert_identifier(session, inst_id, "ECB", series_id)
                    for row in df.iter_rows(named=True):
                        if row["value"] is None:
                            continue
                        rows.append({"instrument_id": inst_id, "date": row["date"], "yield": float(row["value"])})
                    count = _bulk_upsert_bond_yields(session, rows)

                else:
                    print(f"UNKNOWN_ASSET_CLASS({asset_class})")
                    continue

        except Exception as e:
            log.warning("ecb.series_failed", series_id=series_id, error=str(e))
            print(f"FAILED ({e})")
            continue

        total += count
        print(f"{count} rows")

    return total


# ---------------------------------------------------------------------------
# Phase 3: Yahoo Non-Equity (indices, commodities, FX, credit ETFs)
# ---------------------------------------------------------------------------


def ingest_yahoo_non_equity(registry: dict, years: int) -> int:
    from deephold_db.vendors.yahoo import YahooVendor

    yahoo = YahooVendor()
    end = date.today()
    start = end - timedelta(days=int(years * 365.25))
    series_list = [s for s in registry["series"] if s["source"] == "yahoo" and s["asset_class"] not in ("equity",)]
    total = 0

    for i, entry in enumerate(series_list, 1):
        series_id = entry["series_id"]
        vendor_key = entry["vendor_key"]
        name = entry["name"]
        asset_class = entry["asset_class"]
        currency = entry.get("unit", "USD")
        if "USD" in currency or currency in ("Index", "USD/troy oz", "USD/bbl", "USD/MMBtu", "USD/bu", "USD/lb"):
            currency = "USD"
        elif "EUR" in currency:
            currency = "EUR"
        elif "JPY" in currency:
            currency = "JPY"
        elif "GBP" in currency:
            currency = "GBP"
        elif "CHF" in currency:
            currency = "CHF"

        print(f"  [{i}/{len(series_list)}] {series_id} ({asset_class}) ...", end=" ", flush=True)

        try:
            df = yahoo.fetch(vendor_key, start, end)
        except Exception as e:
            log.warning("yahoo.fetch_failed", series_id=series_id, error=str(e))
            print(f"FAILED ({e})")
            time.sleep(2)
            continue

        if df.is_empty():
            print("EMPTY")
            continue

        rows: list[dict] = []
        count = 0

        try:
            with session_scope() as session:
                yahoo_vid = _ensure_vendor(session, "yahoo", "Yahoo Finance (via yfinance, privat)", "Yahoo ToS — privater Gebrauch", "https://finance.yahoo.com")

                if asset_class == "fx":
                    if len(vendor_key.replace("=X", "")) == 6:
                        pair = vendor_key.replace("=X", "")
                        ccy_from = pair[:3]
                        ccy_to = pair[3:]
                    else:
                        ccy_from = "USD"
                        ccy_to = "XXX"

                    for row in df.iter_rows(named=True):
                        if row["close"] is None or row["date"] is None:
                            continue
                        rows.append({"ccy_from": ccy_from, "ccy_to": ccy_to, "date": row["date"], "rate": float(row["close"]), "vendor_id": yahoo_vid})
                    count = _bulk_upsert_fx_rates(session, rows)

                else:
                    inst_id = _upsert_instrument(session, asset_class, name, currency)
                    _upsert_identifier(session, inst_id, "YAHOO", vendor_key)
                    for row in df.iter_rows(named=True):
                        if row["close"] is None or row["date"] is None:
                            continue
                        rows.append({
                            "instrument_id": inst_id,
                            "date": row["date"],
                            "open": row.get("open"),
                            "high": row.get("high"),
                            "low": row.get("low"),
                            "close": row["close"],
                            "adjusted_close": row.get("adjusted_close"),
                            "volume": row.get("volume"),
                            "vendor_id": yahoo_vid,
                        })
                    count = _bulk_upsert_prices_daily(session, rows)

        except Exception as e:
            log.warning("yahoo.series_failed", series_id=series_id, error=str(e))
            print(f"FAILED ({e})")
            time.sleep(2)
            continue

        total += count
        print(f"{count} rows")
        time.sleep(1)

    return total


# ---------------------------------------------------------------------------
# Phase 4+5: Yahoo Equities
# ---------------------------------------------------------------------------


def ingest_yahoo_equities(tickers_cfg: dict, years: int, full_sp500: bool = False) -> int:
    from deephold_db.vendors.yahoo import YahooVendor

    yahoo = YahooVendor()
    end = date.today()
    start = end - timedelta(days=int(years * 365.25))

    all_tickers = []
    for region_data in tickers_cfg.get("regions", {}).values():
        for t in region_data.get("tickers", []):
            all_tickers.append(t)

    if full_sp500:
        sp500 = _fetch_sp500_tickers()
        existing_yahoo = {t["yahoo"] for t in all_tickers}
        for entry in sp500:
            if entry["yahoo"] not in existing_yahoo:
                all_tickers.append(entry)
                existing_yahoo.add(entry["yahoo"])

    print(f"  Total tickers to ingest: {len(all_tickers)}")

    BATCH_SIZE_FETCH = 50
    total = 0
    batch_num = 0

    for batch_start in range(0, len(all_tickers), BATCH_SIZE_FETCH):
        batch = all_tickers[batch_start : batch_start + BATCH_SIZE_FETCH]
        batch_num += 1
        symbols = [t["yahoo"] for t in batch]
        print(f"  Batch {batch_num} ({batch_start + 1}-{batch_start + len(batch)}/{len(all_tickers)}): {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}")

        try:
            results = yahoo.fetch_many(symbols, start, end)
        except Exception as e:
            log.error("yahoo.fetch_many_failed_batch", error=str(e))
            print(f"    Batch failed, falling back to individual fetches...")
            results = {}
            for t, sym in zip(batch, symbols):
                try:
                    results[sym] = yahoo.fetch(sym, start, end)
                    time.sleep(0.5)
                except Exception as e2:
                    log.warning("yahoo.fetch_failed_single", symbol=sym, error=str(e2))
                    print(f"    {sym}: FAILED ({e2})")
                    results[sym] = None

        for ticker_entry, symbol in zip(batch, symbols):
            df = results.get(symbol)
            if df is None or df.is_empty():
                print(f"    {symbol}: EMPTY")
                continue

            rows: list[dict] = []
            count = 0

            try:
                with session_scope() as session:
                    yahoo_vid = _ensure_vendor(session, "yahoo", "Yahoo Finance (via yfinance, privat)", "Yahoo ToS — privater Gebrauch", "https://finance.yahoo.com")
                    inst_id = _upsert_instrument(session, ticker_entry.get("asset_class", "equity"), ticker_entry["name"], ticker_entry.get("currency", "USD"))
                    _upsert_identifier(session, inst_id, "YAHOO", symbol)

                    for row in df.iter_rows(named=True):
                        if row["close"] is None or row["date"] is None:
                            continue
                        rows.append({
                            "instrument_id": inst_id,
                            "date": row["date"],
                            "open": row.get("open"),
                            "high": row.get("high"),
                            "low": row.get("low"),
                            "close": row["close"],
                            "adjusted_close": row.get("adjusted_close"),
                            "volume": row.get("volume"),
                            "vendor_id": yahoo_vid,
                        })

                    count = _bulk_upsert_prices_daily(session, rows)

            except Exception as e:
                log.warning("yahoo.equity_failed", symbol=symbol, error=str(e))
                print(f"    {symbol}: FAILED ({e})")
                continue

            total += count
            print(f"    {symbol}: {count} rows")

        time.sleep(2)

    return total


def _fetch_sp500_tickers() -> list[dict]:
    """Fetch current S&P 500 constituents from Wikipedia."""
    import httpx
    from io import StringIO

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    print("  Fetching S&P 500 constituents from Wikipedia ...")
    try:
        r = httpx.get(url, timeout=30, follow_redirects=True, headers={"User-Agent": "deephold-db/1.0 (research; +https://github.com/bodomain/deephold-db)"})
        r.raise_for_status()
        try:
            import pandas as pd
            tables = pd.read_html(StringIO(r.text))
            df = tables[0]
            tickers = []
            for _, row in df.iterrows():
                symbol = str(row.get("Symbol", "")).replace(".", "-")
                name = str(row.get("Security", ""))
                sector = str(row.get("GICS Sector", ""))
                if not symbol or symbol == "nan":
                    continue
                tickers.append({
                    "symbol": symbol,
                    "name": name,
                    "currency": "USD",
                    "exchange": str(row.get("Exchange", "NYSE")),
                    "yahoo": symbol,
                    "sector": sector,
                })
            print(f"  Found {len(tickers)} S&P 500 constituents")
            return tickers
        except Exception as e:
            log.warning("sp500_parse_failed", error=str(e))
            print(f"  Wikipedia parse failed: {e}")
            return []
    except Exception as e:
        log.warning("sp500_fetch_failed", error=str(e))
        print(f"  Wikipedia fetch failed: {e}")
        return []


# ---------------------------------------------------------------------------
# DQ Summary
# ---------------------------------------------------------------------------


def dq_summary() -> None:
    with session_scope() as session:
        tables = [
            ("prices_daily", PricesDaily),
            ("macro_observations", MacroObservation),
            ("bond_yields", BondYield),
            ("fx_rates_daily", FxRateDaily),
            ("instruments", Instrument),
            ("instrument_identifiers", InstrumentIdentifier),
            ("macro_series", MacroSeries),
            ("vendors", Vendor),
        ]
        print("\n" + "=" * 60)
        print("deephold_db — Data Quality Summary")
        print("=" * 60)
        for table_name, model in tables:
            count = session.query(func.count()).select_from(model).scalar() or 0
            print(f"  {table_name:30s} {count:>12,} rows")

        print(f"\n  Date range (prices_daily):")
        try:
            min_date = session.query(func.min(PricesDaily.date)).scalar()
            max_date = session.query(func.max(PricesDaily.date)).scalar()
            print(f"    min: {min_date}")
            print(f"    max: {max_date}")
        except Exception:
            print(f"    (no data)")

        try:
            min_date = session.query(func.min(MacroObservation.date)).scalar()
            max_date = session.query(func.max(MacroObservation.date)).scalar()
            print(f"\n  Date range (macro_observations):")
            print(f"    min: {min_date}")
            print(f"    max: {max_date}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest all series from config into deephold_db.")
    parser.add_argument("--phase", choices=["fred", "ecb", "yahoo-ne", "yahoo-eq", "all"], default="all", help="Which phase to run (default: all)")
    parser.add_argument("--years", type=int, default=30, help="History depth in years (default: 30)")
    parser.add_argument("--full-sp500", action="store_true", help="Also fetch full S&P 500 from Wikipedia")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    registry = _load_yaml(SERIES_REGISTRY)
    tickers_cfg = _load_yaml(TICKERS)

    phase = args.phase
    years = args.years

    print("=" * 60)
    print(f"deephold_db — Ingest All (phase={phase}, years={years})")
    print("=" * 60)

    total_rows = 0

    if phase in ("all", "fred"):
        print(f"\n{'=' * 60}")
        print(f"Phase 1: FRED ({years} years)")
        print(f"{'=' * 60}")
        n = ingest_fred(registry, years)
        total_rows += n
        print(f"  FRED: {n:,} rows ingested")

    if phase in ("all", "ecb"):
        print(f"\n{'=' * 60}")
        print(f"Phase 2: ECB ({years} years)")
        print(f"{'=' * 60}")
        n = ingest_ecb(registry, years)
        total_rows += n
        print(f"  ECB: {n:,} rows ingested")

    if phase in ("all", "yahoo-ne"):
        print(f"\n{'=' * 60}")
        print(f"Phase 3: Yahoo Non-Equity ({years} years)")
        print(f"{'=' * 60}")
        n = ingest_yahoo_non_equity(registry, years)
        total_rows += n
        print(f"  Yahoo Non-Equity: {n:,} rows ingested")

    if phase in ("all", "yahoo-eq"):
        print(f"\n{'=' * 60}")
        print(f"Phase 4+5: Yahoo Equities ({years} years)")
        print(f"{'=' * 60}")
        n = ingest_yahoo_equities(tickers_cfg, years, full_sp500=args.full_sp500)
        total_rows += n
        print(f"  Yahoo Equities: {n:,} rows ingested")

    print(f"\n{'=' * 60}")
    print(f"Total: {total_rows:,} rows ingested")
    print(f"{'=' * 60}")

    dq_summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())