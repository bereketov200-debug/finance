"""Financial aggregation, reporting periods, and health indicators."""

from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .models import CENT, ZERO


def month_index(month):
    year, number = map(int, month.split("-"))
    return (year - 1) * 12 + number - 1


def shift_month(month, offset):
    year, number = divmod(month_index(month) + offset, 12)
    if not 0 <= year < 9999:
        raise ValueError("Resulting month is outside the supported date range.")
    return f"{year + 1:04d}-{number + 1:02d}"


def months_between(start, end):
    start = start[:7]
    return [shift_month(start, offset) for offset in range(month_index(end[:7]) - month_index(start) + 1)]


def month_end(month):
    year, number = map(int, month.split("-"))
    return f"{month}-{monthrange(year, number)[1]:02d}"


def reporting_window(rows, period, today=None):
    today = today or date.today()
    end = today.isoformat()
    current = end[:7]
    if period == "All records":
        days = [row["date"] for row in rows]
        return (min(days), max(days)) if days else (current + "-01", end)
    offset = {"This month": 0, "Last 3 months": -2, "Last 12 months": -11}[period]
    return shift_month(current, offset) + "-01", end


def percent(numerator, denominator):
    return Decimal(100) * numerator / denominator if denominator else None


def rounded(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP) if value is not None else None


def summarize(rows):
    totals = {"Income": ZERO, "Expense": ZERO}
    for row in rows:
        totals[row["type"]] += Decimal(row["amount"])
    income, expenses = totals["Income"], totals["Expense"]
    net = income - expenses
    return {
        "income": income, "expenses": expenses, "net": net, "count": len(rows),
        "savings_rate": percent(net, income), "expense_ratio": percent(expenses, income),
    }


def monthly(rows, start, end, opening=ZERO):
    groups = defaultdict(list)
    for row in rows:
        if start <= row["date"] <= end:
            groups[row["date"][:7]].append(row)
    result, balance = [], opening
    for month in months_between(start, end):
        totals = summarize(groups[month])
        balance += totals["net"]
        result.append({"month": month, **totals, "balance": balance})
    return result


def expense_categories(rows):
    totals = defaultdict(lambda: ZERO)
    for row in rows:
        if row["type"] == "Expense":
            totals[row["category"]] += Decimal(row["amount"])
    return sorted(totals.items(), key=lambda item: (-item[1], item[0]))


def financial_health(rows, month_totals, budget_rows):
    metrics = summarize(rows)
    adherence = percent(sum(row["actual"] <= row["limit"] for row in budget_rows), len(budget_rows))
    savings = metrics["savings_rate"]
    savings_component = max(ZERO, min(Decimal(1), (savings or ZERO) / 20))
    score = None
    if rows:
        score = (100 * savings_component if adherence is None else
                 60 * savings_component + Decimal("0.40") * adherence)
    recommendations = []
    if not rows:
        recommendations.append("Add or import transactions to calculate a financial health score.")
    elif metrics["income"] == 0:
        recommendations.append("Verify that income is recorded for this period before interpreting ratios.")
    elif metrics["net"] < 0:
        recommendations.append("Recorded expenses exceeded income. Review the highest spending categories.")
    elif savings < 20:
        recommendations.append("Savings fell below the model’s 20% reference point. Review recurring expenses.")
    else:
        recommendations.append("Savings met the model’s 20% reference point. Track whether this persists across months.")
    if adherence is None and rows:
        recommendations.append("Set monthly category budgets to measure adherence.")
    elif adherence is not None and adherence < 100:
        recommendations.append("Review over-limit categories and check whether recurring costs changed.")
    return {
        **metrics, "average_monthly_expenses": rounded(metrics["expenses"] / len(month_totals)) if month_totals else ZERO,
        "budget_adherence": adherence, "health_score": rounded(score), "recommendations": recommendations,
    }
