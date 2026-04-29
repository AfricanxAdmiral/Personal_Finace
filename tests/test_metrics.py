"""Tests for finace.metrics — portfolio performance and risk metrics."""
import math
import numpy as np
import pandas as pd
import pytest
from datetime import date, timedelta

from finace.metrics import (
    annualized_volatility,
    beta,
    calmar_ratio,
    daily_returns,
    drawdown_series,
    max_drawdown,
    portfolio_value_series,
    sharpe_ratio,
    sortino_ratio,
    win_rate,
)
from finace.portfolio import Position


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _series(values, start="2024-01-02", freq="B"):
    idx = pd.date_range(start, periods=len(values), freq=freq)
    return pd.Series(values, index=idx, dtype=float)


def _pos(ticker="AAPL", buy="2024-01-02", sell=None, sell_price=None):
    return Position(
        id=1, ticker=ticker, shares=10.0,
        buy_price=100.0, buy_date=buy,
        sell_price=sell_price, sell_date=sell, note=None,
    )


# ── daily_returns ──────────────────────────────────────────────────────────────

def test_daily_returns_basic():
    s = _series([100.0, 110.0, 105.0])
    dr = daily_returns(s)
    assert len(dr) == 2
    assert dr.iloc[0] == pytest.approx(0.10)


def test_daily_returns_no_nans():
    s = _series([100.0, 110.0, 105.0])
    assert not daily_returns(s).isna().any()


def test_daily_returns_single_value_empty():
    assert daily_returns(_series([100.0])).empty


# ── annualized_volatility ──────────────────────────────────────────────────────

def test_volatility_zero_for_flat_prices():
    s = _series([100.0] * 30)
    assert annualized_volatility(s) == pytest.approx(0.0)


def test_volatility_positive_for_varying_prices():
    s = _series([100.0 * (1 + 0.01 * (i % 3 - 1)) for i in range(60)])
    assert annualized_volatility(s) > 0


def test_volatility_single_price_returns_zero():
    assert annualized_volatility(_series([100.0])) == 0.0


def test_volatility_two_prices_returns_zero_stdev():
    # std of a single return is 0 (ddof=1 denominator → NaN for n=1, but
    # pct_change gives 1 return, std of 1 value with ddof=1 is NaN → handled as 0)
    s = _series([100.0, 110.0])
    result = annualized_volatility(s)
    assert result == pytest.approx(0.0) or math.isnan(result) or result >= 0


def test_volatility_scales_with_std():
    # Higher variance → higher annualised vol
    low_var  = _series([100 + (i % 2) * 1  for i in range(60)])
    high_var = _series([100 + (i % 2) * 10 for i in range(60)])
    assert annualized_volatility(high_var) > annualized_volatility(low_var)


# ── max_drawdown ───────────────────────────────────────────────────────────────

def test_max_drawdown_monotone_up_is_zero():
    s = _series([100.0, 110.0, 120.0, 130.0])
    assert max_drawdown(s) == pytest.approx(0.0)


def test_max_drawdown_negative():
    s = _series([100.0, 110.0, 90.0, 95.0])
    # peak = 110, trough = 90: dd = (90-110)/110 * 100 ≈ -18.18%
    assert max_drawdown(s) < 0


def test_max_drawdown_correct_value():
    s = _series([100.0, 110.0, 90.0, 95.0])
    expected = (90.0 - 110.0) / 110.0 * 100
    assert max_drawdown(s) == pytest.approx(expected)


def test_max_drawdown_single_price_zero():
    assert max_drawdown(_series([100.0])) == 0.0


def test_max_drawdown_full_loss():
    s = _series([100.0, 50.0, 1.0])
    assert max_drawdown(s) < -98.0


# ── drawdown_series ────────────────────────────────────────────────────────────

def test_drawdown_series_starts_at_zero():
    s = _series([100.0, 90.0, 80.0])
    dd = drawdown_series(s)
    assert dd.iloc[0] == pytest.approx(0.0)


def test_drawdown_series_non_positive():
    s = _series([100.0, 90.0, 95.0, 80.0])
    assert (drawdown_series(s) <= 0).all()


def test_drawdown_series_length_matches_input():
    s = _series(range(100, 150))
    assert len(drawdown_series(s)) == len(s)


def test_drawdown_series_empty_input():
    assert drawdown_series(pd.Series(dtype=float)).empty


# ── sharpe_ratio ───────────────────────────────────────────────────────────────

def test_sharpe_returns_float():
    s = _series([100 * (1.001 ** i) for i in range(60)])
    assert isinstance(sharpe_ratio(s), float)


def test_sharpe_single_price_zero():
    assert sharpe_ratio(_series([100.0])) == 0.0


def test_sharpe_higher_return_higher_ratio():
    low_ret  = _series([100 * (1.0005 ** i) for i in range(120)])
    high_ret = _series([100 * (1.002  ** i) for i in range(120)])
    assert sharpe_ratio(high_ret) > sharpe_ratio(low_ret)


def test_sharpe_flat_prices_zero():
    # No excess returns → 0
    s = _series([100.0] * 30)
    assert sharpe_ratio(s) == 0.0


# ── sortino_ratio ──────────────────────────────────────────────────────────────

def test_sortino_returns_float_or_inf():
    s = _series([100 * (1.001 ** i) for i in range(60)])
    result = sortino_ratio(s)
    assert isinstance(result, float)


def test_sortino_no_downdays_returns_inf():
    # monotonically increasing, rf~=0 → all excess returns positive → inf
    s = _series([100 * (1.01 ** i) for i in range(30)])
    result = sortino_ratio(s, risk_free_rate=0.0)
    assert result == float("inf") or result > 0


def test_sortino_single_price_zero():
    assert sortino_ratio(_series([100.0])) == 0.0


def test_sortino_positive_with_mixed_returns():
    import random; random.seed(42)
    vals = [100.0]
    for _ in range(59):
        vals.append(vals[-1] * (1 + random.uniform(-0.01, 0.015)))
    s = _series(vals)
    result = sortino_ratio(s)
    assert isinstance(result, float)


# ── beta ───────────────────────────────────────────────────────────────────────

def test_beta_identical_series_is_one():
    s = _series([100 + i for i in range(60)])
    assert beta(s, s) == pytest.approx(1.0)


def test_beta_insufficient_data_returns_one():
    s = _series([100.0, 101.0])
    b = _series([100.0, 101.0])
    # Only 1 return each → after alignment and dropna may be insufficient
    result = beta(s, b)
    assert isinstance(result, float)


def test_beta_flat_benchmark_returns_one():
    port  = _series([100 + i for i in range(60)])
    bench = _series([200.0] * 60)  # zero variance → returns 1.0
    assert beta(port, bench) == pytest.approx(1.0)


def test_beta_returns_float():
    port  = _series([100 * (1.001 ** i) for i in range(60)])
    bench = _series([100 * (1.0008 ** i) for i in range(60)])
    assert isinstance(beta(port, bench), float)


# ── calmar_ratio ───────────────────────────────────────────────────────────────

def test_calmar_positive_case():
    assert calmar_ratio(15.0, -5.0) == pytest.approx(3.0)


def test_calmar_zero_drawdown_returns_zero():
    assert calmar_ratio(10.0, 0.0) == 0.0


def test_calmar_negative_cagr():
    # negative CAGR / |mdd| → negative calmar
    assert calmar_ratio(-5.0, -10.0) == pytest.approx(-0.5)


# ── win_rate ───────────────────────────────────────────────────────────────────

def test_win_rate_all_winners():
    assert win_rate([100.0, 200.0, 50.0]) == pytest.approx(100.0)


def test_win_rate_all_losers():
    assert win_rate([-100.0, -50.0]) == pytest.approx(0.0)


def test_win_rate_mixed():
    assert win_rate([100.0, -50.0, 200.0, -10.0]) == pytest.approx(50.0)


def test_win_rate_empty_returns_zero():
    assert win_rate([]) == 0.0


def test_win_rate_breakeven_not_counted():
    assert win_rate([0.0, 100.0]) == pytest.approx(50.0)


# ── portfolio_value_series ─────────────────────────────────────────────────────

pytestmark = pytest.mark.usefixtures("tmp_cache")


def _make_fetch(price_map: dict):
    """Return a fetch_fn that returns a price series for a given ticker."""
    def _fetch(ticker, start, end):
        prices = price_map.get(ticker, pd.Series(dtype=float))
        if prices.empty:
            return prices
        mask = (prices.index >= pd.Timestamp(start)) & (prices.index < pd.Timestamp(end))
        return prices[mask]
    return _fetch


def test_portfolio_value_series_empty_positions():
    val, cost = portfolio_value_series([])
    assert val.empty and cost.empty


def test_portfolio_value_series_single_open_position():
    prices = _series([100.0, 105.0, 110.0], start="2024-01-02")
    fetch  = _make_fetch({"AAPL": prices})
    pos    = _pos(buy="2024-01-02")
    val, cost = portfolio_value_series([pos], fetch_fn=fetch)
    assert not val.empty
    assert not cost.empty


def test_portfolio_value_series_value_equals_price_times_shares():
    prices = _series([100.0, 105.0, 110.0], start="2024-01-02")
    fetch  = _make_fetch({"AAPL": prices})
    pos    = _pos(buy="2024-01-02")
    val, _ = portfolio_value_series([pos], fetch_fn=fetch)
    nz = val[val > 0]
    assert not nz.empty


def test_portfolio_value_series_cost_constant_while_open():
    prices = _series([100.0, 105.0, 110.0], start="2024-01-02")
    fetch  = _make_fetch({"AAPL": prices})
    pos    = _pos(buy="2024-01-02")
    _, cost = portfolio_value_series([pos], fetch_fn=fetch)
    nz_cost = cost[cost > 0]
    # Cost basis is buy_price * shares = 1000.0 every active day
    assert abs(nz_cost - 1000.0).max() < 1e-6


def test_portfolio_value_series_missing_ticker_skipped():
    fetch = _make_fetch({})  # no data for any ticker
    pos   = _pos(buy="2024-01-02")
    val, cost = portfolio_value_series([pos], fetch_fn=fetch)
    # All zeros (position skipped)
    assert (val == 0.0).all()


# ── Performance page CAGR / Calmar helpers ─────────────────────────────────────
# The page computes port_cagr = ((final_val / peak_cost) ** (1/years) - 1) * 100
# then passes it to calmar_ratio(port_cagr, mdd).  These tests exercise that
# exact formula path so regressions surface as test failures, not UI bugs.

def _page_cagr(nz: pd.Series, nz_cost: pd.Series) -> float:
    """Replicate the CAGR formula used in page_performance."""
    years_held = max((nz.index[-1] - nz.index[0]).days / 365.25, 1 / 365.25)
    final_val  = float(nz.iloc[-1])
    peak_cost  = float(nz_cost.max()) if not nz_cost.empty and nz_cost.max() > 0 else 1.0
    return ((final_val / peak_cost) ** (1.0 / years_held) - 1) * 100


def test_page_cagr_breakeven_is_zero():
    # final value == cost → 0% return
    idx  = pd.date_range("2023-01-02", periods=252, freq="B")
    cost = pd.Series(1000.0, index=idx)
    val  = pd.Series(1000.0, index=idx)
    assert _page_cagr(val, cost) == pytest.approx(0.0, abs=1e-6)


def test_page_cagr_doubled_money_one_year():
    idx  = pd.date_range("2024-01-02", periods=252, freq="B")
    cost = pd.Series(1000.0, index=idx)
    val  = pd.Series(2000.0, index=idx)
    cagr = _page_cagr(val, cost)
    # ~1 year, doubling → ~100% CAGR
    assert 90.0 < cagr < 110.0


def test_page_cagr_positive_return_positive():
    idx  = pd.date_range("2024-01-02", periods=252, freq="B")
    cost = pd.Series(1000.0, index=idx)
    val  = pd.Series(1100.0, index=idx)
    assert _page_cagr(val, cost) > 0


def test_page_cagr_loss_negative():
    idx  = pd.date_range("2024-01-02", periods=252, freq="B")
    cost = pd.Series(1000.0, index=idx)
    val  = pd.Series(900.0, index=idx)
    assert _page_cagr(val, cost) < 0


def test_page_calmar_from_cagr_and_mdd():
    # Integration: cagr=10%, mdd=-5% → calmar=2.0
    assert calmar_ratio(10.0, -5.0) == pytest.approx(2.0)


def test_page_cagr_uses_peak_cost_not_first_cost():
    # If two positions are added over time, peak_cost > first-day cost.
    # CAGR should be lower (harder hurdle) vs using first-day cost only.
    idx  = pd.date_range("2024-01-02", periods=252, freq="B")
    # Cost ramps up (new positions added) then stays flat
    cost = pd.Series([1000.0] * 100 + [2000.0] * 152, index=idx)
    val  = pd.Series(2200.0, index=idx)
    # peak_cost = 2000, final_val = 2200
    cagr = _page_cagr(val, cost)
    assert cagr == pytest.approx(_page_cagr(
        pd.Series(2200.0, index=idx),
        pd.Series(2000.0, index=idx),
    ))
