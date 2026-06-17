"""Bulk-seed prices_daily from the AEGIS paper universe.

Reads ``config/paper_universe.yaml`` (30 S&P 500 + 5 benchmarks) and pulls
daily OHLCV for each via the Yahoo vendor's bulk method. Idempotent
(upsert via SQLAlchemy merge).

Usage:
    python scripts/seed_paper_data.py
    python scripts/seed_paper_data.py --start 2006-01-01 --end 2025-12-31
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from deephold_db.db import (  # noqa: E402
    Instrument,
    InstrumentIdentifier,
    PricesDaily,
    Vendor,
    session_scope,
)
from deephold_db.utils.config import get_settings  # noqa: E402
from deephold_db.utils.logging import configure_logging, get_logger  # noqa: E402
from deephold_db.vendors.yahoo import YahooVendor  # noqa: E402

log = get_logger(__name__)


def load_universe(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("equities", []), cfg.get("benchmarks", [])


def upsert_vendor(code: str, license: str, homepage: str) -> int:
    with session_scope() as s:
        existing = s.query(Vendor).filter(Vendor.code == code).one_or_none()
        if existing is None:
            v = Vendor(code=code, license=license, homepage=homepage)
            s.add(v)
            s.flush()
            return v.vendor_id
        # Update license/homepage if changed.
        if existing.license != license or existing.homepage != homepage:
            existing.license = license
            existing.homepage = homepage
        return existing.vendor_id


def upsert_instrument(
    asset_class: str,
    name: str,
    currency: str,
    symbol: str,
) -> int:
    with session_scope() as s:
        existing = (
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
        if existing is None:
            inst = Instrument(asset_class=asset_class, name=name, currency=currency)
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
            return inst.instrument_id
        return existing.instrument_id


def upsert_prices(instrument_id: int, vendor_id: int, df) -> int:
    if df.is_empty():
        return 0
    rows = 0
    with session_scope() as s:
        for r in df.iter_rows(named=True):
            s.merge(
                PricesDaily(
                    instrument_id=instrument_id,
                    date=r["date"],
                    open=r.get("open"),
                    high=r.get("high"),
                    low=r.get("low"),
                    close=r["close"],
                    adjusted_close=r.get("adjusted_close"),
                    volume=r.get("volume"),
                    vendor_id=vendor_id,
                )
            )
            rows += 1
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2006-01-01")
    parser.add_argument(
        "--end",
        default=date.today().isoformat(),
        help="Inclusive end date (default: today).",
    )
    parser.add_argument(
        "--universe",
        default=str(PROJECT_ROOT / "config" / "paper_universe.yaml"),
    )
    parser.add_argument(
        "--include-benchmarks/--no-benchmarks",
        dest="benchmarks",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    start = datetime.fromisoformat(args.start).date()
    end = datetime.fromisoformat(args.end).date()
    universe_path = Path(args.universe)
    equities, benchmarks = load_universe(universe_path)

    targets: list[tuple[str, str, str, str, str]] = []
    # (symbol, name, asset_class, currency, sector-or-bench)
    for e in equities:
        targets.append((e["symbol"], e["name"], "equity", "USD", e.get("sector", "?")))
    if args.benchmarks:
        for b in benchmarks:
            targets.append((b["symbol"], b["name"], "index", "USD", "benchmark"))

    print(
        f"Universe: {len(equities)} equities + "
        f"{len(benchmarks) if args.benchmarks else 0} benchmarks "
        f"= {len(targets)} symbols"
    )
    print(f"Period: {start} .. {end} ({(end - start).days} days)")
    print()

    vendor_id = upsert_vendor(
        code="yahoo",
        license="Yahoo ToS — privater Gebrauch, keine Weiterverteilung",
        homepage="https://finance.yahoo.com",
    )

    yahoo = YahooVendor()
    print("Bulk-fetching from Yahoo (single call for all symbols)...")
    t0 = time.time()
    all_symbols = [t[0] for t in targets]
    data = yahoo.fetch_many(all_symbols, start, end)
    fetch_secs = time.time() - t0
    print(f"  fetch_many returned in {fetch_secs:.1f}s")
    print()

    total_rows = 0
    failures: list[tuple[str, str]] = []  # (symbol, reason)

    for sym, name, asset_class, currency, sector in targets:
        df = data.get(sym)
        if df is None or df.is_empty():
            failures.append((sym, "empty response"))
            print(f"  [skip] {sym:<8} {name[:30]:<30} — empty")
            continue

        instrument_id = upsert_instrument(asset_class, name, currency, sym)
        n = upsert_prices(instrument_id, vendor_id, df)
        total_rows += n
        last_date = df["date"].max()
        last_close = df["close"][-1]
        print(
            f"  [ok]   {sym:<8} {name[:30]:<30} {sector[:11]:<11} "
            f"rows={n:>5}  last={last_date}  close={last_close:>10.2f}"
        )

    print()
    print(f"Inserted/updated {total_rows:,} price rows in {time.time() - t0:.1f}s total")
    if failures:
        print(f"Failures: {len(failures)}")
        for sym, reason in failures:
            print(f"  {sym}: {reason}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
