"""Transaction history, editing, and CSV exchange."""

from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from modules import transactions as service
from modules.models import EXPENSE, INCOME, PAYMENTS
from modules.reports import csv_report, csv_template
from .common import commit, date_filter, heading, money


def transaction_form(store, original=None):
    row = original or {}
    identifier = row.get("id", "new")
    kinds = ("Expense", "Income")
    kind = st.selectbox("Transaction type", kinds, index=kinds.index(row.get("type", "Expense")),
                        key=f"kind-{identifier}")
    options = EXPENSE if kind == "Expense" else INCOME
    original_category = row.get("category")
    index = options.index(original_category) if original_category in options else 0
    with st.form(f"transaction-{identifier}-{kind}", clear_on_submit=not original):
        left, right = st.columns(2)
        day_value = date.fromisoformat(row["date"]) if row else date.today()
        day = left.date_input("Date", day_value, min_value=date(1, 1, 1), max_value=date(9999, 12, 31),
                              format="YYYY-MM-DD")
        category = right.selectbox("Category", options, index=index)
        value = left.text_input("Amount", row.get("amount", ""), placeholder="12500.00", max_chars=24)
        method = right.selectbox("Payment method", PAYMENTS,
                                 index=PAYMENTS.index(row.get("payment_method", PAYMENTS[0])))
        counterparty = st.text_input("Counterparty", row.get("counterparty", ""), max_chars=120)
        description = st.text_input("Description", row.get("description", ""), max_chars=240)
        left, right = st.columns(2)
        receipt = left.checkbox("Receipt available", row.get("has_receipt", False))
        reference = right.text_input("Receipt reference (optional)", row.get("receipt_reference", ""), max_chars=120)
        if st.form_submit_button("Save changes" if original else "Add transaction", type="primary"):
            fields = {"type": kind, "date": day.isoformat(), "category": category, "amount": value,
                      "payment_method": method, "counterparty": counterparty, "description": description,
                      "has_receipt": receipt, "receipt_reference": reference}
            if original:
                commit(lambda: service.edit(store, identifier, fields), "Transaction updated.")
            else:
                commit(lambda: service.add(store, fields), "Transaction added.")


def render(store, rows, limits, config, reviews):
    currency = config["currency"]
    heading("02 / Ledger", "Transactions", "Record, reconcile, and export your income and expenses.")
    history, add, edit, exchange = st.tabs(["History", "Add transaction", "Edit or delete", "CSV exchange"])

    with history:
        with st.container(border=True):
            left, right = st.columns(2)
            with left:
                start, end = date_filter(rows, config, "ledger")
            search = right.text_input("Search ledger", placeholder="Counterparty, description, ID, or receipt")
            left, middle, right = st.columns(3)
            kind = left.selectbox("Type", ("All", "Expense", "Income"))
            categories = middle.multiselect("Category", sorted(set(INCOME + EXPENSE)), placeholder="All categories")
            field = right.selectbox("Sort by", ("date", "amount", "category"), format_func=str.title)
            descending = right.checkbox("Descending", value=True)
        selected = service.filter_transactions(rows, start, end, categories, None if kind == "All" else kind, search)
        selected = service.sort_transactions(selected, field, descending)
        st.caption(f"{len(selected):,} matching transactions · amounts in {currency}")
        if selected:
            st.dataframe(pd.DataFrame([{**row, "amount": float(row["amount"])} for row in selected]),
                         hide_index=True, width="stretch",
                         column_config={"amount": st.column_config.NumberColumn(f"Amount ({currency})", format="localized")})
        else:
            st.info("No transactions match the current filters.")
        st.download_button("Export matching transactions", csv_report(
            selected, service.TRANSACTION_COLUMNS, start=start, end=end, currency=currency),
            "transactions.csv", "text/csv", disabled=not selected)

    with add:
        st.subheader("New transaction")
        st.caption(f"Enter a positive amount in {currency}. A receipt reference confirms availability.")
        transaction_form(store)

    with edit:
        if not rows:
            st.info("Add a transaction to enable editing.")
        else:
            indexed = {row["id"]: row for row in service.sort_transactions(rows)}

            def label(identifier):
                item = indexed[identifier]
                return (f"{item['date']} · {item['counterparty']} · "
                        f"{money(Decimal(item['amount']), currency)} · {identifier[:8]}")

            identifier = st.selectbox("Choose transaction", list(indexed), format_func=label)
            transaction_form(store, indexed[identifier])
            with st.expander("Delete transaction"):
                st.write(f"Selected ID `{identifier}`")
                confirmed = st.checkbox("Confirm permanent deletion of this transaction", key=f"delete-{identifier}")
                if st.button("Delete confirmed transaction", disabled=not confirmed, key=f"delete-btn-{identifier}"):
                    commit(lambda: service.delete(store, identifier), "Transaction deleted.")

    with exchange:
        st.subheader("Import transactions")
        st.write("Use UTF-8 comma-separated data. The entire batch is validated before saving.")
        with st.expander("CSV format"):
            st.code(", ".join(service.REQUIRED_COLUMNS), language="text")
            st.write("Use YYYY-MM-DD dates and decimal amounts without grouping separators. "
                     "IDs and creation timestamps can be blank. Receipt fields are optional. "
                     "Choose categories and payment methods from the transaction form.")
        st.download_button("Download CSV template", csv_template(), "transactions_template.csv", "text/csv")
        upload = st.file_uploader("Transaction CSV", type=["csv"])
        if st.button("Validate and import", type="primary", disabled=upload is None):
            commit(lambda: service.import_csv(store, upload.getvalue()), lambda count: f"Imported {count:,} transactions.")
