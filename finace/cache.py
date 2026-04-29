"""Persistent SQLite cache for prices, stock info, and price history.

Design
------
- Current prices : cached with a 5-minute TTL (staleness is expected).
- Stock info      : cached with a 24-hour TTL.
- Price history   : cached permanently by (ticker, date).  Past prices are
  immutable, so they never need to be re-fetched.  Only the gap between the
  latest stored date and today triggers a network call.

The module-level ``_CACHE_FILE`` path is intentionally mutable so tests can
redirect it to a temporary file via ``monkeypatch.setattr``.
"""

import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import date
from typing import Optional

import pandas as pd

_CACHE_FILE: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "price_cache.db")
)

PRICE_TTL = 300       # 5 minutes
INFO_TTL  = 86_400    # 24 hours


# ── Internal DB helpers ────────────────────────────────────────────────────────

@contextmanager
def _db():
    conn = sqlite3.connect(_CACHE_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    _init_schema(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS price_cache (
            ticker     TEXT PRIMARY KEY,
            price      REAL NOT NULL,
            fetched_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS info_cache (
            ticker     TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            currency   TEXT NOT NULL,
            exchange   TEXT NOT NULL,
            fetched_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS history_cache (
            ticker TEXT NOT NULL,
            date   TEXT NOT NULL,
            close  REAL NOT NULL,
            PRIMARY KEY (ticker, date)
        );
    """)


# ── Current price ──────────────────────────────────────────────────────────────

def get_price(ticker: str) -> Optional[float]:
    with _db() as conn:
        row = conn.execute(
            "SELECT price, fetched_at FROM price_cache WHERE ticker = ?", (ticker,)
        ).fetchone()
    if row and time.time() - row[1] < PRICE_TTL:
        return row[0]
    return None


def set_price(ticker: str, price: float) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO price_cache VALUES (?, ?, ?)",
            (ticker, price, time.time()),
        )


# ── Stock info ─────────────────────────────────────────────────────────────────

def get_info(ticker: str) -> Optional[dict]:
    with _db() as conn:
        row = conn.execute(
            "SELECT name, currency, exchange, fetched_at FROM info_cache WHERE ticker = ?",
            (ticker,),
        ).fetchone()
    if row and time.time() - row[3] < INFO_TTL:
        return {"name": row[0], "currency": row[1], "exchange": row[2]}
    return None


def set_info(ticker: str, info: dict) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO info_cache VALUES (?, ?, ?, ?, ?)",
            (ticker, info["name"], info["currency"], info["exchange"], time.time()),
        )


# ── Price history ──────────────────────────────────────────────────────────────

def get_history(ticker: str, start: str, end: str) -> pd.Series:
    """Return cached close prices for *ticker* in [start, end] (ISO dates, inclusive)."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT date, close FROM history_cache "
            "WHERE ticker = ? AND date >= ? AND date <= ? ORDER BY date",
            (ticker, start, end),
        ).fetchall()
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series({r[0]: r[1] for r in rows})
    s.index = pd.DatetimeIndex(s.index)
    return s


def set_history(ticker: str, series: pd.Series) -> None:
    """Upsert close prices into the history cache."""
    if series.empty:
        return
    rows = [
        (ticker, str(idx.date()) if hasattr(idx, "date") else str(idx), float(val))
        for idx, val in series.items()
        if not pd.isna(val)
    ]
    if not rows:
        return
    with _db() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO history_cache VALUES (?, ?, ?)", rows
        )


def latest_cached_date(ticker: str) -> Optional[date]:
    """Return the most recent date stored in history_cache for *ticker*, or None."""
    with _db() as conn:
        row = conn.execute(
            "SELECT MAX(date) FROM history_cache WHERE ticker = ?", (ticker,)
        ).fetchone()
    return date.fromisoformat(row[0]) if (row and row[0]) else None


def cache_stats() -> dict:
    """Return row counts for each table — useful for diagnostics."""
    with _db() as conn:
        return {
            "price_cache":   conn.execute("SELECT COUNT(*) FROM price_cache").fetchone()[0],
            "info_cache":    conn.execute("SELECT COUNT(*) FROM info_cache").fetchone()[0],
            "history_cache": conn.execute("SELECT COUNT(*) FROM history_cache").fetchone()[0],
        }
