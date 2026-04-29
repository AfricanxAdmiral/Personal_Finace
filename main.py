#!/usr/bin/env python3
import sys
from datetime import date, datetime
from typing import Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

import finace.portfolio as pf
from finace.calculator import compute_metrics
from finace.stock import get_current_price, get_stock_info

console = Console()


def parse_date(s: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def colored(value: float, fmt: str = "+.2f") -> Text:
    color = "green" if value >= 0 else "red"
    sign = "+" if value >= 0 else ""
    return Text(f"{sign}{value:{fmt.lstrip('+')}}", style=color)


# ── Views ──────────────────────────────────────────────────────────────────────

def view_portfolio() -> None:
    positions = pf.load()
    if not positions:
        console.print("[yellow]Portfolio is empty. Add a position first.[/yellow]")
        return

    table = Table(
        title="[bold cyan]Stock Portfolio[/bold cyan]",
        box=box.ROUNDED,
        header_style="bold white on dark_blue",
        show_lines=True,
        expand=True,
    )
    for col, kw in [
        ("ID",          dict(justify="right", style="dim", no_wrap=True)),
        ("Ticker",      dict(style="bold yellow", no_wrap=True)),
        ("Shares",      dict(justify="right")),
        ("Buy Price",   dict(justify="right")),
        ("Buy Date",    dict(justify="center", no_wrap=True)),
        ("Price Now",   dict(justify="right")),
        ("Total Cost",  dict(justify="right")),
        ("Cur Value",   dict(justify="right")),
        ("Gain / Loss", dict(justify="right")),
        ("Return %",    dict(justify="right")),
        ("Ann. Return", dict(justify="right")),
        ("Days Held",   dict(justify="right")),
        ("Status",      dict(justify="center")),
    ]:
        table.add_column(col, **kw)

    total_cost = total_value = 0.0

    for pos in positions:
        buy_date = date.fromisoformat(pos.buy_date)

        if pos.sell_price is not None:
            cur_price = pos.sell_price
            sell_date = date.fromisoformat(pos.sell_date) if pos.sell_date else None
            status = Text("SOLD", style="dim")
            price_str = f"${cur_price:,.2f}"
        else:
            with console.status(f"[dim]Fetching {pos.ticker}…[/dim]", spinner="dots"):
                cur_price = get_current_price(pos.ticker)
            sell_date = None
            status = Text("OPEN", style="bold green")
            price_str = f"${cur_price:,.2f}" if cur_price is not None else "[red]N/A[/red]"

        if cur_price is None:
            console.print(f"[red]Could not fetch price for {pos.ticker}[/red]")
            continue

        m = compute_metrics(pos.shares, pos.buy_price, buy_date, cur_price, sell_date)
        total_cost  += m["total_cost"]
        total_value += m["current_value"]

        table.add_row(
            str(pos.id),
            pos.ticker,
            f"{pos.shares:,.4f}".rstrip("0").rstrip("."),
            f"${pos.buy_price:,.2f}",
            pos.buy_date,
            price_str,
            f"${m['total_cost']:,.2f}",
            f"${m['current_value']:,.2f}",
            colored(m["gain_loss"], "+,.2f"),
            colored(m["pct_return"], "+.2f"),
            colored(m["cagr"], "+.2f"),
            f"{m['days_held']:,}",
            status,
        )

    console.print(table)

    total_gl = total_value - total_cost
    gl_color = "green" if total_gl >= 0 else "red"
    console.print(
        f"\n  Total invested: [bold]${total_cost:,.2f}[/bold]   "
        f"Current value: [bold]${total_value:,.2f}[/bold]   "
        f"P&L: [{gl_color}][bold]${total_gl:+,.2f}[/bold][/{gl_color}]"
    )


# ── Actions ────────────────────────────────────────────────────────────────────

def add_stock() -> None:
    console.print(Panel("[bold]Add Position[/bold]", border_style="cyan", width=40))

    ticker = Prompt.ask("Ticker symbol").strip().upper()
    if not ticker:
        return

    with console.status(f"Verifying [bold]{ticker}[/bold]…", spinner="dots"):
        cur_price = get_current_price(ticker)
        info = get_stock_info(ticker)

    if cur_price is None:
        console.print(f"[red]Could not find '{ticker}'. Check the symbol and try again.[/red]")
        return

    console.print(
        f"  [green]✓[/green] {info['name']}  |  "
        f"Current price: [bold]${cur_price:,.2f}[/bold] {info['currency']}"
    )

    try:
        shares    = float(Prompt.ask("Number of shares"))
        buy_price = float(Prompt.ask("Buy price per share ($)"))
    except ValueError:
        console.print("[red]Invalid number.[/red]")
        return

    buy_date_str = Prompt.ask("Buy date", default=date.today().isoformat())
    buy_date = parse_date(buy_date_str)
    if not buy_date:
        console.print("[red]Invalid date. Use YYYY-MM-DD.[/red]")
        return

    note = Prompt.ask("Note (optional)", default="") or None

    pos = pf.add_position(ticker, shares, buy_price, buy_date, note)
    console.print(f"[green]Position #{pos.id} added.[/green]")

    # Preview metrics immediately
    m = compute_metrics(shares, buy_price, buy_date, cur_price)
    gl_color = "green" if m["gain_loss"] >= 0 else "red"
    console.print(
        f"  Unrealised P&L: [{gl_color}][bold]${m['gain_loss']:+,.2f}[/bold][/{gl_color}]  "
        f"({m['pct_return']:+.2f}%)   Ann. return: {m['cagr']:+.2f}%"
    )


def record_sale() -> None:
    console.print(Panel("[bold]Record Sale[/bold]", border_style="cyan", width=40))

    positions = pf.load()
    open_pos   = [p for p in positions if p.sell_price is None]
    if not open_pos:
        console.print("[yellow]No open positions.[/yellow]")
        return

    console.print("Open positions:")
    for p in open_pos:
        console.print(f"  [bold]{p.id}[/bold]  {p.ticker}  {p.shares} shares @ ${p.buy_price}  (bought {p.buy_date})")

    try:
        pos_id     = int(Prompt.ask("Position ID to close"))
        sell_price = float(Prompt.ask("Sell price per share ($)"))
    except ValueError:
        console.print("[red]Invalid input.[/red]")
        return

    sell_date_str = Prompt.ask("Sell date", default=date.today().isoformat())
    sell_date = parse_date(sell_date_str)
    if not sell_date:
        console.print("[red]Invalid date.[/red]")
        return

    pos = pf.sell_position(pos_id, sell_price, sell_date)
    if not pos:
        console.print("[red]Position not found.[/red]")
        return

    buy_date = date.fromisoformat(pos.buy_date)
    m = compute_metrics(pos.shares, pos.buy_price, buy_date, sell_price, sell_date)
    gl_color = "green" if m["gain_loss"] >= 0 else "red"
    console.print(
        f"[green]Position #{pos_id} closed.[/green]\n"
        f"  Realised P&L:  [{gl_color}][bold]${m['gain_loss']:+,.2f}[/bold][/{gl_color}]  "
        f"({m['pct_return']:+.2f}%)\n"
        f"  Ann. return:   {m['cagr']:+.2f}%  over {m['days_held']} days"
    )


def remove_stock() -> None:
    try:
        pos_id = int(Prompt.ask("Position ID to remove"))
    except ValueError:
        console.print("[red]Invalid ID.[/red]")
        return

    if Confirm.ask(f"Permanently remove position #{pos_id}?"):
        if pf.remove_position(pos_id):
            console.print(f"[green]Position #{pos_id} removed.[/green]")
        else:
            console.print("[red]Position not found.[/red]")


def view_chart() -> None:
    positions = pf.load()
    if not positions:
        console.print("[yellow]Portfolio is empty.[/yellow]")
        return

    console.print("  [bold cyan]p[/bold cyan]  Total portfolio chart")
    for pos in positions:
        status = "sold" if pos.sell_price else "open"
        console.print(f"  [bold cyan]{pos.id}[/bold cyan]  {pos.ticker}  {pos.shares:g} shares  ({status})")

    choice = Prompt.ask("Choice (p or position ID)").strip().lower()

    if choice == "p":
        from finace.charts import portfolio_fig
        with console.status("Fetching historical data…", spinner="dots"):
            fig = portfolio_fig(positions)
        if fig:
            fig.show()
        else:
            console.print("[red]Could not build chart.[/red]")
    else:
        try:
            pos_id = int(choice)
        except ValueError:
            console.print("[red]Invalid choice.[/red]")
            return
        pos = next((p for p in positions if p.id == pos_id), None)
        if pos is None:
            console.print("[red]Position not found.[/red]")
            return
        from finace.charts import position_fig
        with console.status(f"Fetching history for {pos.ticker}…", spinner="dots"):
            fig = position_fig(pos)
        if fig:
            fig.show()
        else:
            console.print("[red]No historical data available.[/red]")


def quick_lookup() -> None:
    ticker = Prompt.ask("Ticker symbol").strip().upper()
    with console.status(f"Fetching [bold]{ticker}[/bold]…", spinner="dots"):
        price = get_current_price(ticker)
        info  = get_stock_info(ticker)
    if price is None:
        console.print(f"[red]Could not find '{ticker}'.[/red]")
    else:
        console.print(
            f"  [bold]{ticker}[/bold]  {info['name']}\n"
            f"  Price: [bold cyan]${price:,.2f}[/bold cyan] {info['currency']}  ({info['exchange']})"
        )


# ── Main loop ──────────────────────────────────────────────────────────────────

MENU = [
    ("1", "View portfolio",          view_portfolio),
    ("2", "Add position",            add_stock),
    ("3", "Record sale",             record_sale),
    ("4", "Remove position",         remove_stock),
    ("5", "Quick price lookup",      quick_lookup),
    ("6", "View chart",              view_chart),
    ("q", "Quit",                    None),
]


def main() -> None:
    console.print(Panel(
        "[bold cyan]Finance Monitor[/bold cyan]\n[dim]Stock Portfolio Tracker[/dim]",
        border_style="cyan",
        width=36,
        padding=(1, 4),
    ))

    while True:
        console.print()
        for key, label, _ in MENU:
            console.print(f"  [bold cyan]{key}[/bold cyan]  {label}")

        choice = Prompt.ask("\nChoice").strip().lower()
        console.print()

        if choice == "q":
            console.print("[dim]Bye![/dim]")
            sys.exit(0)

        for key, _, fn in MENU:
            if choice == key and fn:
                fn()
                break
        else:
            console.print("[red]Invalid choice.[/red]")


if __name__ == "__main__":
    main()
