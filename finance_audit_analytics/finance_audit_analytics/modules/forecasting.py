"""Weighted moving-average forecast using completed calendar months."""

from datetime import date

from .finance import monthly, rounded, shift_month


def forecast_expenses(rows, today=None):
    today = today or date.today()
    current = today.isoformat()[:7]
    next_month = shift_month(current, 1) if current != "9999-12" else None
    complete = [row for row in rows if row["date"][:7] < current]
    if not complete:
        return [], next_month, None
    # The first observed month may contain only part of a month.
    start = shift_month(min(row["date"][:7] for row in complete), 1)
    history = monthly(complete, start + "-01", current + "-01")[:-1]
    recent = history[-3:]
    if next_month is None or len(recent) < 3 or sum(item["expenses"] > 0 for item in recent) < 2:
        return history, next_month, None
    estimate = sum(weight * item["expenses"] for weight, item in enumerate(recent, 1)) / 6
    return history, next_month, rounded(estimate)
