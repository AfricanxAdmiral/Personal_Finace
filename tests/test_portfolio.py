"""Tests for finace.portfolio — CRUD operations and JSON persistence."""
import json
import pytest
from datetime import date

import finace.portfolio as pf


# ── load ───────────────────────────────────────────────────────────────────────

def test_load_returns_empty_list_when_no_file(tmp_portfolio):
    assert pf.load() == []

def test_load_returns_empty_list_when_file_empty(tmp_portfolio):
    with open(pf.PORTFOLIO_FILE, "w") as f:
        json.dump([], f)
    assert pf.load() == []


# ── add_position ───────────────────────────────────────────────────────────────

def test_add_returns_position(tmp_portfolio):
    pos = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    assert isinstance(pos, pf.Position)

def test_add_assigns_id_one_to_first(tmp_portfolio):
    pos = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    assert pos.id == 1

def test_add_ids_increment(tmp_portfolio):
    p1 = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    p2 = pf.add_position("MSFT",  5.0, 370.0, date(2024, 1, 2))
    assert p2.id == p1.id + 1

def test_add_ticker_uppercased(tmp_portfolio):
    pos = pf.add_position("aapl", 10.0, 150.0, date(2024, 1, 2))
    assert pos.ticker == "AAPL"

def test_add_persists_to_file(tmp_portfolio):
    pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    loaded = pf.load()
    assert len(loaded) == 1
    assert loaded[0].ticker == "AAPL"

def test_add_stores_note(tmp_portfolio):
    pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2), note="My note")
    assert pf.load()[0].note == "My note"

def test_add_stores_fractional_shares(tmp_portfolio):
    pf.add_position("AAPL", 0.5, 150.0, date(2024, 1, 2))
    assert pf.load()[0].shares == pytest.approx(0.5)

def test_add_sell_fields_default_to_none(tmp_portfolio):
    pos = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    assert pos.sell_price is None
    assert pos.sell_date  is None


# ── sell_position ──────────────────────────────────────────────────────────────

def test_sell_returns_position(tmp_portfolio):
    pos = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    result = pf.sell_position(pos.id, 180.0, date(2024, 6, 1))
    assert result is not None

def test_sell_sets_sell_price(tmp_portfolio):
    pos = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    pf.sell_position(pos.id, 180.0, date(2024, 6, 1))
    assert pf.load()[0].sell_price == pytest.approx(180.0)

def test_sell_sets_sell_date(tmp_portfolio):
    pos = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    pf.sell_position(pos.id, 180.0, date(2024, 6, 1))
    assert pf.load()[0].sell_date == "2024-06-01"

def test_sell_persists_to_file(tmp_portfolio):
    pos = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    pf.sell_position(pos.id, 180.0, date(2024, 6, 1))
    reloaded = pf.load()
    assert reloaded[0].sell_price == pytest.approx(180.0)

def test_sell_unknown_id_returns_none(tmp_portfolio):
    assert pf.sell_position(999, 180.0, date(2024, 6, 1)) is None

def test_sell_does_not_affect_other_positions(tmp_portfolio):
    p1 = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    p2 = pf.add_position("MSFT",  5.0, 370.0, date(2024, 1, 2))
    pf.sell_position(p1.id, 180.0, date(2024, 6, 1))
    loaded = {p.id: p for p in pf.load()}
    assert loaded[p2.id].sell_price is None


# ── remove_position ────────────────────────────────────────────────────────────

def test_remove_returns_true_on_success(tmp_portfolio):
    pos = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    assert pf.remove_position(pos.id) is True

def test_remove_deletes_position(tmp_portfolio):
    pos = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    pf.remove_position(pos.id)
    assert pf.load() == []

def test_remove_unknown_id_returns_false(tmp_portfolio):
    assert pf.remove_position(999) is False

def test_remove_leaves_other_positions(tmp_portfolio):
    p1 = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    p2 = pf.add_position("MSFT",  5.0, 370.0, date(2024, 1, 2))
    pf.remove_position(p1.id)
    remaining = pf.load()
    assert len(remaining) == 1
    assert remaining[0].id == p2.id


# ── JSON round-trip ────────────────────────────────────────────────────────────

def test_roundtrip_preserves_all_fields(tmp_portfolio):
    pf.add_position("NVDA", 3.5, 800.25, date(2024, 3, 15), note="Test")
    pos = pf.load()[0]
    assert pos.ticker    == "NVDA"
    assert pos.shares    == pytest.approx(3.5)
    assert pos.buy_price == pytest.approx(800.25)
    assert pos.buy_date  == "2024-03-15"
    assert pos.note      == "Test"

def test_roundtrip_sold_position(tmp_portfolio):
    p = pf.add_position("AAPL", 10.0, 150.0, date(2024, 1, 2))
    pf.sell_position(p.id, 190.0, date(2024, 9, 1))
    pos = pf.load()[0]
    assert pos.sell_price == pytest.approx(190.0)
    assert pos.sell_date  == "2024-09-01"


# ── update_position ────────────────────────────────────────────────────────────

def test_update_returns_position(tmp_portfolio):
    p = pf.add_position("AAPL", 10, 150.0, date(2024, 1, 2))
    result = pf.update_position(p.id, "AAPL", 10, 150.0, date(2024, 1, 2))
    assert result is not None

def test_update_unknown_id_returns_none(tmp_portfolio):
    assert pf.update_position(999, "AAPL", 10, 150.0, date(2024, 1, 2)) is None

def test_update_changes_ticker(tmp_portfolio):
    p = pf.add_position("AAPL", 10, 150.0, date(2024, 1, 2))
    pf.update_position(p.id, "msft", 10, 150.0, date(2024, 1, 2))
    assert pf.load()[0].ticker == "MSFT"

def test_update_changes_shares(tmp_portfolio):
    p = pf.add_position("AAPL", 10, 150.0, date(2024, 1, 2))
    pf.update_position(p.id, "AAPL", 20, 150.0, date(2024, 1, 2))
    assert pf.load()[0].shares == 20

def test_update_changes_buy_price(tmp_portfolio):
    p = pf.add_position("AAPL", 10, 150.0, date(2024, 1, 2))
    pf.update_position(p.id, "AAPL", 10, 175.5, date(2024, 1, 2))
    assert pf.load()[0].buy_price == pytest.approx(175.5)

def test_update_changes_buy_date(tmp_portfolio):
    p = pf.add_position("AAPL", 10, 150.0, date(2024, 1, 2))
    pf.update_position(p.id, "AAPL", 10, 150.0, date(2024, 6, 1))
    assert pf.load()[0].buy_date == "2024-06-01"

def test_update_changes_note(tmp_portfolio):
    p = pf.add_position("AAPL", 10, 150.0, date(2024, 1, 2), note="old")
    pf.update_position(p.id, "AAPL", 10, 150.0, date(2024, 1, 2), note="new")
    assert pf.load()[0].note == "new"

def test_update_can_clear_note(tmp_portfolio):
    p = pf.add_position("AAPL", 10, 150.0, date(2024, 1, 2), note="old")
    pf.update_position(p.id, "AAPL", 10, 150.0, date(2024, 1, 2), note=None)
    assert pf.load()[0].note is None

def test_update_can_add_sell_info(tmp_portfolio):
    p = pf.add_position("AAPL", 10, 150.0, date(2024, 1, 2))
    pf.update_position(p.id, "AAPL", 10, 150.0, date(2024, 1, 2),
                       sell_price=200.0, sell_date=date(2024, 9, 1))
    pos = pf.load()[0]
    assert pos.sell_price == pytest.approx(200.0)
    assert pos.sell_date  == "2024-09-01"

def test_update_can_clear_sell_info(tmp_portfolio):
    p = pf.add_position("AAPL", 10, 150.0, date(2024, 1, 2))
    pf.sell_position(p.id, 200.0, date(2024, 9, 1))
    pf.update_position(p.id, "AAPL", 10, 150.0, date(2024, 1, 2),
                       sell_price=None, sell_date=None)
    pos = pf.load()[0]
    assert pos.sell_price is None
    assert pos.sell_date  is None

def test_update_does_not_affect_other_positions(tmp_portfolio):
    p1 = pf.add_position("AAPL", 10, 150.0, date(2024, 1, 2))
    p2 = pf.add_position("MSFT", 5,  300.0, date(2024, 2, 1))
    pf.update_position(p1.id, "AAPL", 20, 150.0, date(2024, 1, 2))
    others = [p for p in pf.load() if p.id == p2.id]
    assert others[0].shares == 5

def test_update_persists_to_file(tmp_portfolio):
    p = pf.add_position("AAPL", 10, 150.0, date(2024, 1, 2))
    pf.update_position(p.id, "AAPL", 99, 150.0, date(2024, 1, 2))
    assert pf.load()[0].shares == 99
