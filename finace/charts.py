"""Plotly chart builders for position and portfolio views.

Both public functions accept an optional ``fetch_fn`` so callers can inject
a cached or mocked history fetcher without patching globals.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, List, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from finace.calculator import compute_metrics
from finace.portfolio import Position
import finace.stock as _stock

# ── Shared style constants ─────────────────────────────────────────────────────

PLOTLY_BASE = dict(
    plot_bgcolor="#0d1117",
    paper_bgcolor="#0d1117",
    font_color="#e6edf3",
    legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1),
    xaxis=dict(showgrid=True, gridcolor="#21262d"),
    yaxis=dict(showgrid=True, gridcolor="#21262d", tickprefix="$", tickformat=",.0f"),
    hovermode="x unified",
    margin=dict(t=60, b=40, l=60, r=20),
)

PALETTE = [
    "#58a6ff", "#3fb950", "#d2a8ff", "#ffa657", "#f85149",
    "#79c0ff", "#56d364", "#bc8cff", "#ffb86c", "#ff7b72",
]


# ── Internal helpers ───────────────────────────────────────────────────────────

def _vmarker(fig: go.Figure, x_ts, color: str, label: str) -> None:
    """Add a vertical dotted line + annotation to a figure."""
    fig.add_shape(
        type="line",
        x0=x_ts, x1=x_ts, y0=0, y1=1, yref="paper",
        line=dict(color=color, width=1.5, dash="dot"),
    )
    fig.add_annotation(
        x=x_ts, y=1.02, yref="paper",
        text=label, font=dict(color=color, size=11),
        showarrow=False, xanchor="left",
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def position_fig(
    pos: Position,
    fetch_fn: Optional[Callable] = None,
) -> Optional[go.Figure]:
    """Build an interactive Plotly figure for a single position.

    Returns ``None`` if no price history is available.
    """
    if fetch_fn is None:
        fetch_fn = _stock.fetch_history

    end_date = date.fromisoformat(pos.sell_date) if pos.sell_date else date.today()
    prices   = fetch_fn(
        pos.ticker,
        pos.buy_date,
        (end_date + timedelta(days=1)).isoformat(),
    )
    if prices.empty:
        return None

    values = prices * pos.shares
    if pos.sell_price is not None:
        values.iloc[-1] = pos.sell_price * pos.shares

    cost_basis  = pos.buy_price * pos.shares
    final_price = pos.sell_price or float(prices.iloc[-1])
    m = compute_metrics(
        pos.shares, pos.buy_price,
        date.fromisoformat(pos.buy_date), final_price,
        date.fromisoformat(pos.sell_date) if pos.sell_date else None,
    )

    is_up      = m["gain_loss"] >= 0
    fill_color = "rgba(63,185,80,0.15)" if is_up else "rgba(248,81,73,0.15)"
    kpi_color  = "#3fb950" if is_up else "#f85149"
    status     = "SOLD" if pos.sell_price else "OPEN"

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=values.index, y=[cost_basis] * len(values),
        mode="lines",
        line=dict(color="#484f58", width=1.5, dash="dash"),
        name=f"Cost basis  ${cost_basis:,.2f}",
        hovertemplate="Cost basis: $%{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=values.index, y=values.values,
        mode="lines",
        fill="tonexty",
        fillcolor=fill_color,
        line=dict(color="#58a6ff", width=2.5),
        name="Position value",
        hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.2f}<extra></extra>",
    ))

    _vmarker(fig, values.index[0],  "#3fb950", f"BUY ${pos.buy_price:,.2f}")
    if pos.sell_price is not None:
        _vmarker(fig, values.index[-1], "#f85149", f"SELL ${pos.sell_price:,.2f}")

    fig.update_layout(
        **PLOTLY_BASE,
        title=dict(
            text=(
                f"<b>{pos.ticker}</b>  ·  {pos.shares:g} shares  [{status}]<br>"
                f"<span style='font-size:13px;color:{kpi_color}'>"
                f"P&L  ${m['gain_loss']:+,.2f}  ({m['pct_return']:+.2f}%)  "
                f"·  Ann. Return {m['cagr']:+.2f}%  "
                f"·  {m['days_held']} days"
                f"</span>"
            ),
            font_size=17,
        ),
        height=460,
    )
    return fig


def portfolio_fig(
    positions: List[Position],
    fetch_fn: Optional[Callable] = None,
) -> Optional[go.Figure]:
    """Build a two-panel Plotly figure: total portfolio + individual positions.

    Returns ``None`` if ``positions`` is empty.
    """
    if fetch_fn is None:
        fetch_fn = _stock.fetch_history

    if not positions:
        return None

    today     = date.today()
    all_start = min(date.fromisoformat(p.buy_date) for p in positions)
    date_idx  = pd.date_range(start=all_start, end=today, freq="D")

    total_value = pd.Series(0.0, index=date_idx)
    total_cost  = pd.Series(0.0, index=date_idx)

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.62, 0.38],
        vertical_spacing=0.06,
        subplot_titles=["Total Portfolio Value", "Individual Positions"],
    )

    for i, pos in enumerate(positions):
        buy_dt   = pd.Timestamp(pos.buy_date)
        end_dt   = pd.Timestamp(pos.sell_date) if pos.sell_date else pd.Timestamp(today)
        end_date = date.fromisoformat(pos.sell_date) if pos.sell_date else today

        prices = fetch_fn(
            pos.ticker, pos.buy_date,
            (end_date + timedelta(days=1)).isoformat(),
        )
        if prices.empty:
            continue

        prices_daily = prices.reindex(date_idx).ffill()
        mask      = (date_idx >= buy_dt) & (date_idx <= end_dt)
        pos_value = (prices_daily * pos.shares).where(mask, 0.0)
        pos_cost  = pd.Series(pos.shares * pos.buy_price, index=date_idx).where(mask, 0.0)

        total_value += pos_value
        total_cost  += pos_cost

        active = pos_value[mask]
        label  = f"{pos.ticker} ({'sold' if pos.sell_date else 'open'})"
        fig.add_trace(go.Scatter(
            x=active.index, y=active.values,
            mode="lines",
            line=dict(color=PALETTE[i % len(PALETTE)], width=1.8),
            name=label,
            hovertemplate=f"{pos.ticker}<br>%{{x|%Y-%m-%d}}<br>$%{{y:,.0f}}<extra></extra>",
        ), row=2, col=1)

    nz      = total_value[total_value > 0]
    nz_cost = total_cost[total_value > 0]
    is_up   = (nz.iloc[-1] - nz_cost.iloc[-1]) >= 0 if len(nz) else True

    fig.add_trace(go.Scatter(
        x=nz_cost.index, y=nz_cost.values,
        mode="lines",
        line=dict(color="#484f58", width=1.5, dash="dash"),
        name="Cost basis",
        hovertemplate="Cost basis: $%{y:,.0f}<extra></extra>",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=nz.index, y=nz.values,
        mode="lines",
        fill="tonexty",
        fillcolor="rgba(63,185,80,0.15)" if is_up else "rgba(248,81,73,0.15)",
        line=dict(color="#58a6ff", width=2.5),
        name="Portfolio value",
        hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.0f}<extra></extra>",
    ), row=1, col=1)

    fig.update_layout(
        **PLOTLY_BASE,
        title=dict(text="<b>Portfolio History</b>", font_size=18),
        height=680,
    )
    fig.update_xaxes(showgrid=True, gridcolor="#21262d")
    fig.update_yaxes(showgrid=True, gridcolor="#21262d", tickprefix="$", tickformat=",.0f")
    return fig


def drawdown_fig(
    positions: List[Position],
    fetch_fn: Optional[Callable] = None,
) -> Optional[go.Figure]:
    """Portfolio drawdown over time (negative % from rolling peak)."""
    from finace.metrics import portfolio_value_series, drawdown_series

    total_value, _ = portfolio_value_series(positions, fetch_fn)
    nz = total_value[total_value > 0]
    if nz.empty:
        return None

    dd      = drawdown_series(nz)
    min_idx = dd.idxmin()
    min_val = float(dd.min())

    fig = go.Figure(go.Scatter(
        x=dd.index, y=dd.values,
        mode="lines",
        fill="tozeroy",
        fillcolor="rgba(248,81,73,0.15)",
        line=dict(color="#f85149", width=1.5),
        name="Drawdown",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f}%<extra></extra>",
    ))
    fig.add_annotation(
        x=min_idx, y=min_val,
        text=f"Max DD: {min_val:.1f}%",
        font=dict(color="#f85149", size=11),
        showarrow=True, arrowcolor="#f85149",
        arrowhead=2, ax=0, ay=40,
    )
    base = {k: v for k, v in PLOTLY_BASE.items() if k not in ("xaxis", "yaxis")}
    fig.update_layout(
        **base,
        title="<b>Portfolio Drawdown</b>",
        height=280,
        showlegend=False,
    )
    fig.update_xaxes(showgrid=True, gridcolor="#21262d")
    fig.update_yaxes(showgrid=True, gridcolor="#21262d", ticksuffix="%", tickformat=".1f")
    return fig
