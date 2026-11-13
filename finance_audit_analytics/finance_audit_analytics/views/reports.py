"""Date-scoped CSV report downloads."""

import streamlit as st

from modules.audit_engine import findings_in_scope, run_audit
from modules.budgets import performance
from modules.finance import financial_health, monthly, summarize
from modules.models import now
from modules.reports import AUDIT_COLUMNS, BUDGET_COLUMNS, HEALTH_COLUMNS, MONTH_COLUMNS, csv_report
from modules.transactions import TRANSACTION_COLUMNS, filter_transactions
from .common import date_filter, heading


def render(store, rows, limits, config, reviews):
    heading("08 / Export center", "Reports", "Download CSV snapshots with a reporting period, currency, and UTC generation timestamp.")
    with st.container(border=True):
        start, end = date_filter(rows, config, "reports")
    selected = filter_transactions(rows, start, end)
    opening = summarize([row for row in rows if row["date"] < start])["net"]
    months = monthly(selected, start, end, opening)
    budgets = performance(rows, limits, start[:7], end[:7])
    findings = findings_in_scope(run_audit(rows, limits, config, reviews), (row["id"] for row in selected))
    health = financial_health(selected, months, budgets)
    stamp = now()
    catalog = [
        ("Monthly financial report", "Income, expenses, net cash flow, and closing ledger balance by month.",
         months, MONTH_COLUMNS, "monthly_finance"),
        ("Transaction report", "Individual ledger entries in the selected dates. Can be imported into another ledger.",
         selected, TRANSACTION_COLUMNS, "transactions"),
        ("Budget performance", "Full calendar-month comparisons for every saved limit in the selected months.",
         budgets, BUDGET_COLUMNS, "budget_performance"),
        ("Audit findings", "Findings linked to selected transactions, with evidence IDs and review notes.",
         findings, AUDIT_COLUMNS, "audit_findings"),
        ("Financial health summary", "Savings, spending ratios, budget adherence, and recommendations.",
         [health], HEALTH_COLUMNS, "financial_health"),
    ]
    for title, description, data, columns, filename in catalog:
        with st.container(border=True):
            details, action = st.columns([3, 1])
            with details:
                st.subheader(title)
                st.caption(description)
            action.download_button("Download CSV", csv_report(data, columns, start=start, end=end,
                                                              currency=config["currency"], generated_at=stamp),
                                   f"{filename}_{start}_{end}.csv", "text/csv", key=f"report-{filename}",
                                   disabled=columns == TRANSACTION_COLUMNS and not data)
