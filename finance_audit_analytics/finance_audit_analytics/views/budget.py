"""Monthly budget editor and utilization dashboard."""

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from modules.budgets import overall_utilization, performance, remove_limit, save_limit
from modules.models import EXPENSE
from .common import BLUE, CORAL, TEAL, commit, heading, metrics, money, pct, plot


def budget_editor(store, limits, month, currency, key):
    category = st.selectbox("Expense category", EXPENSE, key=f"{key}-category")
    current = next((row for row in limits if row["month"] == month and row["category"] == category), None)
    form_key = f"{key}-{month}-{category}"
    with st.form(form_key):
        limit = st.text_input(f"Monthly limit ({currency})", value=current["limit"] if current else "",
                              placeholder="75000.00", max_chars=24)
        if st.form_submit_button("Save budget limit", type="primary"):
            commit(lambda: save_limit(store, month, category, limit), f"Budget saved for {category} · {month}.")
    if current:
        with st.expander("Remove this limit"):
            confirmed = st.checkbox("Confirm removal", key=f"{form_key}-confirm")
            if st.button("Remove budget limit", key=f"{form_key}-remove", disabled=not confirmed):
                commit(lambda: remove_limit(store, month, category), f"Budget removed for {category} · {month}.")


def month_selector(label, initial, key):
    day = st.date_input(label, date.fromisoformat(initial + "-01"), key=key,
                        min_value=date(1, 1, 1), max_value=date(9999, 12, 31), format="YYYY-MM-DD",
                        help="Any date in the month selects that entire calendar month.")
    return day.isoformat()[:7]


def render(store, rows, limits, config, reviews):
    currency = config["currency"]
    heading("03 / Spending control", "Budgets", "Compare each category’s spending with its monthly limit.")
    most_recent = max((row["month"] for row in limits), default=date.today().isoformat()[:7])
    with st.container(border=True):
        month = month_selector("Budget month", most_recent, "budget-month")
    overview, edit = st.tabs(["Performance", "Manage limits"])
    with overview:
        records = performance(rows, limits, month, month)
        if not records:
            st.info("There are no saved category limits for this month. Use Manage limits to create one.")
        else:
            metrics([
                ("Total planned", money(sum(row["limit"] for row in records), currency), "Sum of category limits."),
                ("Spent in budgeted categories", money(sum(row["actual"] for row in records), currency),
                 "Unbudgeted categories are excluded."),
                ("Budget utilization", pct(overall_utilization(records)), "Actual spending divided by total planned."),
            ])
            chart, progress = st.columns([3, 2])
            with chart, st.container(border=True):
                st.subheader("Planned vs. actual")
                figure = go.Figure()
                categories = [row["category"] for row in records]
                figure.add_bar(name="Planned", x=categories, y=[float(row["limit"]) for row in records], marker_color=BLUE)
                figure.add_bar(name="Actual", x=categories, y=[float(row["actual"]) for row in records],
                               marker_color=[CORAL if row["status"] == "Exceeded" else TEAL for row in records])
                plot(figure, key="budget-comparison", y_label=currency)
            with progress, st.container(border=True):
                st.subheader("Category utilization")
                for row in records:
                    text = f"{row['category']} · {pct(row['utilization'])} · {row['status']}"
                    st.progress(min(1.0, float(row["utilization"]) / 100), text=text)
                    if row["utilization"] >= 100:
                        st.error(f"{row['category']} has reached its limit." if row["actual"] == row["limit"]
                                 else f"{row['category']} is {money(-row['remaining'], currency)} over budget.")
                    elif row["utilization"] >= 80:
                        st.warning(f"{row['category']} has reached 80% of its limit.")
    with edit:
        st.subheader(f"Category limits · {month}")
        budget_editor(store, limits, month, currency, "budget")
