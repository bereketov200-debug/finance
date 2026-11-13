"""Timestamped, spreadsheet-friendly CSV exports."""

import csv
import io
from decimal import Decimal

from .finance import rounded
from .models import now
from .transactions import TEXT_COLUMNS, TEXT_ENCODING, TRANSACTION_COLUMNS, guard_csv


MONTH_COLUMNS = ("month", "income", "expenses", "net", "balance", "count", "savings_rate", "expense_ratio")
BUDGET_COLUMNS = ("month", "category", "limit", "actual", "remaining", "utilization", "status")
AUDIT_COLUMNS = ("finding_id", "date", "rule", "severity", "transaction_ids", "explanation",
                 "recommended_action", "status", "notes", "review_updated_at")
HEALTH_COLUMNS = ("income", "expenses", "net", "count", "savings_rate", "expense_ratio",
                  "average_monthly_expenses", "budget_adherence", "health_score", "recommendations")


def cell(value):
    if isinstance(value, Decimal):
        return format(rounded(value), "f")
    if isinstance(value, list):
        return guard_csv(" | ".join(value))
    return guard_csv(value)


def csv_report(rows, columns, *, start="", end="", currency="", generated_at=None):
    metadata = {"period_start": start, "period_end": end, "currency": currency,
                "generated_at": generated_at or now()}
    transaction_report = columns == TRANSACTION_COLUMNS
    if transaction_report:
        metadata["csv_text_encoding"] = TEXT_ENCODING
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([*columns, *metadata])
    for row in rows:
        values = [cell(row.get(key)) for key in columns]
        writer.writerow([*values, *metadata.values()])
    if not rows and not transaction_report:
        writer.writerow([""] * len(columns) + list(metadata.values()))
    return output.getvalue().encode("utf-8-sig")


def csv_template():
    return (",".join(TRANSACTION_COLUMNS) + "\n"
            ",2026-01-15,Expense,Food,4200.00,Example lunch,Card,Fictional Cafe,true,DEMO-001,\n").encode("utf-8-sig")
