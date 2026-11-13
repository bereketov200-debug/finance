"""Monthly category limits and actual-spend comparisons."""

from collections import defaultdict
from decimal import Decimal

from .finance import percent
from .models import ZERO, budget


def save_limit(store, month, category, limit):
    item = budget({"month": month, "category": category, "limit": limit})
    store.update("budgets", lambda rows: [
        row for row in rows if (row["month"], row["category"]) != (month, category)
    ] + [item])


def remove_limit(store, month, category):
    store.update("budgets", lambda rows: [
        row for row in rows if (row["month"], row["category"]) != (month, category)
    ])


def performance(rows, limits, start_month=None, end_month=None, categories=()):
    totals = defaultdict(lambda: ZERO)
    for row in rows:
        if row["type"] == "Expense":
            totals[row["date"][:7], row["category"]] += Decimal(row["amount"])
    result = []
    for limit in sorted(limits, key=lambda row: (row["month"], row["category"])):
        month, category = limit["month"], limit["category"]
        if ((start_month and month < start_month) or (end_month and month > end_month)
                or (categories and category not in categories)):
            continue
        planned, actual = Decimal(limit["limit"]), totals[month, category]
        utilization = percent(actual, planned)
        status = ("Exceeded" if actual > planned else "At limit" if actual == planned
                  else "Watch" if utilization >= 80 else "Within limit")
        result.append({
            "month": month, "category": category, "limit": planned, "actual": actual,
            "remaining": planned - actual, "utilization": utilization, "status": status,
        })
    return result


def overall_utilization(rows):
    return percent(sum(row["actual"] for row in rows), sum(row["limit"] for row in rows))
