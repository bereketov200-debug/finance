import json

import pytest

from demo_data import seed_store
from modules.models import amount
from modules.reports import csv_report, csv_template
from modules.storage import StorageError, Store
from modules.transactions import TRANSACTION_COLUMNS, add, delete, edit, import_csv, parse_csv


@pytest.mark.parametrize("invalid", ["0", "-1", "10.001", "NaN", "Infinity", "1e100", "x", ""])
def test_invalid_amounts(invalid):
    with pytest.raises(ValueError):
        amount(invalid)


def test_add_edit_delete_persist_and_keep_identity(store, item):
    original = add(store, item())
    edit(store, original["id"], {"amount": "300.42"})
    restored = Store(store.root).read("transactions")[0]
    assert restored["id"] == original["id"]
    assert restored["created_at"] == original["created_at"]
    assert restored["amount"] == "300.42"
    delete(store, restored["id"])
    assert Store(store.root).read("transactions") == []


def test_corrupt_file_is_not_overwritten(store, item):
    target = store.root / "transactions.json"
    raw = json.dumps([item(), {"id": "broken"}])
    target.write_text(raw, encoding="utf-8")
    assert store.read("transactions") == [item()]
    assert store.warnings
    with pytest.raises(StorageError):
        add(store, item())
    assert target.read_text(encoding="utf-8") == raw


def test_blank_and_missing_files(store):
    path = store.root / "budgets.json"
    path.write_text("", encoding="utf-8")
    assert store.read("budgets") == []
    assert store.warnings
    assert path.read_text(encoding="utf-8") == ""
    path.unlink()
    assert Store(store.root).read("budgets") == []
    assert path.is_file()


def test_failed_atomic_replace_preserves_prior_file(store, item, monkeypatch):
    add(store, item())
    target = store.root / "transactions.json"
    before = target.read_bytes()

    def fail(*args):
        raise OSError("simulated failure")

    monkeypatch.setattr("modules.storage.os.replace", fail)
    with pytest.raises(StorageError):
        add(store, item())
    assert target.read_bytes() == before
    assert not list(store.root.glob("*.tmp"))


def test_csv_rejects_duplicate_ids_and_bad_rows_atomically(store):
    assert import_csv(store, csv_template()) == 1
    data = ("id,date,type,category,amount,description,payment_method,counterparty\n"
            "ABC,2026-10-10,Expense,Food,12.00,Lunch,Card,Example Cafe\n"
            "abc,2026-10-11,Expense,Food,12.00,Lunch,Card,Example Cafe\n"
            "third,2026-10-11,Expense,Food,-12.00,Lunch,Card,Example Cafe\n").encode()
    with pytest.raises(ValueError) as error:
        import_csv(store, data)
    assert "Line 3: Duplicate transaction ID abc" in str(error.value)
    assert "Line 4: Amount" in str(error.value)
    assert len(store.read("transactions")) == 1


def test_transaction_report_reimports_and_protects_spreadsheet_text(item):
    row = item(description="=1+1", counterparty="'A fictional cafe")
    payload = csv_report([row], TRANSACTION_COLUMNS, currency="KZT")
    assert b"'=1+1" in payload
    assert b"generated_at" in payload
    assert parse_csv(payload) == [row]
    with pytest.raises(ValueError, match="Duplicate transaction ID"):
        parse_csv(payload, existing_ids=[row["id"].upper()])


def test_demo_refuses_existing_data(store, item):
    original = add(store, item())
    with pytest.raises(ValueError, match="empty"):
        seed_store(store, "2026-11")
    assert store.read("transactions") == [original]
