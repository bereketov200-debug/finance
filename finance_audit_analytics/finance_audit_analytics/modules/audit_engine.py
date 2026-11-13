"""Deterministic review signals evaluated against the complete saved ledger."""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import date
from decimal import Decimal
from hashlib import sha256
from itertools import groupby

from .budgets import performance
from .models import now, review


RULES = {
    "Large transaction": "Verify the authorization and supporting documents.",
    "Duplicate transaction": "Compare invoices, bank entries, and any reversal or refund.",
    "Missing receipt": "Request the receipt or document the applicable exception.",
    "Budget violation": "Reconcile the category and record the reason for the overage.",
    "Unusual expense": "Compare with prior purchases and verify the invoice and category.",
    "Possible transaction splitting": "Check related invoices and the approval policy for the combined amount.",
    "Suspicious frequency": "Reconcile the burst with the counterparty's normal billing schedule.",
}


def normalize(value):
    return " ".join(value.casefold().split())


def criteria(config):
    sensitivity = config["sensitivity"]
    adjustment = {"Sensitive": -1, "Standard": 0, "Conservative": 1}[sensitivity]
    return {
        "unusual_factor": max(Decimal("1.25"), Decimal(config["unusual_multiplier"]) + Decimal("0.5") * adjustment),
        "split_count": max(2, config["split_count"] + adjustment),
        "frequency_count": max(3, config["frequency_count"] + 2 * adjustment),
        "frequency_factor": 3 + adjustment,
    }


def rule_descriptions(config, currency):
    c = criteria(config)
    return {
        "Large transaction": f"Income or expense strictly above {config['large_threshold']} {currency}. Critical at twice that threshold.",
        "Duplicate transaction": "Same type, date, amount, counterparty and description. Case and extra whitespace are ignored.",
        "Missing receipt": f"Expense at or above {config['receipt_minimum']} {currency} with neither receipt confirmation nor a reference.",
        "Budget violation": "Total category expenses strictly exceed the saved limit for the calendar month.",
        "Unusual expense": f"At least {config['unusual_minimum']} {currency} and above {c['unusual_factor']}× the average of up to 20 earlier expenses in the same category. Requires {config['history_count']} prior expenses from earlier dates. When there are at least five, the highest and lowest are dropped.",
        "Possible transaction splitting": f"At least {c['split_count']} distinct expenses to the same counterparty in one category within {config['split_days']} elapsed days. Each is at least {config['split_min_share']}% of the approval threshold and below it. Their combined amount reaches the threshold.",
        "Suspicious frequency": f"At least {c['frequency_count']} distinct expenses to one counterparty in a {config['frequency_days']}-day window, at or above {c['frequency_factor']}× its average in equally sized windows across the preceding {config['frequency_history_weeks']} weeks (whole windows only). Requires earlier payments to that counterparty and ledger coverage of the baseline.",
    }


def run_audit(rows, limits, config, reviews=()):
    """Produce findings with stable IDs based on rule and transaction evidence."""
    findings = []
    review_by_id = {item["finding_id"]: item for item in reviews}

    def flag(rule, severity, evidence, explanation):
        ids = sorted(row["id"] for row in evidence)
        digest = sha256("|".join([rule, *ids]).encode()).hexdigest()[:24]
        identifier = f"AF-{digest}"
        previous = review_by_id.get(identifier, {})
        findings.append({
            "finding_id": identifier, "transaction_ids": ids, "rule": rule,
            "severity": severity, "date": max(row["date"] for row in evidence),
            "explanation": explanation, "recommended_action": RULES[rule],
            "status": previous.get("status", "Open"), "notes": previous.get("notes", ""),
            "review_updated_at": previous.get("updated_at", ""),
        })

    threshold = Decimal(config["large_threshold"])
    receipt_floor = Decimal(config["receipt_minimum"])
    unusual_floor = Decimal(config["unusual_minimum"])
    tuning = criteria(config)
    duplicates = defaultdict(list)
    ordered = sorted(rows, key=lambda row: (row["date"], row["created_at"], row["id"]))
    expenses = defaultdict(list)
    for row in ordered:
        value = Decimal(row["amount"])
        if value > threshold:
            flag("Large transaction", "Critical" if value >= 2 * threshold else "High", [row],
                 f"Amount {value:,.2f} exceeds the configured threshold of {threshold:,.2f}.")
        duplicates[(row["type"], row["date"], value, normalize(row["counterparty"]),
                    normalize(row["description"]))].append(row)
        if row["type"] == "Expense":
            expenses[row["date"][:7], row["category"]].append(row)
            if value >= receipt_floor and not row["has_receipt"]:
                flag("Missing receipt", "Low", [row], "No receipt confirmation or reference was recorded.")

    duplicate_copies = set()
    for group in duplicates.values():
        if len(group) > 1:
            flag("Duplicate transaction", "High", group,
                 f"{len(group)} transactions have the same type, date, amount, counterparty and description.")
            duplicate_copies.update(row["id"] for row in group[1:])

    for row in performance(rows, limits):
        if row["actual"] > row["limit"]:
            flag("Budget violation", "High" if row["utilization"] >= 150 else "Medium",
                 expenses[row["month"], row["category"]],
                 f"{row['category']} spending for {row['month']} was {row['actual']:,.2f} against a limit of {row['limit']:,.2f} ({row['utilization']:.1f}%).")

    history = defaultdict(list)
    split_groups = defaultdict(list)
    counterparties = defaultdict(list)
    eligible = [row for row in ordered if row["type"] == "Expense" and row["id"] not in duplicate_copies]
    for _, same_day in groupby(eligible, key=lambda row: row["date"]):
        day_rows = list(same_day)
        for row in day_rows:
            category, value = row["category"], Decimal(row["amount"])
            prior = history[category][-max(20, config["history_count"]):]
            if len(prior) >= config["history_count"] and value >= unusual_floor:
                baseline = sorted(prior[-20:])
                if len(baseline) >= 5:
                    baseline = baseline[1:-1]
                average = sum(baseline) / len(baseline)
                if value > tuning["unusual_factor"] * average:
                    flag("Unusual expense", "Medium", [row],
                         f"Amount {value:,.2f} was {value / average:.1f}× the {category} reference average of {average:,.2f}.")
            counterparty = normalize(row["counterparty"])
            counterparties[counterparty].append(row)
            if threshold * config["split_min_share"] / 100 <= value < threshold:
                split_groups[counterparty, category].append(row)
        for row in day_rows:
            history[row["category"]].append(Decimal(row["amount"]))

    for group in split_groups.values():
        for evidence in qualifying_windows(
            group, config["split_days"], tuning["split_count"],
            lambda items, _: sum(Decimal(row["amount"]) for row in items) >= threshold,
        ):
            combined = sum(Decimal(row["amount"]) for row in evidence)
            flag("Possible transaction splitting", "High", evidence,
                 f"{len(evidence)} individually below-threshold expenses totaled {combined:,.2f} for one counterparty and category.")

    if ordered:
        first_day = day_number(ordered[0])
        window = config["frequency_days"]
        baseline_windows = 7 * config["frequency_history_weeks"] // window
        for group in counterparties.values():
            days = [day_number(row) for row in group]

            def above_baseline(items, start):
                before = start - baseline_windows * window
                count = bisect_left(days, start) - bisect_left(days, before)
                return (before >= first_day and count > 0
                        and len(items) * baseline_windows >= tuning["frequency_factor"] * count)

            for evidence in qualifying_windows(group, window - 1, tuning["frequency_count"], above_baseline):
                flag("Suspicious frequency", "Medium", evidence,
                     f"{len(evidence)} expenses to one counterparty in {window} calendar days met the configured frequency test.")

    return sorted(findings, key=lambda row: (row["date"], row["finding_id"]), reverse=True)


def day_number(row):
    return date.fromisoformat(row["date"]).toordinal()


def qualifying_windows(group, elapsed, minimum, qualifies):
    """Scan maximal forward windows, skipping overlap after each reported group."""
    days = [day_number(row) for row in group]
    index = 0
    while index + minimum <= len(group):
        end = bisect_right(days, days[index] + elapsed, lo=index)
        if end - index >= minimum and qualifies(group[index:end], days[index]):
            yield group[index:end]
            index = end
        else:
            index = bisect_right(days, days[index], lo=index)


def findings_in_scope(findings, transaction_ids):
    ids = set(transaction_ids)
    return [item for item in findings if ids.intersection(item["transaction_ids"])]


def save_review(store, identifier, status, notes):
    item = review({"finding_id": identifier, "status": status, "notes": notes, "updated_at": now()})
    store.update("audit_reviews", lambda rows: [row for row in rows if row["finding_id"] != identifier] + [item])
