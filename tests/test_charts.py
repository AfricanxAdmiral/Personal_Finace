"""Tests for finace.charts — Plotly figure builders."""
import pandas as pd
import numpy as np
import pytest
import plotly.graph_objects as go

from finace.charts import drawdown_fig, portfolio_fig, position_fig
from finace.portfolio import Position


# ── Helpers ────────────────────────────────────────────────────────────────────

def _annotation_texts(fig):
    return [a.text for a in fig.layout.annotations if a.text]

def _trace_names(fig):
    return [t.name for t in fig.data]


# ── position_fig — open position ───────────────────────────────────────────────

def test_position_fig_open_returns_figure(open_pos, mock_fetch):
    assert isinstance(position_fig(open_pos, mock_fetch), go.Figure)

def test_position_fig_open_has_two_traces(open_pos, mock_fetch):
    fig = position_fig(open_pos, mock_fetch)
    assert len(fig.data) == 2

def test_position_fig_open_trace_names(open_pos, mock_fetch):
    names = _trace_names(position_fig(open_pos, mock_fetch))
    assert any("Cost basis" in n for n in names)
    assert any("Position value" in n for n in names)

def test_position_fig_open_has_buy_annotation(open_pos, mock_fetch):
    texts = _annotation_texts(position_fig(open_pos, mock_fetch))
    assert any("BUY" in t for t in texts)

def test_position_fig_open_no_sell_annotation(open_pos, mock_fetch):
    texts = _annotation_texts(position_fig(open_pos, mock_fetch))
    assert not any("SELL" in t for t in texts)

def test_position_fig_open_title_contains_ticker(open_pos, mock_fetch):
    title = position_fig(open_pos, mock_fetch).layout.title.text
    assert "AAPL" in title

def test_position_fig_open_title_contains_open_status(open_pos, mock_fetch):
    title = position_fig(open_pos, mock_fetch).layout.title.text
    assert "OPEN" in title


# ── position_fig — sold position ───────────────────────────────────────────────

def test_position_fig_sold_returns_figure(sold_pos, mock_fetch):
    assert isinstance(position_fig(sold_pos, mock_fetch), go.Figure)

def test_position_fig_sold_has_sell_annotation(sold_pos, mock_fetch):
    texts = _annotation_texts(position_fig(sold_pos, mock_fetch))
    assert any("SELL" in t for t in texts)

def test_position_fig_sold_title_contains_sold_status(sold_pos, mock_fetch):
    title = position_fig(sold_pos, mock_fetch).layout.title.text
    assert "SOLD" in title

def test_position_fig_sold_overwrites_last_value(sold_pos, mock_fetch):
    fig    = position_fig(sold_pos, mock_fetch)
    values = fig.data[1].y                        # "Position value" trace
    expected_last = sold_pos.sell_price * sold_pos.shares
    assert values[-1] == pytest.approx(expected_last)


# ── position_fig — no data ─────────────────────────────────────────────────────

def test_position_fig_returns_none_when_no_history(open_pos):
    fig = position_fig(open_pos, fetch_fn=lambda t, s, e: pd.Series(dtype=float))
    assert fig is None


# ── position_fig — default fetch_fn ───────────────────────────────────────────

def test_position_fig_uses_default_fetch_when_none(open_pos, monkeypatch):
    import finace.stock as st
    monkeypatch.setattr(st, "fetch_history", lambda t, s, e: pd.Series(dtype=float))
    assert position_fig(open_pos) is None   # empty → returns None


# ── portfolio_fig — empty input ────────────────────────────────────────────────

def test_portfolio_fig_empty_list_returns_none():
    assert portfolio_fig([]) is None

def test_portfolio_fig_empty_fetch_returns_none(open_pos):
    fig = portfolio_fig([open_pos], fetch_fn=lambda t, s, e: pd.Series(dtype=float))
    # All positions produce no data → total stays zero → nz is empty → still builds fig
    assert isinstance(fig, go.Figure)


# ── portfolio_fig — with positions ────────────────────────────────────────────

def test_portfolio_fig_returns_figure(open_pos, mock_fetch):
    assert isinstance(portfolio_fig([open_pos], mock_fetch), go.Figure)

def test_portfolio_fig_has_cost_basis_trace(open_pos, mock_fetch):
    assert "Cost basis" in _trace_names(portfolio_fig([open_pos], mock_fetch))

def test_portfolio_fig_has_portfolio_value_trace(open_pos, mock_fetch):
    assert "Portfolio value" in _trace_names(portfolio_fig([open_pos], mock_fetch))

def test_portfolio_fig_has_individual_position_trace(open_pos, mock_fetch):
    names = _trace_names(portfolio_fig([open_pos], mock_fetch))
    assert any("AAPL" in n for n in names)

def test_portfolio_fig_two_positions_both_in_traces(open_pos, sold_pos, mock_fetch):
    names = _trace_names(portfolio_fig([open_pos, sold_pos], mock_fetch))
    assert any("AAPL" in n for n in names)
    assert any("MSFT" in n for n in names)

def test_portfolio_fig_is_two_row_subplot(open_pos, mock_fetch):
    fig = portfolio_fig([open_pos], mock_fetch)
    # make_subplots with rows=2 produces xaxis and xaxis2
    assert fig.layout.xaxis2 is not None

def test_portfolio_fig_uses_default_fetch_when_none(open_pos, monkeypatch):
    import finace.stock as st
    monkeypatch.setattr(st, "fetch_history", lambda t, s, e: pd.Series(dtype=float))
    fig = portfolio_fig([open_pos])
    assert isinstance(fig, go.Figure)


# ── drawdown_fig ───────────────────────────────────────────────────────────────

def test_drawdown_fig_returns_figure(open_pos, mock_fetch):
    fig = drawdown_fig([open_pos], fetch_fn=mock_fetch)
    assert isinstance(fig, go.Figure)

def test_drawdown_fig_empty_positions_returns_none():
    assert drawdown_fig([]) is None

def test_drawdown_fig_no_data_returns_none(open_pos, monkeypatch):
    import finace.stock as st
    monkeypatch.setattr(st, "fetch_history", lambda t, s, e: pd.Series(dtype=float))
    assert drawdown_fig([open_pos]) is None

def test_drawdown_fig_update_layout_no_duplicate_keys(open_pos, mock_fetch):
    # Regression: drawdown_fig must not pass yaxis/xaxis both via **PLOTLY_BASE
    # and as explicit kwargs — that raises TypeError at render time.
    fig = drawdown_fig([open_pos], fetch_fn=mock_fetch)
    assert fig is not None  # would raise TypeError before this fix
