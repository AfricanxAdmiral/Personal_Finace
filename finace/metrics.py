"""Portfolio performance and risk metrics.

All pure-computation functions accept a pd.Series of prices (daily close)
and return a scalar.  ``portfolio_value_series`` is the one function that
touches external data; it accepts an injectable ``fetch_fn`` so tests can
supply synthetic prices without a network call.

Metric reference
----------------
Volatility   : annualised std-dev of daily returns (%)
Max Drawdown : worst peak-to-trough loss from any high (negative %)
Sharpe       : (mean excess daily return / std-dev) × √252
Sortino      : like Sharpe but σ is computed only over negative excess returns
Beta         : Cov(portfolio, benchmark) / Var(benchmark)
Calmar       : CAGR / |Max Drawdown|
Win Rate     : % of closed positions where gain > 0
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, List, Optional, Tuple

import numpy as np
import pandas as pd

from finace.portfolio import Position

RISK_FREE_RATE = 4.0   # annual %, used as default in Sharpe / Sortino
BENCHMARK      = "SPY"  # used for Beta


# ── Shared data helper ─────────────────────────────────────────────────────────

def portfolio_value_series(
    positions: List[Position],
    fetch_fn: Optional[Callable] = None,
) -> Tuple[pd.Series, pd.Series]:
    """Return daily (total_value, total_cost) series across all positions.

    Both series share the same DatetimeIndex (every calendar day from the
    earliest buy date to today).  Days when no position is active are zero.
    """
    if fetch_fn is None:
        from finace.stock import fetch_history
        fetch_fn = fetch_history

    if not positions:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    today     = date.today()
    all_start = min(date.fromisoformat(p.buy_date) for p in positions)
    date_idx  = pd.date_range(start=all_start, end=today, freq="D")

    total_value = pd.Series(0.0, index=date_idx)
    total_cost  = pd.Series(0.0, index=date_idx)

    for pos in positions:
        buy_dt   = pd.Timestamp(pos.buy_date)
        end_dt   = pd.Timestamp(pos.sell_date) if pos.sell_date else pd.Timestamp(today)
        end_date = date.fromisoformat(pos.sell_date) if pos.sell_date else today

        prices = fetch_fn(
            pos.ticker,
            pos.buy_date,
            (end_date + timedelta(days=1)).isoformat(),
        )
        if prices.empty:
            continue

        prices_daily = prices.reindex(date_idx).ffill()
        mask         = (date_idx >= buy_dt) & (date_idx <= end_dt)

        total_value += (prices_daily * pos.shares).where(mask, 0.0)
        total_cost  += pd.Series(
            pos.shares * pos.buy_price, index=date_idx
        ).where(mask, 0.0)

    return total_value, total_cost


# ── Building blocks ────────────────────────────────────────────────────────────

def daily_returns(prices: pd.Series) -> pd.Series:
    """Percentage change between consecutive prices, NaNs dropped."""
    return prices.pct_change().dropna()


# ── Risk metrics ───────────────────────────────────────────────────────────────

def annualized_volatility(prices: pd.Series) -> float:
    """Annualised standard deviation of daily returns (%)."""
    dr = daily_returns(prices)
    if len(dr) < 2:
        return 0.0
    return float(dr.std() * np.sqrt(252) * 100)


def max_drawdown(prices: pd.Series) -> float:
    """Maximum peak-to-trough decline (negative %). 0.0 if never negative."""
    if len(prices) < 2:
        return 0.0
    rolling_max = prices.cummax()
    dd          = (prices - rolling_max) / rolling_max
    return float(dd.min() * 100)


def drawdown_series(prices: pd.Series) -> pd.Series:
    """Drawdown at every point in time (negative %)."""
    if prices.empty:
        return pd.Series(dtype=float)
    rolling_max = prices.cummax()
    return (prices - rolling_max) / rolling_max * 100


def sharpe_ratio(
    prices: pd.Series,
    risk_free_rate: float = RISK_FREE_RATE,
) -> float:
    """Annualised Sharpe ratio.  Returns 0.0 when there is insufficient data."""
    dr = daily_returns(prices)
    if len(dr) < 2:
        return 0.0
    rf_daily = (1 + risk_free_rate / 100) ** (1 / 252) - 1
    excess   = dr - rf_daily
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(252))


def sortino_ratio(
    prices: pd.Series,
    risk_free_rate: float = RISK_FREE_RATE,
) -> float:
    """Annualised Sortino ratio (σ computed only over negative excess returns).

    Returns ``float('inf')`` when there are no down-days (all returns exceed
    the risk-free rate); callers should handle that case in display.
    """
    dr = daily_returns(prices)
    if len(dr) < 2:
        return 0.0
    rf_daily = (1 + risk_free_rate / 100) ** (1 / 252) - 1
    excess   = dr - rf_daily
    downside = excess[excess < 0]
    if downside.empty or downside.std() == 0:
        return float("inf") if excess.mean() > 0 else 0.0
    return float(excess.mean() / downside.std() * np.sqrt(252))


def beta(
    portfolio_prices: pd.Series,
    benchmark_prices: pd.Series,
) -> float:
    """Market beta of the portfolio relative to a benchmark price series.

    Returns 1.0 when there is not enough aligned data to compute a meaningful
    result rather than raising an error.
    """
    port_r  = daily_returns(portfolio_prices)
    bench_r = daily_returns(benchmark_prices)
    aligned = pd.concat([port_r, bench_r], axis=1).dropna()
    if len(aligned) < 2:
        return 1.0
    pr, br = aligned.iloc[:, 0], aligned.iloc[:, 1]
    var    = br.var()
    return float(pr.cov(br) / var) if var != 0 else 1.0


def calmar_ratio(cagr_pct: float, mdd_pct: float) -> float:
    """CAGR / |Max Drawdown|.  Higher = better risk-adjusted growth."""
    return cagr_pct / abs(mdd_pct) if mdd_pct != 0 else 0.0


def win_rate(closed_gains: List[float]) -> float:
    """Percentage of closed positions where realised gain > 0."""
    if not closed_gains:
        return 0.0
    return sum(1 for g in closed_gains if g > 0) / len(closed_gains) * 100
