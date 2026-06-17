"""VAM (Volatility-Adjusted Momentum) signal.

Per Chakraborty & Singh (2026):
    S_i,t = R_i,t-L:t-1 / sigma_i
    R_i,t-L:t-1 = sum(log(P_t-21 / P_t-L)) for k in [t-L, t-21]
    sigma_i = annualized daily log-return std over the same window

The skip-month (t-1 excluded) reduces microstructure reversal noise.
"""

from __future__ import annotations

import math

import polars as pl


def cumulative_log_return(close: pl.Series, window: int, skip: int = 1) -> float:
    """Cumulative log return over [t - window, t - skip), paper-style.

    `close` must be ascending in time; the last `skip` bars are excluded
    from the window.
    """
    valid = close.drop_nulls()
    if valid.is_empty() or len(valid) < window + skip:
        return float("nan")
    p_start = float(valid[-(window + skip)])
    p_end = float(valid[-skip])
    if p_start <= 0 or p_end <= 0:
        return float("nan")
    return math.log(p_end / p_start)


def realized_vol(close: pl.Series, window: int, skip: int = 1) -> float:
    """Annualized std of daily log returns over [t - window, t - skip).

    `close` is the wider slice of `window + skip` bars; the last `skip`
    bars are excluded from the std calculation (paper skip-month).
    """
    valid = close.drop_nulls()
    if valid.is_empty() or len(valid) < window + skip:
        return float("nan")
    sub = valid.slice(len(valid) - (window + skip), window)
    rets = (sub / sub.shift(1)).log().drop_nulls()
    if rets.is_empty() or len(rets) < 2:
        return float("nan")
    return float(rets.std()) * math.sqrt(252)


def vam(close: pl.Series, window: int = 252, skip: int = 21) -> float:
    """Volatility-Adjusted Momentum: R / sigma, paper-style.

    Default window = 252 trading days (12 months), skip = 21 days (1 month).
    """
    r = cumulative_log_return(close, window, skip)
    s = realized_vol(close, window, skip)
    if math.isnan(r) or math.isnan(s) or s == 0:
        return float("nan")
    return r / s


def rank_top_n(returns: dict[str, float], n: int) -> list[str]:
    """Return top-n keys by highest score, ignoring NaN."""
    filtered = [(k, v) for k, v in returns.items() if v == v]  # NaN check
    filtered.sort(key=lambda kv: kv[1], reverse=True)
    return [k for k, _ in filtered[:n]]
