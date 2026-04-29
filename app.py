"""Finance Monitor — Streamlit app."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from typing import Optional

import finace.portfolio as pf
import finace.bank as bank
import finace.charts as charts
import finace.cache as cache
import finace.metrics as metrics
from finace.calculator import compute_metrics
from finace.stock import get_current_price, get_stock_info, fetch_history

st.set_page_config(
    page_title="Finance Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Streamlit-cached fetchers ──────────────────────────────────────────────────

@st.cache_data(ttl=300)
def cached_price(ticker: str) -> Optional[float]:
    return get_current_price(ticker)


@st.cache_data(ttl=300)
def cached_info(ticker: str) -> dict:
    return get_stock_info(ticker)


@st.cache_data(ttl=60)
def cached_history(ticker: str, start: str, end: str) -> pd.Series:
    # fetch_history handles persistent SQLite caching internally;
    # the Streamlit layer just prevents redundant DB reads within one session.
    return fetch_history(ticker, start, end)


@st.cache_data(ttl=300)
def cached_fx_rate(pair: str) -> Optional[float]:
    """Return the current rate for a yfinance FX pair (e.g. 'USDTWD=X')."""
    return get_current_price(pair)


# ── Pages ──────────────────────────────────────────────────────────────────────

def page_portfolio() -> None:
    st.title("📊 Portfolio")

    positions = pf.load()
    if not positions:
        st.info("No positions yet — add one from the sidebar.")
        return

    rows = []
    total_cost = total_value = 0.0

    with st.spinner("Fetching current prices…"):
        for pos in positions:
            buy_date = date.fromisoformat(pos.buy_date)
            if pos.sell_price is not None:
                cur_price = pos.sell_price
                sell_date = date.fromisoformat(pos.sell_date) if pos.sell_date else None
                status    = "Sold"
            else:
                cur_price = cached_price(pos.ticker)
                sell_date = None
                status    = "Open"

            if cur_price is None:
                continue

            m = compute_metrics(pos.shares, pos.buy_price, buy_date, cur_price, sell_date)
            total_cost  += m["total_cost"]
            total_value += m["current_value"]
            rows.append({
                "Ticker":      pos.ticker,
                "Shares":      pos.shares,
                "Buy Price":   pos.buy_price,
                "Buy Date":    pos.buy_date,
                "Cur Price":   cur_price,
                "Total Cost":  m["total_cost"],
                "Cur Value":   m["current_value"],
                "Gain/Loss":   m["gain_loss"],
                "Return %":    m["pct_return"],
                "Ann. Return": m["cagr"],
                "Days Held":   m["days_held"],
                "Status":      status,
            })

    total_gl = total_value - total_cost
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Invested", f"${total_cost:,.2f}")
    c2.metric("Current Value",  f"${total_value:,.2f}")
    c3.metric(
        "Total P&L",
        f"${total_gl:+,.2f}",
        delta=f"{total_gl / total_cost * 100:+.2f}%" if total_cost else None,
        delta_color="normal" if total_gl >= 0 else "inverse",
    )

    st.divider()

    rows.sort(key=lambda r: r["Ticker"])
    raw = pd.DataFrame(rows).reset_index(drop=True)

    def _color_row(row):
        val    = raw.loc[row.name, "Gain/Loss"]
        color  = "color: #3fb950" if val >= 0 else "color: #f85149"
        styles = [""] * len(row)
        for col in ("Gain/Loss", "Return %", "Ann. Return"):
            if col in row.index:
                styles[row.index.get_loc(col)] = color
        return styles

    st.dataframe(
        raw.style.apply(_color_row, axis=1),
        column_config={
            "Shares":      st.column_config.NumberColumn(format="%d"),
            "Buy Price":   st.column_config.NumberColumn(format="$%.2f"),
            "Cur Price":   st.column_config.NumberColumn(format="$%.2f"),
            "Total Cost":  st.column_config.NumberColumn(format="$%.2f"),
            "Cur Value":   st.column_config.NumberColumn(format="$%.2f"),
            "Gain/Loss":   st.column_config.NumberColumn(format="$%+.2f"),
            "Return %":    st.column_config.NumberColumn(format="%+.2f%%"),
            "Ann. Return": st.column_config.NumberColumn(format="%+.2f%%"),
            "Days Held":   st.column_config.NumberColumn(format="%d"),
        },
        width="stretch",
        hide_index=True,
    )


def page_add() -> None:
    st.title("➕ Add Position")

    with st.form("add_form", clear_on_submit=True):
        ticker = st.text_input("Ticker symbol (e.g. AAPL, NVDA, BTC-USD)").strip().upper()
        col1, col2 = st.columns(2)
        with col1:
            shares    = st.number_input("Number of shares", min_value=1, step=1, format="%d")
            buy_price = st.number_input("Buy price per share ($)", min_value=0.01, step=0.01, format="%.2f")
        with col2:
            buy_date = st.date_input("Buy date", value=date.today(), max_value=date.today())
            note     = st.text_input("Note (optional)")
        submitted = st.form_submit_button("Add Position", type="primary")

    if submitted:
        if not ticker:
            st.error("Enter a ticker symbol.")
            return
        with st.spinner(f"Verifying {ticker}…"):
            cur_price = cached_price(ticker)
            info      = cached_info(ticker)
        if cur_price is None:
            st.error(f"Could not find '{ticker}'. Check the symbol and try again.")
            return

        pos = pf.add_position(ticker, shares, buy_price, buy_date, note or None)
        m   = compute_metrics(shares, buy_price, buy_date, cur_price)

        st.success(f"Position #{pos.id} added: **{info['name']}** ({ticker})")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current Price", f"${cur_price:,.2f}")
        c2.metric("Total Cost",    f"${m['total_cost']:,.2f}")
        c3.metric("Current Value", f"${m['current_value']:,.2f}")
        c4.metric(
            "Unrealised P&L",
            f"${m['gain_loss']:+,.2f}",
            delta=f"{m['pct_return']:+.2f}%",
            delta_color="normal" if m["gain_loss"] >= 0 else "inverse",
        )
        cached_price.clear()


def page_manage() -> None:
    st.title("⚙️ Manage Positions")

    positions = pf.load()
    if not positions:
        st.info("No positions to manage.")
        return

    tab_edit, tab_sell, tab_remove = st.tabs(["Edit Position", "Record Sale", "Remove Position"])

    with tab_edit:
        edit_options = {
            f"#{p.id}  {p.ticker}  —  {p.shares:g} shares @ ${p.buy_price:,.2f}  "
            f"({'sold' if p.sell_price else 'open'}, bought {p.buy_date})": p
            for p in positions
        }
        sel_e = st.selectbox("Position to edit", list(edit_options.keys()), key="edit_sel")
        pos_e = edit_options[sel_e]

        with st.form("edit_form"):
            ticker_e = st.text_input("Ticker symbol", value=pos_e.ticker).strip().upper()
            col1, col2 = st.columns(2)
            with col1:
                shares_e    = st.number_input(
                    "Number of shares", min_value=1, step=1, format="%d",
                    value=int(pos_e.shares),
                )
                buy_price_e = st.number_input(
                    "Buy price per share ($)", min_value=0.01, step=0.01, format="%.2f",
                    value=float(pos_e.buy_price),
                )
            with col2:
                buy_date_e = st.date_input(
                    "Buy date",
                    value=date.fromisoformat(pos_e.buy_date),
                    max_value=date.today(),
                    key="edit_buy_date",
                )
                note_e = st.text_input("Note (optional)", value=pos_e.note or "")

            sold_e = pos_e.sell_price is not None
            st.checkbox("Position is sold", value=sold_e, key="edit_sold_check", disabled=True)
            if sold_e:
                col3, col4 = st.columns(2)
                with col3:
                    sell_price_e = st.number_input(
                        "Sell price per share ($)", min_value=0.01, step=0.01, format="%.2f",
                        value=float(pos_e.sell_price),
                    )
                with col4:
                    sell_date_e = st.date_input(
                        "Sell date",
                        value=date.fromisoformat(pos_e.sell_date) if pos_e.sell_date else date.today(),
                        max_value=date.today(),
                        key="edit_sell_date",
                    )
            else:
                sell_price_e = None
                sell_date_e  = None

            submitted_e = st.form_submit_button("Save Changes", type="primary")

        if submitted_e:
            if not ticker_e:
                st.error("Ticker symbol cannot be empty.")
            else:
                pf.update_position(
                    pos_e.id, ticker_e, shares_e, buy_price_e, buy_date_e,
                    note_e or None, sell_price_e, sell_date_e,
                )
                st.success(f"Position #{pos_e.id} updated.")
                cached_price.clear()
                st.rerun()

    with tab_sell:
        open_pos = [p for p in positions if p.sell_price is None]
        if not open_pos:
            st.info("No open positions.")
        else:
            options = {
                f"#{p.id}  {p.ticker}  —  {p.shares:g} shares @ ${p.buy_price:,.2f}  (bought {p.buy_date})": p
                for p in open_pos
            }
            sel = st.selectbox("Position to close", list(options.keys()))
            pos = options[sel]

            with st.form("sell_form"):
                col1, col2 = st.columns(2)
                with col1:
                    sell_price = st.number_input(
                        "Sell price per share ($)",
                        min_value=0.01, value=float(pos.buy_price),
                        step=0.01, format="%.2f",
                    )
                with col2:
                    sell_date = st.date_input("Sell date", value=date.today(), max_value=date.today())
                submitted = st.form_submit_button("Record Sale", type="primary")

            if submitted:
                pf.sell_position(pos.id, sell_price, sell_date)
                m = compute_metrics(
                    pos.shares, pos.buy_price,
                    date.fromisoformat(pos.buy_date),
                    sell_price, sell_date,
                )
                st.success(f"Position #{pos.id} ({pos.ticker}) closed.")
                c1, c2, c3 = st.columns(3)
                c1.metric(
                    "Realised P&L", f"${m['gain_loss']:+,.2f}",
                    delta=f"{m['pct_return']:+.2f}%",
                    delta_color="normal" if m["gain_loss"] >= 0 else "inverse",
                )
                c2.metric("Ann. Return", f"{m['cagr']:+.2f}%")
                c3.metric("Days Held",   str(m["days_held"]))
                cached_price.clear()

    with tab_remove:
        options_r = {
            f"#{p.id}  {p.ticker}  ({'sold' if p.sell_price else 'open'})  bought {p.buy_date}": p
            for p in positions
        }
        sel_r = st.selectbox("Position to remove", list(options_r.keys()), key="rm_sel")
        pos_r = options_r[sel_r]

        if st.button("Remove Position", type="primary"):
            pf.remove_position(pos_r.id)
            st.success(f"Position #{pos_r.id} ({pos_r.ticker}) removed.")
            st.rerun()


def page_charts() -> None:
    st.title("📈 Charts")

    positions = pf.load()
    if not positions:
        st.info("No positions yet.")
        return

    view = st.radio("View", ["Total Portfolio", "Single Position"], horizontal=True)

    if view == "Total Portfolio":
        with st.spinner("Fetching historical data…"):
            fig = charts.portfolio_fig(positions, fetch_fn=cached_history)
        if fig:
            st.plotly_chart(fig, width="stretch")
        else:
            st.error("Could not build chart.")
    else:
        options = {
            f"#{p.id}  {p.ticker}  —  {p.shares:g} shares  {'[sold]' if p.sell_price else '[open]'}": p
            for p in positions
        }
        sel = st.selectbox("Position", list(options.keys()))
        pos = options[sel]
        with st.spinner(f"Fetching history for {pos.ticker}…"):
            fig = charts.position_fig(pos, fetch_fn=cached_history)
        if fig:
            st.plotly_chart(fig, width="stretch")
        else:
            st.error(f"No historical data for {pos.ticker}.")


def page_performance() -> None:
    st.title("📉 Performance")

    positions = pf.load()
    if not positions:
        st.info("No positions yet — add one from the sidebar.")
        return

    with st.spinner("Computing metrics…"):
        total_value, total_cost = metrics.portfolio_value_series(positions, fetch_fn=cached_history)
        nz = total_value[total_value > 0]

    if nz.empty:
        st.error("Not enough price history to compute metrics.")
        return

    # ── Portfolio-level KPIs ───────────────────────────────────────────────────
    closed_gains = [
        (p.sell_price - p.buy_price) * p.shares
        for p in positions if p.sell_price is not None
    ]
    vol    = metrics.annualized_volatility(nz)
    mdd    = metrics.max_drawdown(nz)
    sharpe = metrics.sharpe_ratio(nz)
    sortino = metrics.sortino_ratio(nz)
    wr     = metrics.win_rate(closed_gains)

    # CAGR for Calmar: compare current value to total cost at each point in time
    nz_cost    = total_cost[total_value > 0]
    years_held = max((nz.index[-1] - nz.index[0]).days / 365.25, 1 / 365.25)
    final_val  = float(nz.iloc[-1])
    peak_cost  = float(nz_cost.max()) if not nz_cost.empty and nz_cost.max() > 0 else 1.0
    port_cagr  = ((final_val / peak_cost) ** (1.0 / years_held) - 1) * 100
    calmar     = metrics.calmar_ratio(port_cagr, mdd)

    spy_start = nz.index[0].date().isoformat()
    spy_end   = (nz.index[-1].date() + timedelta(days=1)).isoformat()
    with st.spinner("Fetching SPY for Beta…"):
        spy_hist = cached_history("SPY", spy_start, spy_end)

    port_beta = metrics.beta(nz, spy_hist) if not spy_hist.empty else None

    st.subheader("Portfolio Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Volatility (ann.)", f"{vol:.2f}%")
    c2.metric("Max Drawdown",      f"{mdd:.2f}%")
    c3.metric("Sharpe Ratio",      f"{sharpe:.2f}")

    sortino_display = f"{sortino:.2f}" if sortino != float("inf") else "∞"
    c4.metric("Sortino Ratio", sortino_display)

    c5, c6, c7 = st.columns(3)
    c5.metric("Beta (vs SPY)", f"{port_beta:.2f}" if port_beta is not None else "N/A")
    c6.metric("Calmar Ratio",  f"{calmar:.2f}")
    c7.metric("Win Rate",      f"{wr:.1f}%" if closed_gains else "N/A (no closed positions)")

    st.divider()

    # ── Drawdown chart ─────────────────────────────────────────────────────────
    dd_fig = charts.drawdown_fig(positions, fetch_fn=cached_history)
    if dd_fig:
        st.plotly_chart(dd_fig, width="stretch")

    st.divider()

    # ── Per-position risk table ────────────────────────────────────────────────
    st.subheader("Per-Position Risk Metrics")

    rows = []
    for pos in positions:
        end_date = date.fromisoformat(pos.sell_date) if pos.sell_date else date.today()
        ph = cached_history(
            pos.ticker, pos.buy_date,
            (end_date + timedelta(days=1)).isoformat(),
        )
        if ph.empty or len(ph) < 2:
            continue
        sr = metrics.sortino_ratio(ph)
        rows.append({
            "Ticker":     pos.ticker,
            "Status":     "Sold" if pos.sell_price else "Open",
            "Volatility": f"{metrics.annualized_volatility(ph):.2f}%",
            "Max DD":     f"{metrics.max_drawdown(ph):.2f}%",
            "Sharpe":     f"{metrics.sharpe_ratio(ph):.2f}",
            "Sortino":    f"{sr:.2f}" if sr != float("inf") else "∞",
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True)
    else:
        st.info("Not enough history for per-position metrics.")


def page_lookup() -> None:
    st.title("🔍 Price Lookup")

    ticker = st.text_input("Ticker symbol").strip().upper()
    if not ticker:
        return

    with st.spinner(f"Fetching {ticker}…"):
        price = cached_price(ticker)
        info  = cached_info(ticker)

    if price is None:
        st.error(f"Could not find '{ticker}'.")
        return

    st.subheader(f"{info['name']}  ({ticker})")
    c1, c2 = st.columns(2)
    c1.metric("Current Price", f"${price:,.2f} {info['currency']}")
    c2.metric("Exchange", info["exchange"] or "—")

    one_yr_ago = (date.today() - timedelta(days=365)).isoformat()
    tomorrow   = (date.today() + timedelta(days=1)).isoformat()
    with st.spinner("Loading 1-year chart…"):
        hist = cached_history(ticker, one_yr_ago, tomorrow)

    if not hist.empty:
        is_up = price >= float(hist.iloc[0])
        color = "#3fb950" if is_up else "#f85149"
        fig   = go.Figure(go.Scatter(
            x=hist.index, y=hist.values,
            mode="lines",
            line=dict(color=color, width=2),
            fill="tozeroy",
            fillcolor=f"rgba({'63,185,80' if is_up else '248,81,73'},0.08)",
            hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            **charts.PLOTLY_BASE,
            title=f"{ticker} — 1 Year",
            height=340,
            showlegend=False,
        )
        st.plotly_chart(fig, width="stretch")


# ── Overview page ─────────────────────────────────────────────────────────────

def page_overview() -> None:
    st.title("📋 Overview")
    st.caption("All values converted to TWD (NT$)")

    with st.spinner("Fetching exchange rates…"):
        usd_twd = cached_fx_rate("USDTWD=X")
        jpy_twd = cached_fx_rate("JPYTWD=X")

    if usd_twd is None:
        st.error("Could not fetch USD/TWD exchange rate. Check your connection.")
        return
    if jpy_twd is None:
        st.error("Could not fetch JPY/TWD exchange rate. Check your connection.")
        return

    def to_twd(amount: float, currency: str) -> float:
        if currency == "TWD": return amount
        if currency == "USD": return amount * usd_twd
        if currency == "JPY": return amount * jpy_twd
        return 0.0

    # ── Stock portfolio (open positions only, grouped by ticker) ──────────────
    positions = pf.load()
    open_pos  = [p for p in positions if p.sell_price is None]

    ticker_shares: dict = {}
    ticker_price:  dict = {}
    with st.spinner("Fetching stock prices…"):
        for pos in open_pos:
            price = cached_price(pos.ticker)
            if price is None:
                continue
            ticker_shares[pos.ticker] = ticker_shares.get(pos.ticker, 0) + int(pos.shares)
            ticker_price[pos.ticker]  = price

    stock_twd          = 0.0
    stock_rows         = []
    stock_chart_labels = []
    stock_chart_values = []
    for ticker in sorted(ticker_shares):
        price     = ticker_price[ticker]
        shares    = ticker_shares[ticker]
        value_usd = price * shares
        value_twd = to_twd(value_usd, "USD")
        stock_twd += value_twd
        stock_chart_labels.append(ticker)
        stock_chart_values.append(value_twd)
        stock_rows.append({
            "Ticker":      ticker,
            "Shares":      shares,
            "Price (USD)": f"${price:,.2f}",
            "Value (USD)": f"${value_usd:,.2f}",
            "Value (TWD)": f"NT${value_twd:,.0f}",
        })

    # ── Bank accounts ──────────────────────────────────────────────────────────
    accounts, transactions = bank.load()
    bank_twd          = 0.0
    bank_rows         = []
    bank_chart_labels = []
    bank_chart_values = []

    for a in sorted(accounts, key=lambda a: a.name):
        bal     = bank.current_balance(a.id, transactions, a.initial_balance)
        bal_twd = to_twd(bal, a.currency)
        bank_twd += bal_twd
        bank_chart_labels.append(a.name)
        bank_chart_values.append(bal_twd)
        bank_rows.append({
            "Account":     a.name,
            "Type":        a.account_type,
            "Balance":     f"{bal:,.2f} {a.currency}",
            "Value (TWD)": f"NT${bal_twd:,.0f}",
        })

    total_twd = stock_twd + bank_twd

    # ── Summary KPIs ───────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Net Worth", f"NT${total_twd:,.0f}")
    c2.metric("Stock Portfolio", f"NT${stock_twd:,.0f}")
    c3.metric("Bank Accounts",   f"NT${bank_twd:,.0f}")
    st.caption(f"Exchange rates — USD/TWD: {usd_twd:.2f}  |  JPY/TWD: {jpy_twd:.4f}")
    st.divider()

    # ── Donut charts ───────────────────────────────────────────────────────────
    def _donut(labels, values, title, colors=None):
        if not values or sum(v for v in values if v > 0) == 0:
            return None
        base = {k: v for k, v in charts.PLOTLY_BASE.items()
                if k not in ("xaxis", "yaxis", "hovermode")}
        fig = go.Figure(go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            textinfo="label+percent",
            hovertemplate="%{label}<br>NT$%{value:,.0f}<br>%{percent}<extra></extra>",
            marker=dict(colors=colors or charts.PALETTE[:len(labels)]),
        ))
        fig.update_layout(
            **base,
            title=dict(text=f"<b>{title}</b>", font_size=13, x=0.5),
            height=300,
            showlegend=True,
            margin=dict(t=50, b=10, l=10, r=10),
        )
        return fig

    ch1, ch2, ch3 = st.columns(3)

    with ch1:
        fig = _donut(
            ["Stocks", "Banking"], [stock_twd, bank_twd],
            "Stocks vs Banking", colors=["#58a6ff", "#3fb950"],
        )
        st.plotly_chart(fig, width="stretch") if fig else st.info("No data yet.")

    with ch2:
        fig = _donut(stock_chart_labels, stock_chart_values, "By Stock")
        st.plotly_chart(fig, width="stretch") if fig else st.info("No open positions.")

    with ch3:
        fig = _donut(bank_chart_labels, bank_chart_values, "By Account")
        st.plotly_chart(fig, width="stretch") if fig else st.info("No bank accounts.")

    st.divider()

    # ── Stock breakdown table ──────────────────────────────────────────────────
    st.subheader("📈 Stock Portfolio")
    if stock_rows:
        st.dataframe(
            pd.DataFrame(stock_rows),
            column_config={"Shares": st.column_config.NumberColumn(format="%d")},
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No open stock positions.")

    st.divider()

    # ── Bank breakdown table ───────────────────────────────────────────────────
    st.subheader("🏦 Bank Accounts")
    if bank_rows:
        st.dataframe(pd.DataFrame(bank_rows), hide_index=True, width="stretch")
    else:
        st.info("No bank accounts.")


# ── Bank pages ────────────────────────────────────────────────────────────────

def page_bank_accounts() -> None:
    st.title("🏦 Bank Accounts")

    accounts, transactions = bank.load()
    if not accounts:
        st.info("No accounts yet — add one from the sidebar.")
        return

    rows = []
    total_usd = 0.0
    for a in sorted(accounts, key=lambda a: a.name):
        bal = bank.current_balance(a.id, transactions, a.initial_balance)
        if a.currency == "USD":
            total_usd += bal
        rows.append({
            "Account":  a.name,
            "Type":     a.account_type,
            "Balance":  bal,
            "Currency": a.currency,
            "Note":     a.note or "",
        })

    st.metric("Total Balance (USD accounts)", f"${total_usd:,.2f}")
    st.divider()
    st.dataframe(
        pd.DataFrame(rows),
        column_config={
            "Balance": st.column_config.NumberColumn(format="$%.2f"),
        },
        hide_index=True,
        width="stretch",
    )


def page_bank_add_account() -> None:
    st.title("➕ Add Bank Account")

    with st.form("add_account_form", clear_on_submit=True):
        name = st.text_input("Account name (e.g. Chase Checking)")
        col1, col2 = st.columns(2)
        with col1:
            account_type    = st.selectbox("Account type", bank.ACCOUNT_TYPES)
            initial_balance = st.number_input(
                "Opening balance ($)", min_value=0.0, step=0.01, format="%.2f"
            )
        with col2:
            currency = st.selectbox("Currency", bank.CURRENCIES)
            note     = st.text_input("Note (optional)")
        submitted = st.form_submit_button("Add Account", type="primary")

    if submitted:
        if not name.strip():
            st.error("Account name cannot be empty.")
            return
        a = bank.add_account(name.strip(), account_type, initial_balance, currency, note or None)
        st.success(f"Account #{a.id} '{a.name}' added with opening balance ${initial_balance:,.2f}.")


def page_bank_transactions() -> None:
    st.title("💸 Transactions")

    accounts, transactions = bank.load()
    if not accounts:
        st.info("No accounts yet — add one first.")
        return

    options = {f"#{a.id}  {a.name}  ({a.account_type})": a for a in accounts}
    sel  = st.selectbox("Account", list(options.keys()))
    acct = options[sel]

    acct_txs    = [t for t in transactions if t.account_id == acct.id]
    bal          = bank.current_balance(acct.id, transactions, acct.initial_balance)
    deposits     = sum(t.amount for t in acct_txs if t.type == "deposit")
    withdrawals  = sum(t.amount for t in acct_txs if t.type == "withdrawal")

    c1, c2, c3 = st.columns(3)
    c1.metric("Current Balance",  f"${bal:,.2f} {acct.currency}")
    c2.metric("Total Deposited",  f"${deposits:,.2f}")
    c3.metric("Total Withdrawn",  f"${withdrawals:,.2f}")

    st.divider()

    with st.form("add_tx_form", clear_on_submit=True):
        st.subheader("Record Transaction")
        col1, col2 = st.columns(2)
        with col1:
            tx_type = st.radio("Type", ["Deposit", "Withdrawal"], horizontal=True)
            amount  = st.number_input("Amount ($)", min_value=0.01, step=0.01, format="%.2f")
        with col2:
            tx_date     = st.date_input("Date", value=date.today(), max_value=date.today())
            description = st.text_input("Description (optional)")
        add_tx = st.form_submit_button("Record", type="primary")

    if add_tx:
        if tx_type == "Withdrawal" and amount > bal:
            st.warning(f"This withdrawal exceeds the current balance (${bal:,.2f}).")
        bank.add_transaction(acct.id, tx_type.lower(), amount, tx_date, description or None)
        st.success(f"{tx_type} of ${amount:,.2f} recorded.")
        st.rerun()

    st.divider()
    st.subheader("Transaction History")

    if not acct_txs:
        st.info("No transactions yet.")
    else:
        rows = []
        for t in sorted(acct_txs, key=lambda t: t.date, reverse=True):
            rows.append({
                "Date":        t.date,
                "Type":        t.type.capitalize(),
                "Amount":      t.amount if t.type == "deposit" else -t.amount,
                "Description": t.description or "",
            })

        df = pd.DataFrame(rows)

        def _color_tx(row):
            return ["color: #3fb950" if col == "Amount" and row["Amount"] >= 0
                    else "color: #f85149" if col == "Amount"
                    else "" for col in row.index]

        st.dataframe(
            df.style.apply(_color_tx, axis=1),
            column_config={
                "Amount": st.column_config.NumberColumn(format="$%+.2f"),
            },
            hide_index=True,
            width="stretch",
        )


def page_bank_manage() -> None:
    st.title("⚙️ Manage Bank Accounts")

    accounts, transactions = bank.load()
    if not accounts:
        st.info("No accounts to manage.")
        return

    tab_edit, tab_remove_acct, tab_remove_tx = st.tabs(
        ["Edit Account", "Remove Account", "Remove Transaction"]
    )

    with tab_edit:
        opts = {f"#{a.id}  {a.name}  ({a.account_type})": a for a in accounts}
        sel_e = st.selectbox("Account to edit", list(opts.keys()), key="edit_acct_sel")
        acct_e = opts[sel_e]

        with st.form("edit_acct_form"):
            name_e     = st.text_input("Account name", value=acct_e.name)
            col1, col2 = st.columns(2)
            with col1:
                type_idx = bank.ACCOUNT_TYPES.index(acct_e.account_type) if acct_e.account_type in bank.ACCOUNT_TYPES else 0
                type_e   = st.selectbox("Account type", bank.ACCOUNT_TYPES, index=type_idx)
                init_e   = st.number_input(
                    "Opening balance ($)", min_value=0.0, step=0.01, format="%.2f",
                    value=float(acct_e.initial_balance),
                )
            with col2:
                curr_idx = bank.CURRENCIES.index(acct_e.currency) if acct_e.currency in bank.CURRENCIES else 0
                curr_e   = st.selectbox("Currency", bank.CURRENCIES, index=curr_idx)
                note_e   = st.text_input("Note (optional)", value=acct_e.note or "")
            submitted_e = st.form_submit_button("Save Changes", type="primary")

        if submitted_e:
            if not name_e.strip():
                st.error("Account name cannot be empty.")
            else:
                bank.update_account(acct_e.id, name_e.strip(), type_e, init_e, curr_e, note_e or None)
                st.success(f"Account #{acct_e.id} updated.")
                st.rerun()

    with tab_remove_acct:
        opts_r = {f"#{a.id}  {a.name}  ({a.account_type})": a for a in accounts}
        sel_r  = st.selectbox("Account to remove", list(opts_r.keys()), key="rm_acct_sel")
        acct_r = opts_r[sel_r]

        tx_count = sum(1 for t in transactions if t.account_id == acct_r.id)
        if tx_count:
            st.warning(f"Removing this account will also delete {tx_count} transaction(s).")

        if st.button("Remove Account", type="primary", key="rm_acct_btn"):
            bank.remove_account(acct_r.id)
            st.success(f"Account '{acct_r.name}' removed.")
            st.rerun()

    with tab_remove_tx:
        opts_ta = {f"#{a.id}  {a.name}": a for a in accounts}
        sel_ta  = st.selectbox("Account", list(opts_ta.keys()), key="rm_tx_acct_sel")
        acct_ta = opts_ta[sel_ta]

        acct_txs = sorted(
            [t for t in transactions if t.account_id == acct_ta.id],
            key=lambda t: t.date, reverse=True,
        )
        if not acct_txs:
            st.info("No transactions for this account.")
        else:
            tx_opts = {
                f"#{t.id}  {t.date}  {t.type.capitalize()}  ${t.amount:,.2f}"
                + (f"  — {t.description}" if t.description else ""): t
                for t in acct_txs
            }
            sel_tx = st.selectbox("Transaction to remove", list(tx_opts.keys()), key="rm_tx_sel")
            tx_r   = tx_opts[sel_tx]

            if st.button("Remove Transaction", type="primary", key="rm_tx_btn"):
                bank.remove_transaction(tx_r.id)
                st.success(f"Transaction #{tx_r.id} removed.")
                st.rerun()


# ── Sidebar & routing ──────────────────────────────────────────────────────────

STOCK_PAGES = {
    "📊  Portfolio":    page_portfolio,
    "➕  Add Position": page_add,
    "⚙️  Manage":       page_manage,
    "📈  Charts":       page_charts,
    "📉  Performance":  page_performance,
    "🔍  Price Lookup": page_lookup,
}

BANK_PAGES = {
    "🏦  Accounts":     page_bank_accounts,
    "➕  Add Account":  page_bank_add_account,
    "💸  Transactions": page_bank_transactions,
    "⚙️  Manage":       page_bank_manage,
}

with st.sidebar:
    st.markdown("## Finance Monitor")
    st.divider()
    category = st.radio(
        "Category",
        ["📋  Overview", "📈  Stocks", "🏦  Banking"],
        label_visibility="collapsed",
        key="nav_category",
    )
    st.divider()
    if "Overview" in category:
        active_fn = page_overview
    elif "Stocks" in category:
        page = st.radio("Page", list(STOCK_PAGES.keys()), label_visibility="collapsed", key="nav_stock")
        active_fn = STOCK_PAGES[page]
    else:
        page = st.radio("Page", list(BANK_PAGES.keys()), label_visibility="collapsed", key="nav_bank")
        active_fn = BANK_PAGES[page]
    st.divider()
    st.caption("Prices delayed ~15 min. Not financial advice.")

active_fn()
