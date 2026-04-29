"""Tests for finace.bank — bank account and transaction management."""
import pytest
from datetime import date

import finace.bank as bank

pytestmark = pytest.mark.usefixtures("tmp_bank")


# ── load ───────────────────────────────────────────────────────────────────────

def test_load_empty_when_no_file():
    accounts, transactions = bank.load()
    assert accounts == [] and transactions == []


# ── add_account ────────────────────────────────────────────────────────────────

def test_add_account_returns_account():
    a = bank.add_account("Chase", "Checking", 1000.0)
    assert isinstance(a, bank.Account)

def test_add_account_assigns_id():
    a = bank.add_account("Chase", "Checking", 1000.0)
    assert a.id == 1

def test_add_account_increments_id():
    bank.add_account("A", "Checking", 0.0)
    b = bank.add_account("B", "Savings", 0.0)
    assert b.id == 2

def test_add_account_persists():
    bank.add_account("Chase", "Checking", 1000.0)
    accounts, _ = bank.load()
    assert len(accounts) == 1

def test_add_account_stores_all_fields():
    bank.add_account("My Savings", "Savings", 500.0, currency="EUR", note="holiday fund")
    a = bank.load()[0][0]
    assert a.name            == "My Savings"
    assert a.account_type    == "Savings"
    assert a.initial_balance == pytest.approx(500.0)
    assert a.currency        == "EUR"
    assert a.note            == "holiday fund"

def test_add_account_default_currency_usd():
    bank.add_account("X", "Checking", 0.0)
    assert bank.load()[0][0].currency == "USD"

def test_add_account_default_note_none():
    bank.add_account("X", "Checking", 0.0)
    assert bank.load()[0][0].note is None


# ── update_account ─────────────────────────────────────────────────────────────

def test_update_account_returns_account():
    a = bank.add_account("Chase", "Checking", 1000.0)
    assert bank.update_account(a.id, "Chase", "Checking", 1000.0, "USD") is not None

def test_update_account_unknown_id_returns_none():
    assert bank.update_account(999, "X", "Checking", 0.0, "USD") is None

def test_update_account_changes_name():
    a = bank.add_account("Old", "Checking", 1000.0)
    bank.update_account(a.id, "New", "Checking", 1000.0, "USD")
    assert bank.load()[0][0].name == "New"

def test_update_account_changes_type():
    a = bank.add_account("X", "Checking", 0.0)
    bank.update_account(a.id, "X", "Savings", 0.0, "USD")
    assert bank.load()[0][0].account_type == "Savings"

def test_update_account_changes_balance():
    a = bank.add_account("X", "Checking", 100.0)
    bank.update_account(a.id, "X", "Checking", 999.0, "USD")
    assert bank.load()[0][0].initial_balance == pytest.approx(999.0)

def test_update_account_changes_currency():
    a = bank.add_account("X", "Checking", 0.0)
    bank.update_account(a.id, "X", "Checking", 0.0, "EUR")
    assert bank.load()[0][0].currency == "EUR"

def test_update_account_clears_note():
    a = bank.add_account("X", "Checking", 0.0, note="old")
    bank.update_account(a.id, "X", "Checking", 0.0, "USD", note=None)
    assert bank.load()[0][0].note is None

def test_update_account_does_not_affect_others():
    a1 = bank.add_account("A", "Checking", 100.0)
    a2 = bank.add_account("B", "Savings",  200.0)
    bank.update_account(a1.id, "A", "Checking", 999.0, "USD")
    others = [a for a in bank.load()[0] if a.id == a2.id]
    assert others[0].initial_balance == pytest.approx(200.0)


# ── remove_account ─────────────────────────────────────────────────────────────

def test_remove_account_returns_true():
    a = bank.add_account("X", "Checking", 0.0)
    assert bank.remove_account(a.id) is True

def test_remove_account_unknown_id_returns_false():
    assert bank.remove_account(999) is False

def test_remove_account_deletes_it():
    a = bank.add_account("X", "Checking", 0.0)
    bank.remove_account(a.id)
    assert bank.load()[0] == []

def test_remove_account_also_deletes_its_transactions():
    a = bank.add_account("X", "Checking", 0.0)
    bank.add_transaction(a.id, "deposit", 100.0, date(2024, 1, 2))
    bank.remove_account(a.id)
    assert bank.load()[1] == []

def test_remove_account_leaves_other_accounts():
    a1 = bank.add_account("A", "Checking", 0.0)
    a2 = bank.add_account("B", "Savings",  0.0)
    bank.remove_account(a1.id)
    accounts, _ = bank.load()
    assert len(accounts) == 1 and accounts[0].id == a2.id

def test_remove_account_leaves_other_transactions():
    a1 = bank.add_account("A", "Checking", 0.0)
    a2 = bank.add_account("B", "Savings",  0.0)
    bank.add_transaction(a1.id, "deposit", 50.0,  date(2024, 1, 2))
    bank.add_transaction(a2.id, "deposit", 100.0, date(2024, 1, 3))
    bank.remove_account(a1.id)
    _, txs = bank.load()
    assert len(txs) == 1 and txs[0].account_id == a2.id


# ── add_transaction ────────────────────────────────────────────────────────────

def test_add_transaction_returns_transaction():
    a = bank.add_account("X", "Checking", 0.0)
    tx = bank.add_transaction(a.id, "deposit", 100.0, date(2024, 1, 2))
    assert isinstance(tx, bank.Transaction)

def test_add_transaction_assigns_id():
    a = bank.add_account("X", "Checking", 0.0)
    tx = bank.add_transaction(a.id, "deposit", 100.0, date(2024, 1, 2))
    assert tx.id == 1

def test_add_transaction_increments_id():
    a = bank.add_account("X", "Checking", 0.0)
    bank.add_transaction(a.id, "deposit",    100.0, date(2024, 1, 2))
    t2 = bank.add_transaction(a.id, "withdrawal", 50.0,  date(2024, 1, 3))
    assert t2.id == 2

def test_add_transaction_persists():
    a = bank.add_account("X", "Checking", 0.0)
    bank.add_transaction(a.id, "deposit", 100.0, date(2024, 1, 2))
    _, txs = bank.load()
    assert len(txs) == 1

def test_add_transaction_stores_all_fields():
    a = bank.add_account("X", "Checking", 0.0)
    bank.add_transaction(a.id, "withdrawal", 50.0, date(2024, 3, 15), description="ATM")
    _, txs = bank.load()
    t = txs[0]
    assert t.account_id  == a.id
    assert t.type        == "withdrawal"
    assert t.amount      == pytest.approx(50.0)
    assert t.date        == "2024-03-15"
    assert t.description == "ATM"

def test_add_transaction_default_description_none():
    a = bank.add_account("X", "Checking", 0.0)
    bank.add_transaction(a.id, "deposit", 10.0, date(2024, 1, 2))
    assert bank.load()[1][0].description is None


# ── remove_transaction ─────────────────────────────────────────────────────────

def test_remove_transaction_returns_true():
    a  = bank.add_account("X", "Checking", 0.0)
    tx = bank.add_transaction(a.id, "deposit", 100.0, date(2024, 1, 2))
    assert bank.remove_transaction(tx.id) is True

def test_remove_transaction_unknown_id_returns_false():
    assert bank.remove_transaction(999) is False

def test_remove_transaction_deletes_it():
    a  = bank.add_account("X", "Checking", 0.0)
    tx = bank.add_transaction(a.id, "deposit", 100.0, date(2024, 1, 2))
    bank.remove_transaction(tx.id)
    assert bank.load()[1] == []

def test_remove_transaction_leaves_others():
    a   = bank.add_account("X", "Checking", 0.0)
    t1  = bank.add_transaction(a.id, "deposit",    100.0, date(2024, 1, 2))
    t2  = bank.add_transaction(a.id, "withdrawal", 50.0,  date(2024, 1, 3))
    bank.remove_transaction(t1.id)
    _, txs = bank.load()
    assert len(txs) == 1 and txs[0].id == t2.id


# ── current_balance ────────────────────────────────────────────────────────────

def test_current_balance_no_transactions():
    assert bank.current_balance(1, [], 500.0) == pytest.approx(500.0)

def test_current_balance_deposit_adds():
    a = bank.add_account("X", "Checking", 1000.0)
    bank.add_transaction(a.id, "deposit", 200.0, date(2024, 1, 2))
    _, txs = bank.load()
    assert bank.current_balance(a.id, txs, a.initial_balance) == pytest.approx(1200.0)

def test_current_balance_withdrawal_subtracts():
    a = bank.add_account("X", "Checking", 1000.0)
    bank.add_transaction(a.id, "withdrawal", 300.0, date(2024, 1, 2))
    _, txs = bank.load()
    assert bank.current_balance(a.id, txs, a.initial_balance) == pytest.approx(700.0)

def test_current_balance_multiple_transactions():
    a = bank.add_account("X", "Checking", 1000.0)
    bank.add_transaction(a.id, "deposit",    500.0, date(2024, 1, 2))
    bank.add_transaction(a.id, "withdrawal", 200.0, date(2024, 1, 3))
    bank.add_transaction(a.id, "deposit",    100.0, date(2024, 1, 4))
    _, txs = bank.load()
    assert bank.current_balance(a.id, txs, a.initial_balance) == pytest.approx(1400.0)

def test_current_balance_ignores_other_accounts():
    a1 = bank.add_account("A", "Checking", 1000.0)
    a2 = bank.add_account("B", "Savings",   500.0)
    bank.add_transaction(a2.id, "deposit", 1000.0, date(2024, 1, 2))
    _, txs = bank.load()
    assert bank.current_balance(a1.id, txs, a1.initial_balance) == pytest.approx(1000.0)

def test_current_balance_can_go_negative():
    a = bank.add_account("X", "Checking", 100.0)
    bank.add_transaction(a.id, "withdrawal", 200.0, date(2024, 1, 2))
    _, txs = bank.load()
    assert bank.current_balance(a.id, txs, a.initial_balance) == pytest.approx(-100.0)
