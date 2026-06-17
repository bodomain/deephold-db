"""Return calculations on polars Series of prices.

All functions take a polars Series of close prices (ascending date) and
return a polars Series of returns aligned with the same index.
"""

from __future__ import annotations

import numpy as np
import polars as pl


def log_returns(prices: pl.Series) -> pl.Series:
    """Daily log returns: r_t = ln(P_t / P_{t-1}). First value is null."""
    p = prices.cast(pl.Float64)
    prev = p.shift(1)
    out = (p / prev).log()
    return out.rename(prices.name or "log_return")


def simple_returns(prices: pl.Series) -> pl.Series:
    """Daily simple returns: r_t = P_t / P_{t-1} - 1."""
    p = prices.cast(pl.Float64)
    prev = p.shift(1)
    out = p / prev - 1.0
    return out.rename(prices.name or "simple_return")


def compound_returns(log_rets: pl.Series) -> pl.Series:
    """Cumulative compounded returns from log returns: exp(sum) - 1."""
    valid = log_rets.drop_nulls()
    if valid.is_empty():
        return pl.Series("cum", [], dtype=pl.Float64)
    cs = valid.cum_sum()
    return cs.exp() - 1.0


def annualized_log_return(daily_log_rets: pl.Series, trading_days: int = 252) -> float:
    """Annualized log return: mean(daily) * 252."""
    valid = daily_log_rets.drop_nulls()
    if valid.is_empty():
        return float("nan")
    return float(valid.mean()) * trading_days


def annualized_vol(daily_log_rets: pl.Series, trading_days: int = 252) -> float:
    """Annualized vol: std(daily) * sqrt(252)."""
    valid = daily_log_rets.drop_nulls()
    if valid.is_empty() or len(valid) < 2:
        return float("nan")
    return float(valid.std()) * np.sqrt(trading_days)
