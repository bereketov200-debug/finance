"""Financial health indicators and data-driven review suggestions."""

import plotly.graph_objects as go
import streamlit as st

from modules.budgets import performance
from modules.finance import financial_health, monthly
from modules.transactions import filter_transactions
from .common import CORAL, TEAL, chart_data, date_filter, heading, metrics, money, pct, plot, score


def render(store, rows, limits, config, reviews):
    currency = config["currency"]
    heading("06 / Financial health", "Financial Health", "Assess how much income you retain and how closely you follow your budgets.")
    with st.container(border=True):
        start, end = date_filter(rows, config, "health")
    selected = filter_transactions(rows, start, end)
    trend = monthly(selected, start, end)
    budget_rows = performance(rows, limits, start[:7], end[:7])
    result = financial_health(selected, trend, budget_rows)
    metrics([
        ("Financial health score", score(result["health_score"]), "Based on savings and budget adherence."),
        ("Savings rate", pct(result["savings_rate"]), "Net cash flow as a percentage of income."),
        ("Expense-to-income ratio", pct(result["expense_ratio"]), "Expenses as a percentage of income."),
    ])
    metrics([
        ("Net cash flow", money(result["net"], currency), "Income minus expenses for the selected dates."),
        ("Average monthly expenses", money(result["average_monthly_expenses"], currency), "Expenses divided by the number of selected calendar months, including zero-spend months."),
        ("Budget adherence", pct(result["budget_adherence"]), "Share of configured category-month limits met. Uses full calendar months."),
    ])
    chart, guidance = st.columns([3, 2])
    with chart, st.container(border=True):
        st.subheader("Monthly spending trend")
        data = chart_data(trend, ("expenses", "income"))
        figure = go.Figure()
        figure.add_scatter(x=data["month"], y=data["income"], mode="lines+markers", name="Income",
                           line=dict(color=TEAL))
        figure.add_scatter(x=data["month"], y=data["expenses"], mode="lines+markers", name="Expenses",
                           line=dict(color=CORAL))
        plot(figure, key="health-trend", y_label=currency)
    with guidance, st.container(border=True):
        st.subheader("What to review")
        for recommendation in result["recommendations"]:
            st.write(f"• {recommendation}")
    with st.expander("Health score methodology"):
        st.write("Divide the savings rate by the 20% reference rate and clamp the result to 0–1. "
                 "Multiply that factor by 60 and add 40% of the budget adherence percentage. "
                 "Without configured budgets, the savings factor carries all 100 points. "
                 "The savings factor is zero when income is zero. Empty transaction selections have no score.")
