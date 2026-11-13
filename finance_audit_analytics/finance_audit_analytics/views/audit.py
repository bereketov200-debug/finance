"""Audit review queue and risk reporting."""

from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.audit_engine import findings_in_scope, rule_descriptions, run_audit, save_review
from modules.finance import months_between
from modules.models import SEVERITIES, STATUSES
from modules.risk_scoring import ACTIVE, FORMULA, WEIGHTS, risk_score, transaction_exposure
from modules.transactions import filter_transactions
from .common import BLUE, CORAL, GOLD, TEAL, commit, date_filter, heading, metrics, plot, score


COLORS = dict(zip(SEVERITIES, (TEAL, GOLD, CORAL, "#D791F6")))


def scoped(rows, limits, config, reviews, start, end):
    ids = [row["id"] for row in filter_transactions(rows, start, end)]
    return ids, findings_in_scope(run_audit(rows, limits, config, reviews), ids)


def review_page(store, rows, limits, config, reviews):
    heading("04 / Automated audit", "Audit Review", "Review the evidence, record a decision, and track follow-up.")
    st.info("Audit flags indicate potential risks that require manual review.")
    with st.expander("Detection criteria"):
        for rule, detail in rule_descriptions(config, config["currency"]).items():
            st.markdown(f"**{rule}**")
            st.write(detail)
    with st.container(border=True):
        left, center, right = st.columns(3)
        with left:
            start, end = date_filter(rows, config, "audit-review")
        statuses = center.multiselect("Review status", STATUSES, placeholder="All statuses")
        severities = right.multiselect("Severity", SEVERITIES, placeholder="All severities")
    _, all_findings = scoped(rows, limits, config, reviews, start, end)
    findings = [item for item in all_findings if (not statuses or item["status"] in statuses)
                and (not severities or item["severity"] in severities)]
    st.caption(f"{len(findings):,} findings match. Findings may include related evidence outside the dates.")
    if not findings:
        st.info("No findings match the current selection.")
        return
    summary = [{key: item[key] for key in ("date", "rule", "severity", "status", "finding_id")} for item in findings]
    st.dataframe(pd.DataFrame(summary), hide_index=True, width="stretch")
    indexed = {item["finding_id"]: item for item in findings}

    def label(identifier):
        item = indexed[identifier]
        return f"{item['date']} · {item['severity']} · {item['rule']} · {identifier[3:11]}"

    identifier = st.selectbox("Choose finding to review", list(indexed), format_func=label)
    item = indexed[identifier]
    with st.container(border=True):
        st.subheader(item["rule"])
        st.caption(f"{item['severity']} severity · {item['status']} · {identifier}")
        st.write(item["explanation"])
        st.markdown("**Recommended action**")
        st.write(item["recommended_action"])
        with st.expander(f"Evidence · {len(item['transaction_ids'])} transactions"):
            identifiers = set(item["transaction_ids"])
            evidence = [{key: row[key] for key in ("id", "date", "counterparty", "amount", "description", "has_receipt")}
                        for row in rows if row["id"] in identifiers]
            st.dataframe(pd.DataFrame(evidence), hide_index=True, width="stretch")
        with st.form(f"review-{identifier}"):
            status = st.selectbox("Update review status", STATUSES, index=STATUSES.index(item["status"]))
            notes = st.text_area("Review notes", item["notes"], max_chars=2000)
            if item["review_updated_at"]:
                st.caption(f"Last saved · {item['review_updated_at']}")
            if st.form_submit_button("Save review", type="primary"):
                commit(lambda: save_review(store, identifier, status, notes), "Audit review saved.")


def dashboard_page(store, rows, limits, config, reviews):
    heading("05 / Risk monitoring", "Audit Dashboard", "Track active exposure, rule activity, and review coverage.")
    with st.container(border=True):
        start, end = date_filter(rows, config, "audit-dashboard")
    ids, findings = scoped(rows, limits, config, reviews, start, end)
    active = [item for item in findings if item["status"] in ACTIVE]
    weights = transaction_exposure(active, ids)
    metrics([
        ("Total audit findings", f"{len(findings):,}", "Findings touching at least one selected transaction."),
        ("High-risk findings", f"{sum(item['severity'] in ('High', 'Critical') for item in active):,}",
         "Active High and Critical findings."),
        ("Audit risk score", score(risk_score(weights)), "Risk exposure from open and under-review findings."),
    ])
    with st.expander("How the audit risk score is calculated"):
        st.write(FORMULA)
        st.caption("This deterministic indicator describes configured rule exposure. It is neither a probability nor a conclusion about fraud.")

    by_severity = Counter(item["severity"] for item in findings)
    by_rule = Counter(item["rule"] for item in findings)
    severity = pd.DataFrame({"Severity": SEVERITIES, "Findings": [by_severity[level] for level in SEVERITIES]})
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("Findings by severity")
        plot(px.bar(severity, x="Severity", y="Findings", color="Severity", color_discrete_map=COLORS)
             .update_layout(showlegend=False), key="audit-severity")
    with right, st.container(border=True):
        st.subheader("Most triggered rules")
        if by_rule:
            data = pd.DataFrame(by_rule.most_common()[::-1], columns=["Rule", "Findings"])
            plot(px.bar(data, x="Findings", y="Rule", orientation="h", color_discrete_sequence=[BLUE]), key="audit-rules")
        else:
            st.caption("No rules triggered for the selection.")
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("Transaction risk distribution")
        risk = Counter(weights.values())
        severity_weights = [WEIGHTS[level] for level in SEVERITIES]
        distribution = pd.DataFrame({"Risk": ["Unflagged", *SEVERITIES],
                                     "Transactions": [risk[value] for value in (0, *severity_weights)]})
        if weights:
            plot(px.pie(distribution, names="Risk", values="Transactions", color="Risk", hole=0.62,
                        color_discrete_map={"Unflagged": BLUE, **COLORS}), key="audit-distribution")
        else:
            st.caption("There are no transactions in this selection.")
    with right, st.container(border=True):
        st.subheader("Findings over time")
        by_month = Counter(item["date"][:7] for item in findings if start <= item["date"] <= end)
        months = months_between(start, end)
        data = pd.DataFrame({"Month": months, "Findings": [by_month[month] for month in months]})
        plot(px.line(data, x="Month", y="Findings", markers=True, color_discrete_sequence=[TEAL]), key="audit-timeline")
        st.caption("Grouped by the latest related transaction date within the selected dates.")
