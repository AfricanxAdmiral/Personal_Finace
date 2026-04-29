"""Bank account management — multiple accounts with deposit/withdrawal tracking."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from typing import List, Optional, Tuple

BANK_FILE: str = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bank.json")
)

ACCOUNT_TYPES = ["Checking", "Savings", "Money Market", "CD", "Other"]
CURRENCIES    = ["USD", "TWD", "JPY"]


@dataclass
class Account:
    id:              int
    name:            str
    account_type:    str
    initial_balance: float
    currency:        str           = "USD"
    note:            Optional[str] = None


@dataclass
class Transaction:
    id:          int
    account_id:  int
    type:        str            # "deposit" | "withdrawal"
    amount:      float
    date:        str            # ISO-8601
    description: Optional[str] = None


# ── I/O ────────────────────────────────────────────────────────────────────────

def _load_raw() -> dict:
    if not os.path.exists(BANK_FILE):
        return {"accounts": [], "transactions": []}
    with open(BANK_FILE) as f:
        return json.load(f)


def _save(accounts: List[Account], transactions: List[Transaction]) -> None:
    with open(BANK_FILE, "w") as f:
        json.dump(
            {
                "accounts":     [asdict(a) for a in accounts],
                "transactions": [asdict(t) for t in transactions],
            },
            f, indent=2,
        )


def load() -> Tuple[List[Account], List[Transaction]]:
    raw = _load_raw()
    return (
        [Account(**a) for a in raw["accounts"]],
        [Transaction(**t) for t in raw["transactions"]],
    )


# ── ID helpers ─────────────────────────────────────────────────────────────────

def _next_account_id(accounts: List[Account]) -> int:
    return max((a.id for a in accounts), default=0) + 1


def _next_tx_id(transactions: List[Transaction]) -> int:
    return max((t.id for t in transactions), default=0) + 1


# ── Account CRUD ───────────────────────────────────────────────────────────────

def add_account(
    name:            str,
    account_type:    str,
    initial_balance: float,
    currency:        str           = "USD",
    note:            Optional[str] = None,
) -> Account:
    accounts, transactions = load()
    account = Account(
        id=_next_account_id(accounts),
        name=name,
        account_type=account_type,
        initial_balance=initial_balance,
        currency=currency,
        note=note,
    )
    accounts.append(account)
    _save(accounts, transactions)
    return account


def update_account(
    account_id:      int,
    name:            str,
    account_type:    str,
    initial_balance: float,
    currency:        str,
    note:            Optional[str] = None,
) -> Optional[Account]:
    accounts, transactions = load()
    for a in accounts:
        if a.id == account_id:
            a.name            = name
            a.account_type    = account_type
            a.initial_balance = initial_balance
            a.currency        = currency
            a.note            = note
            _save(accounts, transactions)
            return a
    return None


def remove_account(account_id: int) -> bool:
    accounts, transactions = load()
    new_accounts = [a for a in accounts if a.id != account_id]
    if len(new_accounts) == len(accounts):
        return False
    _save(new_accounts, [t for t in transactions if t.account_id != account_id])
    return True


# ── Transaction CRUD ───────────────────────────────────────────────────────────

def add_transaction(
    account_id:  int,
    tx_type:     str,
    amount:      float,
    tx_date:     date,
    description: Optional[str] = None,
) -> Transaction:
    accounts, transactions = load()
    tx = Transaction(
        id=_next_tx_id(transactions),
        account_id=account_id,
        type=tx_type,
        amount=amount,
        date=tx_date.isoformat(),
        description=description,
    )
    transactions.append(tx)
    _save(accounts, transactions)
    return tx


def remove_transaction(tx_id: int) -> bool:
    accounts, transactions = load()
    new_transactions = [t for t in transactions if t.id != tx_id]
    if len(new_transactions) == len(transactions):
        return False
    _save(accounts, new_transactions)
    return True


# ── Balance helper ─────────────────────────────────────────────────────────────

def current_balance(
    account_id:      int,
    transactions:    List[Transaction],
    initial_balance: float,
) -> float:
    """initial_balance + deposits − withdrawals for the given account."""
    bal = initial_balance
    for t in transactions:
        if t.account_id != account_id:
            continue
        if t.type == "deposit":
            bal += t.amount
        elif t.type == "withdrawal":
            bal -= t.amount
    return bal
