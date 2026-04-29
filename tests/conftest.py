"""Shared fixtures for all test modules."""
import numpy as np
import pandas as pd
import pytest

from finace.portfolio import Position


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    """Redirect the SQLite cache to a temp file so tests never touch the real DB."""
    import finace.cache as c
    monkeypatch.setattr(c, "_CACHE_FILE", str(tmp_path / "test_cache.db"))


@pytest.fixture
def tmp_portfolio(tmp_path, monkeypatch):
    """Redirect portfolio storage to a temp file for the duration of the test."""
    import finace.portfolio as pf
    monkeypatch.setattr(pf, "PORTFOLIO_FILE", str(tmp_path / "portfolio.json"))


@pytest.fixture
def tmp_bank(tmp_path, monkeypatch):
    """Redirect bank storage to a temp file for the duration of the test."""
    import finace.bank as bk
    monkeypatch.setattr(bk, "BANK_FILE", str(tmp_path / "bank.json"))


@pytest.fixture
def fake_prices():
    """60 business-days of synthetic close prices starting 2024-01-02."""
    np.random.seed(42)
    dates  = pd.date_range(start="2024-01-02", periods=60, freq="B")
    prices = 150.0 + np.cumsum(np.random.randn(60) * 2)
    return pd.Series(prices, index=pd.DatetimeIndex(dates.date))


@pytest.fixture
def mock_fetch(fake_prices):
    """History fetcher that returns fake_prices regardless of arguments."""
    def _fetch(ticker, start, end):
        return fake_prices
    return _fetch


@pytest.fixture
def open_pos():
    return Position(id=1, ticker="AAPL", shares=10.0, buy_price=150.0, buy_date="2024-01-02")


@pytest.fixture
def sold_pos():
    return Position(
        id=2, ticker="MSFT", shares=5.0, buy_price=370.0,
        buy_date="2024-01-02", sell_price=420.0, sell_date="2024-04-01",
    )
