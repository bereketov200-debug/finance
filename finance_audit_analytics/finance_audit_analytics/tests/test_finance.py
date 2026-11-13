from datetime import date
from decimal import Decimal

from modules.budgets import overall_utilization, performance
from modules.finance import financial_health, monthly, summarize
from modules.forecasting import forecast_expenses


def test_financial_totals_and_closing_balance_use_exact_decimals(item):
    rows = [
        item("salary", type="Income", category="Salary", amount="400.20"),
        item("food", amount="100.10"),
        item("food2", amount="100.10", date="2026-12-01"),
    ]
    totals = summarize(rows)
    assert totals["net"] == Decimal("200.00")
    assert totals["savings_rate"] == 100 * Decimal("200.00") / Decimal("400.20")
    trend = monthly(rows, "2026-10-01", "2026-12-31", Decimal("20.50"))
    assert [row["net"] for row in trend] == [Decimal("300.10"), 0, Decimal("-100.10")]
    assert trend[-1]["balance"] == Decimal("220.50")


def test_budget_utilization_boundaries_and_full_month(item):
    rows = [item("food", amount="80"), item("shop", category="Shopping", amount="100"),
            item("edu", category="Education", amount="125"), item("salary", type="Income", category="Other", amount="200")]
    limits = [{"month": "2026-10", "category": category, "limit": "100"}
              for category in ("Food", "Shopping", "Education", "Utilities")]
    result = performance(rows, limits, "2026-10", "2026-10")
    assert {row["category"]: row["status"] for row in result} == {
        "Food": "Watch", "Shopping": "At limit", "Education": "Exceeded", "Utilities": "Within limit",
    }
    assert overall_utilization(result) == Decimal("76.25")


def test_health_score_combines_savings_and_adherence(item):
    rows = [item("income", type="Income", category="Salary", amount="100"),
            item("expense", amount="90")]
    trend = monthly(rows, "2026-09-01", "2026-10-31")
    budgets = [{"limit": Decimal("100"), "actual": Decimal("90")},
               {"limit": Decimal("5"), "actual": Decimal("6")}]
    metrics = financial_health(rows, trend, budgets)
    assert metrics["expense_ratio"] == 90
    assert metrics["average_monthly_expenses"] == 45
    assert metrics["budget_adherence"] == 50
    assert metrics["health_score"] == 50


def test_empty_and_zero_income(item):
    assert summarize([])["net"] == 0
    assert summarize([])["savings_rate"] is None
    assert summarize([item()])["expense_ratio"] is None
    assert financial_health([], [], [])["health_score"] is None
    assert overall_utilization([]) is None
    assert forecast_expenses([], date(2026, 11, 1)) == ([], "2026-12", None)


def test_weighted_forecast_excludes_partial_and_current_months(item):
    rows = [item(str(month), date=f"2026-{month:02d}-03", amount=str(value))
            for month, value in ((6, 999), (7, 100), (8, 200), (9, 300), (10, 999))]
    history, target, forecast = forecast_expenses(rows, date(2026, 10, 15))
    assert [entry["month"] for entry in history] == ["2026-07", "2026-08", "2026-09"]
    assert target == "2026-11"
    assert forecast == Decimal("233.33")
    assert forecast_expenses(rows[-2:], date(2026, 10, 15))[2] is None
