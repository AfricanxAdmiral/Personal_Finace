from datetime import date
from typing import Optional


def compute_metrics(
    shares: float,
    buy_price: float,
    buy_date: date,
    current_price: float,
    sell_date: Optional[date] = None,
) -> dict:
    end_date = sell_date or date.today()
    days_held = max((end_date - buy_date).days, 1)

    total_cost    = shares * buy_price
    current_value = shares * current_price
    gain_loss     = current_value - total_cost
    pct_return    = (gain_loss / total_cost * 100) if total_cost else 0.0

    years = days_held / 365.25
    if total_cost > 0 and current_value > 0:
        cagr = ((current_value / total_cost) ** (1.0 / years) - 1) * 100
    else:
        cagr = 0.0

    return {
        "total_cost":    total_cost,
        "current_value": current_value,
        "gain_loss":     gain_loss,
        "pct_return":    pct_return,
        "cagr":          cagr,
        "days_held":     days_held,
        "years_held":    years,
    }
