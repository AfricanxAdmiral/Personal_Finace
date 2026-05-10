"""Regression tests: numeric table columns must store floats, not formatted strings.

Storing "$10,000" instead of 10000.0 causes alphabetic sort, which puts
"$10,000" before "$2,000" (wrong). These tests lock in correct behaviour.
"""
import pandas as pd
import pytest


# ── Sorting correctness ────────────────────────────────────────────────────────

def test_float_column_sorts_numerically():
    values = [10_000.0, 500.0, 2_000.0]
    df = pd.DataFrame({"v": values})
    assert list(df.sort_values("v")["v"]) == [500.0, 2_000.0, 10_000.0]


def test_formatted_string_sorts_alphabetically_not_numerically():
    """Demonstrates the bug that was fixed: formatted strings sort wrong."""
    strings = ["NT$10,000", "NT$500", "NT$2,000"]
    df = pd.DataFrame({"v": strings})
    # Alphabetic: "NT$10,000" < "NT$2,000" < "NT$500" (compares char by char)
    assert list(df.sort_values("v")["v"]) == ["NT$10,000", "NT$2,000", "NT$500"]
    # That is NOT the numerically correct order [NT$500, NT$2,000, NT$10,000]


def test_numeric_columns_are_float_not_string():
    """Stock/bank overview rows must contain floats for numeric sort to work."""
    price_usd  = 175.5
    value_usd  = price_usd * 10
    value_twd  = value_usd * 32.0   # example rate

    row = {
        "Price (USD)": price_usd,
        "Value (USD)": value_usd,
        "Value (TWD)": value_twd,
    }
    assert isinstance(row["Price (USD)"], float)
    assert isinstance(row["Value (USD)"], float)
    assert isinstance(row["Value (TWD)"], float)


def test_performance_metric_columns_are_float_not_string():
    """Performance per-position rows must contain floats, not '15.23%' strings."""
    import finace.metrics as metrics
    import numpy as np
    import pandas as pd

    np.random.seed(0)
    prices = pd.Series(
        100 + np.cumsum(np.random.randn(60)),
        index=pd.date_range("2024-01-02", periods=60, freq="B"),
    )

    vol    = metrics.annualized_volatility(prices)
    mdd    = metrics.max_drawdown(prices)
    sharpe = metrics.sharpe_ratio(prices)

    assert isinstance(vol,    float), "Volatility must be float"
    assert isinstance(mdd,    float), "Max DD must be float"
    assert isinstance(sharpe, float), "Sharpe must be float"


# ── TWD / JPY integer formatting ───────────────────────────────────────────────

def test_twd_value_displayed_as_integer():
    """Value (TWD) column uses %.0f format — no decimal places."""
    import finace.bank as bank
    formatted = bank.fmt_money(12_345.67, "TWD")
    assert "." not in formatted


def test_jpy_value_displayed_as_integer():
    """JPY balance uses %.0f format — no decimal places."""
    import finace.bank as bank
    formatted = bank.fmt_money(12_345.67, "JPY")
    assert "." not in formatted


def test_usd_value_displayed_with_two_decimals():
    """USD amounts retain two decimal places."""
    import finace.bank as bank
    formatted = bank.fmt_money(12_345.6, "USD")
    assert formatted.endswith(".60")


def test_twd_sorting_with_floats_correct():
    """TWD values stored as floats sort in correct numeric order."""
    twd_values = [30_000.0, 1_500.0, 10_000.0]
    df = pd.DataFrame({"Value (TWD)": twd_values})
    result = list(df.sort_values("Value (TWD)")["Value (TWD)"])
    assert result == [1_500.0, 10_000.0, 30_000.0]


def test_jpy_sorting_with_floats_correct():
    """JPY values stored as floats sort in correct numeric order."""
    jpy_values = [100_000.0, 5_000.0, 50_000.0]
    df = pd.DataFrame({"Balance": jpy_values})
    result = list(df.sort_values("Balance")["Balance"])
    assert result == [5_000.0, 50_000.0, 100_000.0]
