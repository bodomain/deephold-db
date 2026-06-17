"""AEGIS paper replication: VAM-Lite backtest vs benchmarks.

Loads the paper universe from the DB, runs a VAM top-N backtest, and
compares realised metrics against the 5 benchmarks.

Usage:
    python scripts/paper_replicate.py
    python scripts/paper_replicate.py --top-n 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from deephold_db.analytics.backtest import (  # noqa: E402
    benchmark_from_prices,
    result_metrics,
    run_vam_topn_backtest,
)
from deephold_db.db import (  # noqa: E402
    Instrument,
    InstrumentIdentifier,
    PricesDaily,
    session_scope,
)


def load_universe(path: Path) -> tuple[list[str], list[str]]:
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    equities = [e["symbol"] for e in cfg.get("equities", [])]
    benchmarks = [b["symbol"] for b in cfg.get("benchmarks", [])]
    return equities, benchmarks


def load_prices(symbols: list[str]) -> dict[str, pl.Series]:
    """Load aligned close prices for the given YAHOO symbols."""
    with session_scope() as s:
        # 1) Resolve symbol -> instrument_id
        inst_ids: dict[str, int] = {}
        rows = (
            s.query(InstrumentIdentifier.value, Instrument.instrument_id)
            .join(Instrument, Instrument.instrument_id == InstrumentIdentifier.instrument_id)
            .filter(
                InstrumentIdentifier.scheme == "YAHOO",
                InstrumentIdentifier.value.in_(symbols),
            )
            .all()
        )
        for value, iid in rows:
            inst_ids[value] = iid
        # 2) Fetch prices for each
        out: dict[str, pl.Series] = {}
        for sym, iid in inst_ids.items():
            price_rows = (
                s.query(PricesDaily.date, PricesDaily.close)
                .filter(PricesDaily.instrument_id == iid)
                .order_by(PricesDaily.date)
                .all()
            )
            if not price_rows:
                print(f"  [warn] no prices for {sym}")
                continue
            close = pl.Series(
                sym,
                [float(r.close) for r in price_rows if r.close is not None],
            )
            out[sym] = close
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", default=str(PROJECT_ROOT / "config" / "paper_universe.yaml"))
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--window", type=int, default=252)
    parser.add_argument("--skip", type=int, default=21)
    parser.add_argument("--friction", type=float, default=0.0010)
    parser.add_argument(
        "--equities-only/--all",
        dest="equities_only",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Run VAM only on equities (benchmarks are always buy-and-hold).",
    )
    args = parser.parse_args()

    equity_syms, bench_syms = load_universe(Path(args.universe))
    target_equities = equity_syms if args.equities_only else (equity_syms + bench_syms)

    print(f"Loading {len(target_equities)} symbols from DB...")
    all_prices = load_prices(target_equities)
    print(f"  loaded {len(all_prices)} price series")
    print()

    # Run VAM-TopN on the equity universe.
    if args.equities_only:
        equity_prices = all_prices
    else:
        equity_prices = {sym: all_prices[sym] for sym in equity_syms if sym in all_prices}

    print(
        f"Running VAM-Top{args.top_n} backtest on {len(equity_prices)} equities "
        f"(L={args.window}, skip={args.skip}, friction={args.friction * 100:.2f}%)..."
    )
    vam_result = run_vam_topn_backtest(
        equity_prices,
        top_n=args.top_n,
        vam_window=args.window,
        vam_skip=args.skip,
        friction=args.friction,
    )
    print(f"  VAM-Top{args.top_n}: {len(vam_result.monthly_returns)} monthly returns")
    print()

    # Benchmarks: buy-and-hold each.
    bench_results = []
    for sym in bench_syms:
        if sym not in all_prices:
            print(f"  [skip] benchmark {sym}: not in DB")
            continue
        br = benchmark_from_prices(sym, all_prices[sym])
        bench_results.append(br)
    print(f"  {len(bench_results)} benchmarks loaded")
    print()

    # Comparison table.
    rows = [result_metrics(vam_result)]
    for br in bench_results:
        rows.append(result_metrics(br))
    print("=" * 80)
    print(
        f"{'Strategy':<22} {'CAGR':>8} {'Vol':>8} {'Sharpe':>8} {'Sortino':>8} {'MaxDD':>8} {'Months':>8}"
    )
    print("-" * 80)
    for r in rows:
        print(
            f"{r['name']:<22} {r.get('CAGR', 'n/a'):>8} {r.get('Vol', 'n/a'):>8} "
            f"{r.get('Sharpe', 'n/a'):>8} {r.get('Sortino', 'n/a'):>8} "
            f"{r.get('MaxDD', 'n/a'):>8} {r.get('Months', 0):>8}"
        )
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
