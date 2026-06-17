"""Performance metrics for a return series.

All inputs are polars Series of daily *log* returns, ascending date.
"""

from __future__ import annotations

import math

import numpy as np
import polars as pl

TRADING_DAYS = 252


def cagr(close: pl.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """Compound Annual Growth Rate from a price series.

    CAGR = (P_end / P_start)^(years) - 1
    """
    valid = close.drop_nulls()
    if valid.is_empty() or len(valid) < 2:
        return float("nan")
    p0 = float(valid[0])
    p1 = float(valid[-1])
    if p0 <= 0:
        return float("nan")
    n_days = (valid.len() - 1) / periods_per_year
    if n_days <= 0:
        return float("nan")
    return (p1 / p0) ** (1.0 / n_days) - 1.0


def annualized_vol(log_rets: pl.Series, periods_per_year: int = TRADING_DAYS) -> float:
    valid = log_rets.drop_nulls()
    if valid.is_empty() or len(valid) < 2:
        return float("nan")
    return float(valid.std()) * math.sqrt(periods_per_year)


def sharpe(log_rets: pl.Series, rf: float = 0.04, periods_per_year: int = TRADING_DAYS) -> float:
    """Sharpe = (annualized_return - rf) / annualized_vol."""
    valid = log_rets.drop_nulls()
    if valid.is_empty() or len(valid) < 2:
        return float("nan")
    ann_ret = float(valid.mean()) * periods_per_year
    vol = annualized_vol(valid, periods_per_year)
    if vol == 0 or math.isnan(vol):
        return float("nan")
    return (ann_ret - rf) / vol


def sortino(log_rets: pl.Series, rf: float = 0.04, periods_per_year: int = TRADING_DAYS) -> float:
    """Sortino = (annualized_return - rf) / annualized_downside_deviation.

    Downside deviation: sqrt(mean(min(0, r - rf/252)^2)).
    """
    valid = log_rets.drop_nulls()
    if valid.is_empty() or len(valid) < 2:
        return float("nan")
    daily_rf = rf / periods_per_year
    diffs = valid - daily_rf
    downside = diffs.clip(upper_bound=0.0)
    dd = math.sqrt(float((downside**2).mean())) * math.sqrt(periods_per_year)
    ann_ret = float(valid.mean()) * periods_per_year
    if dd == 0 or math.isnan(dd):
        return float("nan")
    return (ann_ret - rf) / dd


def max_drawdown(close: pl.Series) -> float:
    """Maximum drawdown: max((peak - trough) / peak) over the price series."""
    valid = close.drop_nulls()
    if valid.is_empty():
        return float("nan")
    arr = valid.to_numpy()
    peak = np.maximum.accumulate(arr)
    drawdown = (arr - peak) / peak
    return float(drawdown.min())


def calmar(close: pl.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """Calmar = CAGR / |MaxDD|."""
    c = cagr(close, periods_per_year)
    m = max_drawdown(close)
    if math.isnan(c) or math.isnan(m) or m == 0:
        return float("nan")
    return c / abs(m)
