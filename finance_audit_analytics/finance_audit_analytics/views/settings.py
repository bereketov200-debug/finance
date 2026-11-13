"""Persistent display preferences and audit controls."""

from datetime import date

import streamlit as st

from modules.models import CURRENCIES, INT_SETTINGS, PERIODS, settings
from .budget import budget_editor, month_selector
from .common import commit, heading


SENSITIVITY = ("Conservative", "Standard", "Sensitive")


def count_field(column, label, config, key):
    low, high = INT_SETTINGS[key]
    return column.number_input(label, min_value=low, max_value=high, value=config[key], step=1)


def render(store, rows, limits, config, reviews):
    heading("09 / Configuration", "Settings", "Manage the ledger display, audit thresholds, and monthly category limits.")
    preferences, budgets = st.tabs(["Display and audit", "Budget limits"])
    with preferences:
        with st.form("settings"):
            st.subheader("Reporting preferences")
            left, right = st.columns(2)
            currency = left.selectbox("Display currency", CURRENCIES, index=CURRENCIES.index(config["currency"]))
            period = right.selectbox("Default reporting period", PERIODS, index=PERIODS.index(config["period"]))
            st.caption("The ledger uses one currency. Changing the display currency relabels all saved amounts and thresholds.")
            st.divider()
            st.subheader("Audit thresholds")
            left, right = st.columns(2)
            sensitivity = left.selectbox("Audit sensitivity", SENSITIVITY, index=SENSITIVITY.index(config["sensitivity"]),
                                         help="Adjusts the unusual-expense multiplier, minimum split count, and frequency test.")
            threshold = right.text_input("Large transaction / approval threshold", config["large_threshold"])
            receipt = left.text_input("Minimum expense for receipt checks", config["receipt_minimum"])
            unusual = right.text_input("Minimum unusual expense amount", config["unusual_minimum"])
            multiplier = left.text_input("Unusual expense baseline multiplier", config["unusual_multiplier"])
            history_count = count_field(right, "Minimum previous expenses", config, "history_count")
            st.markdown("**Splitting and frequency windows**")
            left, right = st.columns(2)
            split_days = count_field(left, "Split window (elapsed days)", config, "split_days")
            split_count = count_field(right, "Split base minimum count", config, "split_count")
            split_min_share = count_field(left, "Minimum split item (% of approval threshold)", config, "split_min_share")
            frequency_days = count_field(right, "Frequency window (calendar days)", config, "frequency_days")
            frequency_count = count_field(left, "Frequency base minimum count", config, "frequency_count")
            frequency_weeks = count_field(right, "Frequency baseline (weeks)", config, "frequency_history_weeks")
            if st.form_submit_button("Save settings", type="primary"):
                candidate = {
                    "currency": currency, "period": period, "sensitivity": sensitivity,
                    "large_threshold": threshold, "receipt_minimum": receipt,
                    "unusual_minimum": unusual, "history_count": history_count, "unusual_multiplier": multiplier,
                    "split_days": split_days, "split_count": split_count, "split_min_share": split_min_share,
                    "frequency_days": frequency_days, "frequency_count": frequency_count,
                    "frequency_history_weeks": frequency_weeks,
                }
                commit(lambda: store.update("settings", lambda _: settings(candidate)), "Settings saved.")
    with budgets:
        month = month_selector("Budget month", date.today().isoformat()[:7], "settings-month")
        budget_editor(store, limits, month, config["currency"], "settings-budget")
