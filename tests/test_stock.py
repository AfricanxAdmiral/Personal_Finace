"""Tests for finace.stock — yfinance wrappers with SQLite caching."""
import pandas as pd
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, call

from finace.stock import fetch_history, get_current_price, get_stock_info

# All tests use a temporary SQLite DB so they never pollute or read the real cache.
pytestmark = pytest.mark.usefixtures("tmp_cache")


# ── Mock factory ───────────────────────────────────────────────────────────────

def _make_ticker(price=175.5, info=None, history_df=None):
    mock = MagicMock()
    mock.fast_info.last_price = price
    mock.info = info or {
        "longName": "Apple Inc.",
        "currency": "USD",
        "exchange": "NASDAQ",
    }
    if history_df is None:
        history_df = pd.DataFrame(
            {"Close": [170.0, 172.0, 175.5]},
            index=pd.date_range("2024-01-02", periods=3, freq="B"),
        )
    mock.history.return_value = history_df
    return mock


# ── get_current_price ──────────────────────────────────────────────────────────

def test_get_current_price_returns_correct_value(monkeypatch):
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: _make_ticker(price=175.5))
    assert get_current_price("AAPL") == pytest.approx(175.5)

def test_get_current_price_is_float(monkeypatch):
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: _make_ticker(price=175.5))
    assert isinstance(get_current_price("AAPL"), float)

def test_get_current_price_none_when_yf_returns_none(monkeypatch):
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: _make_ticker(price=None))
    assert get_current_price("FAKE") is None

def test_get_current_price_none_when_yf_returns_zero(monkeypatch):
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: _make_ticker(price=0))
    assert get_current_price("ZERO") is None

def test_get_current_price_none_on_exception(monkeypatch):
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: (_ for _ in ()).throw(Exception()))
    assert get_current_price("BAD") is None

def test_get_current_price_stored_in_cache(monkeypatch):
    import finace.cache as c
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: _make_ticker(price=175.5))
    get_current_price("AAPL")
    assert c.get_price("AAPL") == pytest.approx(175.5)

def test_get_current_price_uses_cache_on_second_call(monkeypatch):
    call_count = {"n": 0}
    def counting_ticker(t):
        call_count["n"] += 1
        return _make_ticker(price=175.5)
    monkeypatch.setattr("finace.stock.yf.Ticker", counting_ticker)
    get_current_price("AAPL")  # populates cache
    get_current_price("AAPL")  # should be served from cache
    assert call_count["n"] == 1


# ── get_stock_info ─────────────────────────────────────────────────────────────

def test_get_stock_info_name(monkeypatch):
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: _make_ticker())
    assert get_stock_info("AAPL")["name"] == "Apple Inc."

def test_get_stock_info_currency(monkeypatch):
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: _make_ticker())
    assert get_stock_info("AAPL")["currency"] == "USD"

def test_get_stock_info_exchange(monkeypatch):
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: _make_ticker())
    assert get_stock_info("AAPL")["exchange"] == "NASDAQ"

def test_get_stock_info_fallback_on_exception(monkeypatch):
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: (_ for _ in ()).throw(Exception()))
    info = get_stock_info("XYZ")
    assert info["name"] == "XYZ"
    assert info["currency"] == "USD"

def test_get_stock_info_uses_shortName_fallback(monkeypatch):
    ticker = _make_ticker(info={"shortName": "Short Co", "currency": "USD", "exchange": "NYSE"})
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: ticker)
    assert get_stock_info("SC")["name"] == "Short Co"

def test_get_stock_info_stored_in_cache(monkeypatch):
    import finace.cache as c
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: _make_ticker())
    get_stock_info("AAPL")
    assert c.get_info("AAPL") is not None

def test_get_stock_info_uses_cache_on_second_call(monkeypatch):
    call_count = {"n": 0}
    def counting_ticker(t):
        call_count["n"] += 1
        return _make_ticker()
    monkeypatch.setattr("finace.stock.yf.Ticker", counting_ticker)
    get_stock_info("AAPL")
    get_stock_info("AAPL")
    assert call_count["n"] == 1


# ── fetch_history ──────────────────────────────────────────────────────────────

def test_fetch_history_returns_series(monkeypatch):
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: _make_ticker())
    s = fetch_history("AAPL", "2024-01-02", "2024-01-05")
    assert isinstance(s, pd.Series)

def test_fetch_history_index_is_timezone_naive(monkeypatch):
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: _make_ticker())
    s = fetch_history("AAPL", "2024-01-02", "2024-01-05")
    assert s.index.tz is None

def test_fetch_history_empty_on_no_yf_data(monkeypatch):
    ticker = _make_ticker(history_df=pd.DataFrame())
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: ticker)
    assert fetch_history("FAKE", "2024-01-02", "2024-01-05").empty

def test_fetch_history_stores_in_cache(monkeypatch):
    import finace.cache as c
    monkeypatch.setattr("finace.stock.yf.Ticker", lambda t: _make_ticker())
    fetch_history("AAPL", "2024-01-02", "2024-01-05")
    assert c.latest_cached_date("AAPL") is not None

def test_fetch_history_second_call_skips_yfinance(monkeypatch):
    """After the first fetch, a same-range request must not call yfinance again."""
    call_count = {"n": 0}

    # Provide a history spanning well into the past so "latest" is recent enough
    # that the gap-threshold check is satisfied.
    yesterday = date.today() - timedelta(days=1)
    hist_df = pd.DataFrame(
        {"Close": [170.0, 172.0]},
        index=pd.DatetimeIndex([yesterday - timedelta(days=1), yesterday]),
    )
    def counting_ticker(t):
        call_count["n"] += 1
        return _make_ticker(history_df=hist_df)

    monkeypatch.setattr("finace.stock.yf.Ticker", counting_ticker)

    start = (yesterday - timedelta(days=2)).isoformat()
    end   = yesterday.isoformat()
    fetch_history("AAPL", start, end)   # first call — hits yfinance
    fetch_history("AAPL", start, end)   # second call — must use cache
    assert call_count["n"] == 1

def test_fetch_history_incremental_only_fetches_gap(monkeypatch):
    """Re-requesting with an extended end date should fetch only the new portion."""
    import finace.cache as c

    # Seed cache with data up to 2024-03-01
    seed = pd.Series({"2024-01-02": 180.0, "2024-03-01": 185.0})
    seed.index = pd.DatetimeIndex(seed.index)
    c.set_history("AAPL", seed)

    history_requests = []
    def capturing_ticker(t):
        mock = _make_ticker()
        def record(start, end):
            history_requests.append((start, end))
            # Return one extra day of data
            return pd.DataFrame(
                {"Close": [190.0]},
                index=pd.DatetimeIndex(["2024-06-01"]),
            )
        mock.history = record
        return mock

    monkeypatch.setattr("finace.stock.yf.Ticker", capturing_ticker)
    fetch_history("AAPL", "2024-01-02", "2024-06-01")

    # Only one yfinance call and it starts AFTER our last cached date
    assert len(history_requests) == 1
    fetched_start = date.fromisoformat(history_requests[0][0])
    assert fetched_start > date(2024, 3, 1)

def test_fetch_history_passes_correct_dates_to_yfinance(monkeypatch):
    calls = []

    def capturing_ticker(t):
        mock = _make_ticker()
        def record(start, end):
            calls.append({"start": start, "end": end})
            return mock.history.return_value
        mock.history = record
        return mock

    monkeypatch.setattr("finace.stock.yf.Ticker", capturing_ticker)
    fetch_history("AAPL", "2024-01-02", "2024-01-06")
    assert calls[0]["start"] == "2024-01-02"
