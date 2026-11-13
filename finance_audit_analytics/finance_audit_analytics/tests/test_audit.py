from datetime import date

from demo_data import make_demo
from modules.audit_engine import RULES, run_audit, save_review
from modules.models import DEFAULT_SETTINGS, transaction
from modules.risk_scoring import risk_score, transaction_exposure
from modules.storage import Store


def test_duplicate_normalization_and_type_guard(item):
    rows = [item("one"), item("two", description=" GROCERIES ", counterparty="Fictional  market"),
            item("income", type="Income", category="Other")]
    findings = run_audit(rows, [], DEFAULT_SETTINGS)
    assert len(findings) == 1
    assert findings[0]["rule"] == "Duplicate transaction"
    assert findings[0]["transaction_ids"] == ["one", "two"]
    assert findings == run_audit(list(reversed(rows)), [], DEFAULT_SETTINGS)


def test_large_and_missing_receipt_boundaries(item):
    rows = [
        item("equal", amount="300000", description="Threshold equality"),
        item("high", amount="300000.01"),
        item("critical", amount="600000"),
        item("missing", amount="5000", has_receipt=False),
        item("low", amount="4999.99", has_receipt=False),
        item("ref", amount="5000", description="Separate purchase", has_receipt=False, receipt_reference="R-123"),
        item("income", type="Income", category="Salary", amount="5000", has_receipt=False),
    ]
    findings = run_audit(rows, [], DEFAULT_SETTINGS)
    assert {(entry["rule"], entry["severity"], entry["transaction_ids"][0]) for entry in findings} == {
        ("Large transaction", "High", "high"), ("Large transaction", "Critical", "critical"),
        ("Missing receipt", "Low", "missing"),
    }


def test_risk_weights_deduplicate_evidence_and_exclude_closed_findings():
    findings = [
        {"transaction_ids": ["a", "b"], "severity": "Low", "status": "Open"},
        {"transaction_ids": ["a"], "severity": "High", "status": "Under Review"},
        {"transaction_ids": ["c"], "severity": "Critical", "status": "Resolved"},
        {"transaction_ids": ["b"], "severity": "Critical", "status": "False Positive"},
    ]
    weights = transaction_exposure(findings, ["a", "b", "c"])
    assert weights == {"a": 55, "b": 10, "c": 0}
    assert risk_score(weights) == 42
    assert risk_score({}) == 0
    assert risk_score({"a": 100}) == 100


def test_review_status_and_notes_survive_restart(store, item):
    rows = [item(amount="350000")]
    identifier = run_audit(rows, [], DEFAULT_SETTINGS)[0]["finding_id"]
    save_review(store, identifier, "Resolved", "Approval verified.")
    resumed = Store(store.root)
    result = run_audit(rows, [], DEFAULT_SETTINGS, resumed.read("audit_reviews"))[0]
    assert result["finding_id"] == identifier
    assert result["status"] == "Resolved"
    assert result["notes"] == "Approval verified."
    assert risk_score(transaction_exposure([result], ["tx-1"])) == 0


def test_demo_triggers_all_rules_and_is_reproducible():
    rows, limits = make_demo("2026-11")
    assert (rows, limits) == make_demo("2026-11")
    assert len(rows) >= 150
    assert len({date.fromisoformat(row["date"]).month for row in rows}) == 9
    findings = run_audit([transaction(row) for row in rows], limits, DEFAULT_SETTINGS)
    assert {item["rule"] for item in findings} == set(RULES)


def test_same_day_expenses_do_not_supply_unusual_expense_baseline(item):
    rows = [item(str(i), description=f"Different item {i}") for i in range(6)]
    rows.append(item("spike", amount="50000"))
    assert "Unusual expense" not in {entry["rule"] for entry in run_audit(rows, [], DEFAULT_SETTINGS)}
