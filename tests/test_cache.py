"""Tests for finace.cache — SQLite persistence layer."""
import time
import pandas as pd
import pytest
from datetime import date

import finace.cache as c


# All tests use tmp_cache so they never touch the real price_cache.db
pytestmark = pytest.mark.usefixtures("tmp_cache")


# ── price cache ────────────────────────────────────────────────────────────────

def test_price_miss_returns_none():
    assert c.get_price("AAPL") is None

def test_price_hit_returns_value():
    c.set_price("AAPL", 175.5)
    assert c.get_price("AAPL") == pytest.approx(175.5)

def test_price_hit_returns_float():
    c.set_price("AAPL", 175.5)
    assert isinstance(c.get_price("AAPL"), float)

def test_price_overwrite():
    c.set_price("AAPL", 100.0)
    c.set_price("AAPL", 200.0)
    assert c.get_price("AAPL") == pytest.approx(200.0)

def test_price_expired_returns_none(monkeypatch):
    # Store with a timestamp 10 minutes in the past
    old_time = time.time() - 601
    monkeypatch.setattr(time, "time", lambda: old_time)
    c.set_price("AAPL", 175.5)
    # Restore real time for the read
    monkeypatch.setattr(time, "time", lambda: old_time + 700)
    assert c.get_price("AAPL") is None

def test_price_isolated_by_ticker():
    c.set_price("AAPL", 175.5)
    assert c.get_price("MSFT") is None


# ── info cache ─────────────────────────────────────────────────────────────────

def test_info_miss_returns_none():
    assert c.get_info("AAPL") is None

def test_info_hit_returns_dict():
    c.set_info("AAPL", {"name": "Apple Inc.", "currency": "USD", "exchange": "NASDAQ"})
    info = c.get_info("AAPL")
    assert info["name"]     == "Apple Inc."
    assert info["currency"] == "USD"
    assert info["exchange"] == "NASDAQ"

def test_info_overwrite():
    c.set_info("AAPL", {"name": "Old", "currency": "USD", "exchange": "X"})
    c.set_info("AAPL", {"name": "New", "currency": "USD", "exchange": "Y"})
    assert c.get_info("AAPL")["name"] == "New"

def test_info_expired_returns_none(monkeypatch):
    old_time = time.time() - 90_000  # > 24 h ago
    monkeypatch.setattr(time, "time", lambda: old_time)
    c.set_info("AAPL", {"name": "A", "currency": "USD", "exchange": "X"})
    monkeypatch.setattr(time, "time", lambda: old_time + 90_001)
    assert c.get_info("AAPL") is None


# ── history cache ──────────────────────────────────────────────────────────────

def test_history_miss_returns_empty_series():
    s = c.get_history("AAPL", "2024-01-01", "2024-03-01")
    assert s.empty

def test_history_store_and_retrieve():
    series = pd.Series(
        {"2024-01-02": 185.0, "2024-01-03": 187.0},
    )
    series.index = pd.DatetimeIndex(series.index)
    c.set_history("AAPL", series)

    result = c.get_history("AAPL", "2024-01-01", "2024-01-05")
    assert len(result) == 2
    assert result["2024-01-02"] == pytest.approx(185.0)
    assert result["2024-01-03"] == pytest.approx(187.0)

def test_history_date_range_filtering():
    series = pd.Series(
        {"2024-01-02": 185.0, "2024-01-03": 187.0, "2024-01-04": 189.0},
    )
    series.index = pd.DatetimeIndex(series.index)
    c.set_history("AAPL", series)

    result = c.get_history("AAPL", "2024-01-02", "2024-01-03")
    assert len(result) == 2
    assert "2024-01-04" not in result.index.astype(str)

def test_history_upsert_updates_existing():
    s1 = pd.Series({"2024-01-02": 185.0})
    s1.index = pd.DatetimeIndex(s1.index)
    c.set_history("AAPL", s1)

    s2 = pd.Series({"2024-01-02": 190.0})  # same date, new price
    s2.index = pd.DatetimeIndex(s2.index)
    c.set_history("AAPL", s2)

    result = c.get_history("AAPL", "2024-01-01", "2024-01-05")
    assert result["2024-01-02"] == pytest.approx(190.0)

def test_history_isolated_by_ticker():
    series = pd.Series({"2024-01-02": 185.0})
    series.index = pd.DatetimeIndex(series.index)
    c.set_history("AAPL", series)
    assert c.get_history("MSFT", "2024-01-01", "2024-01-05").empty

def test_history_skips_nan_values():
    import numpy as np
    series = pd.Series({"2024-01-02": 185.0, "2024-01-03": float("nan")})
    series.index = pd.DatetimeIndex(series.index)
    c.set_history("AAPL", series)
    result = c.get_history("AAPL", "2024-01-01", "2024-01-05")
    assert len(result) == 1


# ── latest_cached_date ─────────────────────────────────────────────────────────

def test_latest_cached_date_none_when_empty():
    assert c.latest_cached_date("AAPL") is None

def test_latest_cached_date_correct():
    series = pd.Series(
        {"2024-01-02": 185.0, "2024-01-05": 190.0, "2024-01-03": 187.0},
    )
    series.index = pd.DatetimeIndex(series.index)
    c.set_history("AAPL", series)
    assert c.latest_cached_date("AAPL") == date(2024, 1, 5)

def test_latest_cached_date_isolated_by_ticker():
    series = pd.Series({"2024-06-01": 100.0})
    series.index = pd.DatetimeIndex(series.index)
    c.set_history("AAPL", series)
    assert c.latest_cached_date("MSFT") is None


# ── cache_stats ────────────────────────────────────────────────────────────────

def test_cache_stats_returns_counts():
    c.set_price("AAPL", 175.0)
    c.set_info("AAPL", {"name": "Apple", "currency": "USD", "exchange": "NASDAQ"})
    s = pd.Series({"2024-01-02": 185.0})
    s.index = pd.DatetimeIndex(s.index)
    c.set_history("AAPL", s)

    stats = c.cache_stats()
    assert stats["price_cache"]   == 1
    assert stats["info_cache"]    == 1
    assert stats["history_cache"] == 1
