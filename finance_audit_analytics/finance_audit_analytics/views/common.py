"""Shared Streamlit layout, formatting, and interaction utilities."""

from datetime import date

import pandas as pd
import streamlit as st

from modules.finance import reporting_window
from modules.storage import StorageError


TEAL = "#54D6C7"
BLUE = "#79A7FF"
CORAL = "#FF8487"
GOLD = "#F7C46D"
PALETTE = (TEAL, BLUE, GOLD, CORAL, "#AD9AF5", "#68BCF3", "#8FCA86", "#E796C4")


def heading(section, title, subtitle):
    st.caption(section.upper())
    st.title(title)
    st.write(subtitle)


def date_filter(rows, config, key):
    today = date.today()
    start, end = reporting_window(rows, config["period"], today)
    available_start = min([start, today.isoformat(), *(row["date"] for row in rows)])
    available_end = max([end, today.isoformat(), *(row["date"] for row in rows)])
    # Provide room to select empty periods as well as dates already in the ledger.
    min_day = min(date.fromisoformat(available_start), today.replace(year=max(1, today.year - 5), day=1))
    max_day = max(date.fromisoformat(available_end), today.replace(year=min(9999, today.year + 2), day=28))
    selected = st.date_input("Reporting dates", (date.fromisoformat(start), date.fromisoformat(end)),
                             min_value=min_day, max_value=max_day, key=f"dates-{key}-{config['period']}",
                             format="YYYY-MM-DD")
    if len(selected) != 2:
        st.info("Select both dates to apply this filter.")
        st.stop()
    return tuple(day.isoformat() for day in selected)


def money(value, currency):
    return "—" if value is None else f"{value:,.2f} {currency}"


def pct(value):
    return "—" if value is None else f"{value:,.1f}%"


def score(value):
    return "—" if value is None else f"{value:,.0f} / 100"


def metrics(items):
    for column, (label, value, help_text) in zip(st.columns(len(items)), items):
        column.metric(label, value, help=help_text, border=True)


def plot(figure, *, key, y_label=None, x_label=None, height=310):
    figure.update_layout(
        height=height, margin=dict(l=16, r=18, t=20, b=16), colorway=PALETTE,
        legend=dict(orientation="h", y=-0.19), hovermode="closest",
    )
    if x_label:
        figure.update_xaxes(title=x_label)
    if y_label:
        figure.update_yaxes(title=y_label)
    st.plotly_chart(figure, key=key, width="stretch", config={"displaylogo": False, "responsive": True})


def chart_data(rows, fields):
    return pd.DataFrame([{**row, **{key: float(row[key]) for key in fields}} for row in rows])


def commit(action, message):
    try:
        result = action()
    except (ValueError, StorageError) as error:
        st.error(str(error))
    else:
        st.session_state["notice"] = message(result) if callable(message) else message
        st.rerun()
