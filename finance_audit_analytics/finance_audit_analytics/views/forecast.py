"""Next-month expense estimate and historical spending chart."""

import plotly.graph_objects as go
import streamlit as st

from modules.forecasting import forecast_expenses
from .common import BLUE, TEAL, heading, metrics, money, plot


def render(store, rows, limits, config, reviews):
    currency = config["currency"]
    heading("07 / Planning", "Expense Forecast", "Estimate next month’s spending from completed months in the ledger.")
    history, next_month, estimate = forecast_expenses(rows)
    metrics([
        ("Next forecast month", next_month or "—", "The calendar month after the current month."),
        ("Estimated expenses", money(estimate, currency), "Weighted average of the three most recent completed months."),
        ("Historical months", str(len(history)), "Completed months after the first observed ledger month."),
    ])
    if estimate is None:
        st.warning("Insufficient recent history. The model needs three completed months after the first recorded month, with expenses in at least two of those three months.")
    if history:
        with st.container(border=True):
            st.subheader("Historical expenses and forecast")
            figure = go.Figure(go.Scatter(x=[row["month"] + "-01" for row in history],
                                          y=[float(row["expenses"]) for row in history],
                                          mode="lines+markers", name="Recorded expenses", line=dict(color=TEAL)))
            if estimate is not None:
                figure.add_scatter(x=[next_month + "-01"], y=[float(estimate)], mode="markers",
                                   marker=dict(size=14, symbol="diamond", color=BLUE), name="Next-month estimate")
            figure.update_xaxes(type="date", tickformat="%b %Y")
            plot(figure, key="forecast-history", y_label=currency)
    with st.expander("Forecast methodology", expanded=True):
        st.write("Use the latest three completed calendar months, weighting them 1, 2, and 3 from oldest to newest. "
                 "Divide the weighted total by 6. Months with no recorded expenses contribute zero. "
                 "Exclude the first observed month because its coverage may be partial, and exclude the current month.")
        st.caption("This estimate can change as records are added. Seasonal changes and one-off expenses can affect its accuracy.")
