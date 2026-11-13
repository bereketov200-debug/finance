from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from demo_data import seed_store
from modules.storage import Store


APP = Path(__file__).resolve().parents[1] / "app.py"
TITLES = {
    "Overview": "Finance & Audit Analytics", "Transactions": "Transactions", "Budgets": "Budgets",
    "Audit Review": "Audit Review", "Audit Dashboard": "Audit Dashboard", "Financial Health": "Financial Health",
    "Expense Forecast": "Expense Forecast", "Reports": "Reports", "Settings": "Settings",
}


def control(elements, label):
    return next(element for element in elements if element.label == label)


@pytest.mark.parametrize("with_demo", [False, True])
def test_all_nine_pages_render(tmp_path, monkeypatch, with_demo):
    monkeypatch.setenv("FINANCE_DATA_DIR", str(tmp_path))
    if with_demo:
        seed_store(Store(tmp_path), "2026-11")
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    for page, title in TITLES.items():
        app.radio[0].set_value(page).run()
        assert not app.exception, (page, app.exception)
        assert app.title[0].value == title


def test_add_budget_review_and_settings_persist(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCE_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.radio[0].set_value("Transactions").run()
    for label, value in (("Amount", "320000.23"), ("Counterparty", "Fictional Shop"), ("Description", "Equipment")):
        control(app.text_input, label).set_value(value)
    control(app.button, "Add transaction").click().run()
    assert not app.exception and not app.error
    assert Store(tmp_path).read("transactions")[0]["amount"] == "320000.23"
    app.radio[0].set_value("Budgets").run()
    control(app.text_input, "Monthly limit (KZT)").set_value("100000")
    control(app.button, "Save budget limit").click().run()
    assert not app.exception and Store(tmp_path).read("budgets")[0]["limit"] == "100000.00"
    app.radio[0].set_value("Audit Review").run()
    control(app.selectbox, "Update review status").set_value("Under Review")
    control(app.text_area, "Review notes").set_value("Checking approval.")
    control(app.button, "Save review").click().run()
    assert not app.exception and Store(tmp_path).read("audit_reviews")[0]["notes"] == "Checking approval."
    app.radio[0].set_value("Settings").run()
    control(app.selectbox, "Display currency").set_value("USD")
    control(app.button, "Save settings").click().run()
    assert not app.exception and Store(tmp_path).read("settings")["currency"] == "USD"


def test_edit_and_confirm_delete_in_ui(tmp_path, monkeypatch, item):
    monkeypatch.setenv("FINANCE_DATA_DIR", str(tmp_path))
    store = Store(tmp_path)
    store.update("transactions", lambda rows: [item()])
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    app.radio[0].set_value("Transactions").run()
    amounts = [widget for widget in app.text_input if widget.label == "Amount"]
    assert len(amounts) == 2
    amounts[1].set_value("220.50")
    control(app.button, "Save changes").click().run()
    assert not app.exception and not app.error
    assert store.read("transactions")[0]["amount"] == "220.50"
    assert control(app.button, "Delete confirmed transaction").disabled
    control(app.checkbox, "Confirm permanent deletion of this transaction").check().run()
    control(app.button, "Delete confirmed transaction").click().run()
    assert not app.exception and not app.error
    assert store.read("transactions") == []
