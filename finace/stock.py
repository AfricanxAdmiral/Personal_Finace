"""Yahoo Finance data access with persistent caching.

Query strategy
--------------
get_current_price  — SQLite cache with 5-min TTL; one network call per ticker
                     per 5 minutes across all sessions.
get_stock_info     — SQLite cache with 24-hr TTL; rarely re-fetched.
fetch_history      — Incremental: only the date range *not already stored* in
                     SQLite triggers a yfinance call.  Past prices are immutable
                     so they are fetched once and never again.
"""

from datetime import date, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

import finace.cache as _cache


# ── Current price ──────────────────────────────────────────────────────────────

def get_current_price(ticker: str) -> Optional[float]:
    cached = _cache.get_price(ticker)
    if cached is not None:
        return cached
    try:
        price = yf.Ticker(ticker).fast_info.last_price
        if price:
            result = float(price)
            _cache.set_price(ticker, result)
            return result
        return None
    except Exception:
        return None


# ── Stock info ─────────────────────────────────────────────────────────────────

def get_stock_info(ticker: str) -> dict:
    cached = _cache.get_info(ticker)
    if cached is not None:
        return cached
    try:
        info = yf.Ticker(ticker).info
        result = {
            "name":     info.get("longName") or info.get("shortName") or ticker,
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", ""),
        }
        _cache.set_info(ticker, result)
        return result
    except Exception:
        return {"name": ticker, "currency": "USD", "exchange": ""}


# ── Price history ──────────────────────────────────────────────────────────────

def fetch_history(ticker: str, start: str, end: str) -> pd.Series:
    """Return daily close prices with persistent incremental caching.

    Only calls yfinance for the portion of [start, end] not already stored:

    - First call for a ticker   → full range fetched and stored.
    - Subsequent calls          → only the gap from latest_cached_date → end.
    - Already up-to-date        → pure SQLite read, zero network calls.
    """
    today   = date.today()
    req_end = date.fromisoformat(end)
    latest  = _cache.latest_cached_date(ticker)

    if latest is None:
        # Nothing cached at all — fetch the full requested range.
        _yf_fetch_and_store(ticker, start, end)

    else:
        # Fetch the gap between our latest cached date and the requested end.
        # Give a 1-day slack so weekends / holidays don't cause spurious fetches.
        gap_threshold = min(req_end, today) - timedelta(days=1)
        if latest < gap_threshold:
            fetch_from = (latest + timedelta(days=1)).isoformat()
            _yf_fetch_and_store(ticker, fetch_from, end)

        # Always try to refresh today's close if it falls within the range.
        elif req_end >= today and latest < today:
            _yf_fetch_and_store(ticker, today.isoformat(), (today + timedelta(days=1)).isoformat())

    return _cache.get_history(ticker, start, end)


def _yf_fetch_and_store(ticker: str, start: str, end: str) -> None:
    """Fetch from yfinance and write results to the history cache."""
    try:
        hist = yf.Ticker(ticker).history(start=start, end=end)
        if not hist.empty:
            s = hist["Close"].copy()
            s.index = pd.DatetimeIndex(s.index.date)
            _cache.set_history(ticker, s)
    except Exception:
        pass
