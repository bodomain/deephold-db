"""Walk-forward VAM-top-N backtest.

Per Chakraborty & Singh (2026), simplified:

  1. Universe: N equities, daily adjusted close.
  2. Each month t:
       - For each stock, compute VAM over the trailing L=12 months,
         skipping the last month (skip=21 trading days).
       - Select top-N by VAM (with the momentum gate: VAM must be positive).
  3. Equal-weight the top-N, hold for 1 month, realise the return.
  4. Apply 10 bps transaction-cost friction per turnover.
  5. Compare the realised series against a set of benchmarks (same DB).

This is a "VAM-Lite" backtest — no GICS sector constraints, no anchor triad,
no SLSQP, no minimax correlation filter. It captures the data pipeline
end-to-end and gives a reasonable first-order validation of the
methodology on our infrastructure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import polars as pl

from deephold_db.analytics.metrics import (
    TRADING_DAYS,
    cagr,
    max_drawdown,
    sharpe,
    sortino,
)
from deephold_db.analytics.returns import log_returns
from deephold_db.analytics.vam import rank_top_n, vam

TRADING_DAYS_PER_MONTH = 21
FRICTION_BPS = 0.0010  # 10 bps, paper default


@dataclass
class BacktestResult:
    name: str
    daily_log_returns: pl.Series
    monthly_returns: pl.Series
    rebalance_dates: list


def _slice_window(close: pl.Series, end_idx: int, window: int, skip: int) -> pl.Series:
    """Return a window of `close` that ends `skip` bars before `end_idx`.

    Returns `window + skip` bars total: the last `skip` are excluded
    from the VAM calculation but kept so the function can index
    `valid[-skip]` and `valid[-(window+skip)]`.
    """
    if end_idx < window + skip:
        return close.slice(0, 0)
    start = end_idx - (window + skip)
    return close.slice(start, window + skip)


def run_vam_topn_backtest(
    prices: dict[str, pl.Series],
    rebalance_every: int = TRADING_DAYS_PER_MONTH,
    top_n: int = 10,
    vam_window: int = 252,
    vam_skip: int = 21,
    friction: float = FRICTION_BPS,
) -> BacktestResult:
    """Run the VAM top-N equal-weight backtest.

    Args:
        prices: {symbol: polars Series of close prices, ascending date}.
        rebalance_every: trading days between rebalances (21 = monthly).
        top_n: number of assets to hold.
        vam_window: trailing window for VAM (252 = 12 months).
        vam_skip: bars excluded from window end (21 = skip last month).
        friction: per-rebalance cost as fraction of turnover.
    """
    if not prices:
        raise ValueError("prices dict is empty")

    # Align all series to the same date index.
    min_len = min(len(s) for s in prices.values())
    aligned = {sym: s.slice(0, min_len) for sym, s in prices.items()}

    # Daily log returns for each symbol.
    log_rets = {sym: log_returns(s) for sym, s in aligned.items()}

    # Iterate rebalance dates.
    daily_rets: list[float] = []
    monthly_rets: list[float] = []
    rebalance_dates: list[int] = []
    held_symbols: list[str] = []

    n = min_len
    # We start when we have enough history for the VAM window.
    start_idx = vam_window + vam_skip + 1
    if start_idx >= n:
        raise ValueError(
            f"Universe too short: {n} bars < vam_window ({vam_window}) + vam_skip ({vam_skip}) + 1"
        )

    for end_idx in range(start_idx, n, rebalance_every):
        # 1. Score each symbol with VAM.
        scores: dict[str, float] = {}
        for sym, close in aligned.items():
            window_close = _slice_window(close, end_idx, vam_window, vam_skip)
            if window_close.is_empty():
                continue
            s = vam(window_close, window=vam_window, skip=vam_skip)
            scores[sym] = s
        # 2. Top-N by VAM, positive gate.
        top = [sym for sym in rank_top_n(scores, top_n * 2) if scores[sym] > 0][:top_n]
        if not top:
            continue

        # 3. Equal-weight, hold until next rebalance.
        next_idx = min(end_idx + rebalance_every, n)
        rets_in_period: list[float] = []
        for i in range(end_idx, next_idx):
            r = 0.0
            for sym in top:
                lr = log_rets[sym]
                if (
                    i < len(lr)
                    and lr[i] is not None
                    and not (isinstance(lr[i], float) and math.isnan(lr[i]))
                ):
                    r += float(lr[i]) / len(top)
            rets_in_period.append(r)
        period_ret = sum(rets_in_period)
        # 4. Friction: turnover vs previous month.
        if held_symbols:
            turnover = len(set(top).symmetric_difference(held_symbols)) / (2 * len(top))
        else:
            turnover = 1.0
        net_ret = period_ret - friction * turnover
        monthly_rets.append(net_ret)
        held_symbols = top
        rebalance_dates.append(end_idx)
        # Distribute the period's daily returns to the daily series.
        for r in rets_in_period[:-1]:
            daily_rets.append(r)
        daily_rets.append(rets_in_period[-1] - friction * turnover)

    return BacktestResult(
        name=f"VAM-Top{top_n}",
        daily_log_returns=pl.Series("vam_daily", daily_rets),
        monthly_returns=pl.Series("vam_monthly", monthly_rets),
        rebalance_dates=rebalance_dates,
    )


def benchmark_from_prices(
    name: str,
    close: pl.Series,
) -> BacktestResult:
    """Convert a benchmark price series into a BacktestResult.

    No rebalancing, no friction — buy-and-hold.
    """
    rets = log_returns(close).drop_nulls()
    return BacktestResult(
        name=name,
        daily_log_returns=rets,
        monthly_returns=rets,
        rebalance_dates=[],
    )


def result_metrics(result: BacktestResult, label: str | None = None) -> dict:
    """Compute the standard metrics for a BacktestResult."""
    name = label or result.name
    if result.daily_log_returns.is_empty():
        return {"name": name}
    close = result.daily_log_returns.cum_sum().exp()  # cumulative growth from 1
    return {
        "name": name,
        "CAGR": f"{cagr(close):.2%}" if not math.isnan(cagr(close)) else "n/a",
        "Vol": f"{float(result.daily_log_returns.std()) * math.sqrt(TRADING_DAYS):.2%}",
        "Sharpe": f"{sharpe(result.daily_log_returns):.2f}",
        "Sortino": f"{sortino(result.daily_log_returns):.2f}",
        "MaxDD": f"{max_drawdown(close):.2%}",
        "Months": len(result.monthly_returns),
    }
