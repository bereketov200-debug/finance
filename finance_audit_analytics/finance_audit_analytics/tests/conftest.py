import pytest

from modules.models import transaction
from modules.storage import Store


@pytest.fixture
def item():
    def make(identifier="tx-1", **changes):
        defaults = {
            "id": identifier, "date": "2026-10-10", "type": "Expense", "category": "Food",
            "amount": "100.10", "description": "Groceries", "payment_method": "Card",
            "counterparty": "Fictional Market", "has_receipt": True, "receipt_reference": "",
            "created_at": "2026-10-10T10:00:00+00:00",
        }
        return transaction(defaults | changes)
    return make


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path)
