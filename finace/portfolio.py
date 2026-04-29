import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from typing import List, Optional

# Points to portfolio.json at the project root (one level above this package).
# Tests patch this attribute via monkeypatch to redirect to a temp file.
PORTFOLIO_FILE: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "portfolio.json")
)


@dataclass
class Position:
    id:         int
    ticker:     str
    shares:     float
    buy_price:  float
    buy_date:   str
    sell_price: Optional[float] = None
    sell_date:  Optional[str]   = None
    note:       Optional[str]   = None


def load() -> List[Position]:
    if not os.path.exists(PORTFOLIO_FILE):
        return []
    with open(PORTFOLIO_FILE) as f:
        return [Position(**p) for p in json.load(f)]


def save(positions: List[Position]) -> None:
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump([asdict(p) for p in positions], f, indent=2)


def _next_id(positions: List[Position]) -> int:
    return max((p.id for p in positions), default=0) + 1


def add_position(
    ticker: str,
    shares: float,
    buy_price: float,
    buy_date: date,
    note: Optional[str] = None,
) -> Position:
    positions = load()
    pos = Position(
        id=_next_id(positions),
        ticker=ticker.upper(),
        shares=shares,
        buy_price=buy_price,
        buy_date=buy_date.isoformat(),
        note=note,
    )
    positions.append(pos)
    save(positions)
    return pos


def sell_position(pos_id: int, sell_price: float, sell_date: date) -> Optional[Position]:
    positions = load()
    for pos in positions:
        if pos.id == pos_id:
            pos.sell_price = sell_price
            pos.sell_date  = sell_date.isoformat()
            save(positions)
            return pos
    return None


def update_position(
    pos_id:     int,
    ticker:     str,
    shares:     float,
    buy_price:  float,
    buy_date:   date,
    note:       Optional[str] = None,
    sell_price: Optional[float] = None,
    sell_date:  Optional[date]  = None,
) -> Optional[Position]:
    positions = load()
    for pos in positions:
        if pos.id == pos_id:
            pos.ticker     = ticker.upper()
            pos.shares     = shares
            pos.buy_price  = buy_price
            pos.buy_date   = buy_date.isoformat()
            pos.note       = note
            pos.sell_price = sell_price
            pos.sell_date  = sell_date.isoformat() if sell_date else None
            save(positions)
            return pos
    return None


def remove_position(pos_id: int) -> bool:
    positions = load()
    filtered  = [p for p in positions if p.id != pos_id]
    if len(filtered) == len(positions):
        return False
    save(filtered)
    return True
