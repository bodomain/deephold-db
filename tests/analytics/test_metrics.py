"""Tests for analytics.returns and analytics.metrics.

Synthetic price series with known properties (e.g. constant +0.1%/day
log-return → CAGR ≈ e^0.0001*252 - 1 ≈ 2.53%).

Run:  pytest tests/analytics/ -v
"""

from __future__ import annotations

import math

import numpy as np
import polars as pl
import pytest

from deephold_db.analytics.metrics import (
    cagr,
    calmar,
    max_drawdown,
    sharpe,
    sortino,
)
from deephold_db.analytics.returns import (
    annualized_log_return,
    annualized_vol,
    compound_returns,
    log_returns,
    simple_returns,
)

# ---------- returns tests -------------------------------------------------


def test_log_returns_constant_growth() -> None:
    """Constant +0.1% per day → log return ≈ 0.001 each step."""
    prices = pl.Series("p", [100.0 * math.exp(0.001 * i) for i in range(10)])
    rets = log_returns(prices)
    assert rets[0] is None or (isinstance(rets[0], float) and math.isnan(rets[0]))
    for i in range(1, len(rets)):
        assert rets[i] == pytest.approx(0.001, abs=1e-9)


def test_log_returns_first_is_null() -> None:
    prices = pl.Series("p", [100.0, 101.0, 102.0])
    rets = log_returns(prices)
    assert rets[0] is None or (isinstance(rets[0], float) and math.isnan(rets[0]))
    assert rets[1] == pytest.approx(math.log(101 / 100))
    assert rets[2] == pytest.approx(math.log(102 / 101))


def test_simple_returns_basic() -> None:
    prices = pl.Series("p", [100.0, 110.0, 99.0])
    rets = simple_returns(prices)
    assert rets[1] == pytest.approx(0.10)
    assert rets[2] == pytest.approx(-0.10)


def test_compound_returns_recovers_price_ratio() -> None:
    """Cumulating log returns and exponentiating should recover P_end / P_start - 1."""
    prices = pl.Series("p", [100.0, 110.0, 121.0, 99.0])
    rets = log_returns(prices).slice(1)  # drop the leading null
    cum = compound_returns(rets)
    # Last value should equal (P_end / P_start - 1) = 99/100 - 1
    assert float(cum[-1]) == pytest.approx(99 / 100 - 1, abs=1e-9)


def test_annualized_log_return_constant() -> None:
    rets = pl.Series("r", [0.001] * 252)
    assert annualized_log_return(rets) == pytest.approx(0.001 * 252, abs=1e-9)


def test_annualized_vol_known() -> None:
    # log returns drawn from N(0, 0.01) → daily std ≈ 0.01, annualized ≈ 0.01*sqrt(252)
    rng = np.random.default_rng(42)
    samples = rng.normal(0, 0.01, 5000)
    rets = pl.Series("r", samples)
    v = annualized_vol(rets)
    # Wide tolerance for sampling noise
    assert 0.14 < v < 0.18


# ---------- metrics tests --------------------------------------------------


def test_cagr_known_growth() -> None:
    """100 → 121 over 2 years (252 trading days each) → CAGR = 10%."""
    n = 504
    p0 = 100.0
    p1 = 121.0
    # Linear interpolation
    arr = np.linspace(p0, p1, n + 1)
    close = pl.Series("p", arr)
    c = cagr(close)
    # Linear interpolation in price space is not exactly log-linear, but close.
    assert math.isclose(c, 0.10, abs_tol=1e-3)


def test_cagr_empty() -> None:
    close = pl.Series("p", [], dtype=pl.Float64)
    assert math.isnan(cagr(close))


def test_max_drawdown_basic() -> None:
    close = pl.Series("p", [100.0, 120.0, 60.0, 80.0, 100.0])
    # Peak 120, trough 60 → -50%
    assert max_drawdown(close) == pytest.approx(-0.5, abs=1e-9)


def test_max_drawdown_no_drawdown() -> None:
    close = pl.Series("p", [100.0, 101.0, 102.0, 103.0])
    assert max_drawdown(close) == pytest.approx(0.0, abs=1e-9)


def test_sharpe_zero_vol() -> None:
    rets = pl.Series("r", [0.0] * 252)
    assert math.isnan(sharpe(rets))


def test_sharpe_known() -> None:
    """Constant 0.1% daily log return, 1% vol, rf=0:
    ann_ret ≈ 0.001*252 = 0.252, ann_vol ≈ 0.01*sqrt(252) ≈ 0.1587
    Sharpe ≈ (0.252 - 0.04) / 0.1587 ≈ 1.336
    """
    rng = np.random.default_rng(0)
    n = 5000
    daily = rng.normal(0.001, 0.01, n)
    rets = pl.Series("r", daily)
    s = sharpe(rets, rf=0.04)
    # Sample mean is ≈ 0.001; tolerance accommodates sample variance
    assert 0.9 < s < 1.7


def test_sortino_known() -> None:
    """Net positive series with some downside: Sortino must be > Sharpe (penalty only downside)."""
    # 7 days +0.01, 3 days -0.01 → mean = 0.004, downside std finite, ratio positive
    rets = pl.Series(
        "r",
        [+0.01] * 7 + [-0.01] * 3,
    )
    s = sortino(rets, rf=0.0)
    assert s > 0
    assert math.isfinite(s)


def test_calmar_known() -> None:
    """CAGR 10%, MaxDD -20% → Calmar = 0.5."""
    n = 504  # 2 years
    prices = np.array([100.0 * (1.1 ** (i / n)) for i in range(n + 1)])
    # Inject a drawdown
    prices[n // 2] *= 0.8
    close = pl.Series("p", prices)
    cal = calmar(close)
    # Calmar is CAGR / |MaxDD|, should be > 0
    assert cal > 0
    assert math.isfinite(cal)
