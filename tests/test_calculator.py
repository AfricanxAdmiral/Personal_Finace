"""Tests for finace.calculator.compute_metrics."""
import pytest
from datetime import date

from finace.calculator import compute_metrics

BUY  = date(2023, 1, 1)
SELL = date(2024, 1, 1)  # 365 days later


# ── Return / gain-loss ─────────────────────────────────────────────────────────

def test_gain_loss_positive():
    m = compute_metrics(10, 100.0, BUY, 150.0, SELL)
    assert m["gain_loss"] == pytest.approx(500.0)

def test_gain_loss_negative():
    m = compute_metrics(10, 100.0, BUY, 80.0, SELL)
    assert m["gain_loss"] == pytest.approx(-200.0)

def test_gain_loss_zero_at_breakeven():
    m = compute_metrics(10, 100.0, BUY, 100.0, SELL)
    assert m["gain_loss"] == pytest.approx(0.0)

def test_total_cost():
    m = compute_metrics(7, 50.0, BUY, 60.0, SELL)
    assert m["total_cost"] == pytest.approx(350.0)

def test_current_value():
    m = compute_metrics(7, 50.0, BUY, 60.0, SELL)
    assert m["current_value"] == pytest.approx(420.0)

def test_pct_return_positive():
    m = compute_metrics(1, 100.0, BUY, 125.0, SELL)
    assert m["pct_return"] == pytest.approx(25.0)

def test_pct_return_negative():
    m = compute_metrics(1, 100.0, BUY, 75.0, SELL)
    assert m["pct_return"] == pytest.approx(-25.0)

def test_pct_return_breakeven():
    m = compute_metrics(1, 100.0, BUY, 100.0, SELL)
    assert m["pct_return"] == pytest.approx(0.0)


# ── CAGR ───────────────────────────────────────────────────────────────────────

def test_cagr_positive_gain():
    m = compute_metrics(1, 100.0, BUY, 150.0, SELL)
    assert m["cagr"] > 0

def test_cagr_negative_gain():
    m = compute_metrics(1, 100.0, BUY, 50.0, SELL)
    assert m["cagr"] < 0

def test_cagr_double_in_one_year():
    # Doubling in ~1 year → CAGR ≈ 100 %
    m = compute_metrics(1, 100.0, BUY, 200.0, SELL)
    assert m["cagr"] == pytest.approx(100.0, abs=1.0)

def test_cagr_breakeven_is_zero():
    m = compute_metrics(1, 100.0, BUY, 100.0, SELL)
    assert m["cagr"] == pytest.approx(0.0, abs=0.01)


# ── Days held ──────────────────────────────────────────────────────────────────

def test_days_held_with_sell_date():
    buy  = date(2023, 1, 1)
    sell = date(2023, 7, 1)
    m = compute_metrics(1, 100.0, buy, 110.0, sell)
    assert m["days_held"] == (sell - buy).days

def test_days_held_minimum_is_one():
    # Same buy and sell date → still 1 day minimum
    same = date(2024, 6, 1)
    m = compute_metrics(1, 100.0, same, 105.0, same)
    assert m["days_held"] == 1

def test_days_held_without_sell_date_uses_today():
    # Without sell_date, days_held should be positive (position is live)
    m = compute_metrics(1, 100.0, date(2023, 1, 1), 110.0)
    assert m["days_held"] > 0


# ── Edge cases ─────────────────────────────────────────────────────────────────

def test_fractional_shares():
    m = compute_metrics(0.5, 100.0, BUY, 200.0, SELL)
    assert m["total_cost"]    == pytest.approx(50.0)
    assert m["current_value"] == pytest.approx(100.0)

def test_large_share_count():
    m = compute_metrics(1_000_000, 1.0, BUY, 2.0, SELL)
    assert m["gain_loss"] == pytest.approx(1_000_000.0)

def test_all_keys_present():
    m = compute_metrics(1, 100.0, BUY, 110.0, SELL)
    for key in ("total_cost", "current_value", "gain_loss", "pct_return", "cagr", "days_held", "years_held"):
        assert key in m

def test_years_held():
    m = compute_metrics(1, 100.0, BUY, 110.0, SELL)
    assert m["years_held"] == pytest.approx(365 / 365.25, rel=1e-4)
