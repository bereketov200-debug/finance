"""Severity-based exposure score for active findings."""

from decimal import Decimal, ROUND_HALF_UP


WEIGHTS = {"Low": 10, "Medium": 25, "High": 55, "Critical": 100}
ACTIVE = ("Open", "Under Review")
FORMULA = (
    "Assign each selected transaction its highest active severity weight (Low 10, Medium 25, High 55, "
    "Critical 100). Use zero for unflagged transactions. The score is 60% of the largest weight plus "
    "40% of the mean weight across all selected transactions, rounded to the nearest whole number. "
    "Only Open and Under Review findings contribute. An empty selection scores 0."
)


def transaction_exposure(findings, transaction_ids):
    weights = dict.fromkeys(transaction_ids, 0)
    for finding in findings:
        if finding["status"] in ACTIVE:
            weight = WEIGHTS[finding["severity"]]
            for identifier in finding["transaction_ids"]:
                if identifier in weights:
                    weights[identifier] = max(weights[identifier], weight)
    return weights


def risk_score(weights):
    if not weights:
        return 0
    maximum = max(weights.values())
    mean = Decimal(sum(weights.values())) / len(weights)
    return int((Decimal("0.60") * maximum + Decimal("0.40") * mean).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    ))
