"""Streamlit entry point for Finance & Audit Analytics."""

import streamlit as st

from modules.storage import StorageError, Store
from views import audit, budget, dashboard, forecast, health, ledger, reports, settings


PAGES = {
    "Overview": ("📊", dashboard.render),
    "Transactions": ("⇄", ledger.render),
    "Budgets": ("◫", budget.render),
    "Audit Review": ("⚑", audit.review_page),
    "Audit Dashboard": ("◎", audit.dashboard_page),
    "Financial Health": ("♥", health.render),
    "Expense Forecast": ("↗", forecast.render),
    "Reports": ("↓", reports.render),
    "Settings": ("⚙", settings.render),
}


def main():
    st.set_page_config(page_title="Finance & Audit Analytics", page_icon="📊", layout="wide")
    try:
        store = Store()
    except StorageError as error:
        st.error(str(error))
        return
    records = store.read("transactions")
    limits = store.read("budgets")
    config = store.read("settings")
    reviews = store.read("audit_reviews")
    for warning in store.warnings:
        st.warning(warning)

    with st.sidebar:
        st.markdown("### Finance & Audit Analytics")
        st.caption("LOCAL FINANCE WORKSPACE")
        page = st.radio("Workspace", PAGES, format_func=lambda name: f"{PAGES[name][0]}  {name}",
                        label_visibility="collapsed")
        st.divider()
        st.caption(f"Ledger currency · {config['currency']}  •  {len(records):,} transactions")
    if message := st.session_state.pop("notice", None):
        st.success(message)
    PAGES[page][1](store, records, limits, config, reviews)


if __name__ == "__main__":
    main()
