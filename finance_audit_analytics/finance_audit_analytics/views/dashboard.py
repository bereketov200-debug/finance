"""Financial overview with filters, KPIs, and interactive charts."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.audit_engine import run_audit
from modules.budgets import overall_utilization, performance
from modules.finance import expense_categories, monthly, summarize
from modules.models import EXPENSE, INCOME
from modules.risk_scoring import risk_score, transaction_exposure
from modules.transactions import filter_transactions
from .common import BLUE, CORAL, PALETTE, TEAL, chart_data, date_filter, heading, metrics, money, pct, plot, score


def render(store, rows, limits, config, reviews):
    currency = config["currency"]
    heading("01 / Financial overview", "Finance & Audit Analytics",
            "Financial Management, Intelligent Monitoring & Automated Audit System")
    with st.container(border=True):
        left, right = st.columns([1, 2])
        with left:
            start, end = date_filter(rows, config, "dashboard")
        categories = right.multiselect("Categories", sorted(set(INCOME + EXPENSE)),
                                       placeholder="All categories")
    selected = filter_transactions(rows, start, end, categories)
    category_rows = filter_transactions(rows, categories=categories)
    opening = summarize([row for row in category_rows if row["date"] < start])["net"]
    totals = summarize(selected)
    trend = monthly(selected, start, end, opening)
    budgets = performance(rows, limits, start[:7], end[:7], categories)
    exposure = transaction_exposure(run_audit(rows, limits, config, reviews), (row["id"] for row in selected))

    metrics([
        ("Total income", money(totals["income"], currency), "Income in the selected dates and categories."),
        ("Total expenses", money(totals["expenses"], currency), "Expenses in the selected dates and categories."),
        ("Current balance", money(trend[-1]["balance"], currency), "Cumulative recorded net through the end date, including the opening balance for selected categories."),
    ])
    metrics([
        ("Monthly net cash flow", money(trend[-1]["net"], currency), "Net cash flow for the final selected month, limited to the selected dates."),
        ("Savings rate", pct(totals["savings_rate"]), "Net cash flow divided by income."),
        ("Budget utilization", pct(overall_utilization(budgets)), "Actual spending against configured limits for all selected calendar months."),
    ])
    metrics([
        ("Transactions", f"{totals['count']:,}", "Number of transactions matching the filters."),
        ("Suspicious transactions", f"{sum(value > 0 for value in exposure.values()):,}", "Distinct selected transactions linked to active review flags."),
        ("Financial risk score", score(risk_score(exposure)), "Exposure to active audit findings in this selection."),
    ])
    if not selected:
        st.info("No transactions match this selection. Add or import transactions from the Transactions page.")
        return

    data = chart_data(trend, ("income", "expenses", "net", "balance"))
    category_data = pd.DataFrame([(name, float(value)) for name, value in expense_categories(selected)],
                                 columns=["Category", "Expenses"])
    left, right = st.columns([3, 2])
    with left, st.container(border=True):
        st.subheader("Income vs. expenses")
        figure = go.Figure()
        figure.add_bar(x=data["month"], y=data["income"], name="Income", marker_color=TEAL)
        figure.add_bar(x=data["month"], y=data["expenses"], name="Expenses", marker_color=CORAL)
        plot(figure, key="dashboard-cash", y_label=currency)
    with right, st.container(border=True):
        st.subheader("Expense mix")
        if category_data.empty:
            st.caption("No expenses in this selection.")
        else:
            figure = px.pie(category_data, names="Category", values="Expenses", hole=0.62, color_discrete_sequence=PALETTE)
            plot(figure, key="dashboard-mix")
    left, right = st.columns([3, 2])
    with left, st.container(border=True):
        st.subheader("Monthly balance trend")
        figure = go.Figure(go.Scatter(x=data["month"], y=data["balance"], mode="lines+markers",
                                      fill="tozeroy", line=dict(color=BLUE), name="Balance"))
        plot(figure, key="dashboard-balance", y_label=currency)
    with right, st.container(border=True):
        st.subheader("Top five expense categories")
        if category_data.empty:
            st.caption("No expenses in this selection.")
        else:
            figure = px.bar(category_data.head(5).iloc[::-1], x="Expenses", y="Category", orientation="h",
                            color_discrete_sequence=[TEAL], labels={"Expenses": currency, "Category": ""})
            plot(figure, key="dashboard-top")
    with st.container(border=True):
        st.subheader("Financial performance")
        figure = go.Figure(go.Bar(x=data["month"], y=data["net"], name="Net cash flow",
                                  marker_color=[TEAL if value >= 0 else CORAL for value in data["net"]]))
        plot(figure, key="dashboard-net", y_label=currency)
