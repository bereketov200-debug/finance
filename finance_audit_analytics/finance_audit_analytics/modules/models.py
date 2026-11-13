"""Canonical JSON record shapes and shared validation."""

import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation


INCOME = ("Salary", "Freelance", "Other")
EXPENSE = ("Food", "Transportation", "Shopping", "Education", "Entertainment",
           "Utilities", "Healthcare", "Other")
PAYMENTS = ("Card", "Bank transfer", "Cash", "Digital wallet", "Other")
CURRENCIES = ("KZT", "USD", "EUR", "GBP", "RUB")
PERIODS = ("All records", "This month", "Last 3 months", "Last 12 months")
STATUSES = ("Open", "Under Review", "Resolved", "False Positive")
SEVERITIES = ("Low", "Medium", "High", "Critical")
CENT = Decimal("0.01")
ZERO = Decimal("0.00")
DEFAULT_SETTINGS = {
    "currency": "KZT", "period": "All records", "sensitivity": "Standard",
    "large_threshold": "300000.00", "receipt_minimum": "5000.00",
    "unusual_minimum": "20000.00", "history_count": 5, "unusual_multiplier": "3.00",
    "split_days": 2, "split_count": 3, "split_min_share": 15,
    "frequency_days": 3, "frequency_count": 6, "frequency_history_weeks": 4,
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value, label, *, required=False, limit=240):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if (required and not value) or len(value) > limit or "\x00" in value:
        raise ValueError(f"{label} must {'contain 1 to' if required else 'contain at most'} {limit} characters.")
    return value


def amount(value, label="Amount", *, allow_zero=False):
    try:
        result = Decimal(str(value).strip())
        if not result.is_finite() or result < 0 or result > Decimal("999999999999.99"):
            raise ValueError
        if (not allow_zero and result == 0) or result != result.quantize(CENT):
            raise ValueError
    except (InvalidOperation, ValueError):
        lower = "0.00" if allow_zero else "0.01"
        raise ValueError(f"{label} must be between {lower} and 999999999999.99, with up to 2 decimals.") from None
    return result.quantize(CENT).copy_abs()


def choice(value, options, label):
    if value not in options:
        raise ValueError(f"{label} must be one of {', '.join(options)}.")
    return value


def month_key(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError("Month must use YYYY-MM.")
    return date.fromisoformat(value + "-01").isoformat()[:7]


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be ISO 8601 with a timezone.")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone.")
    try:
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    except OverflowError:
        raise ValueError("Timestamp is outside the supported UTC date range.") from None


def transaction(record):
    kind = choice(record["type"], ("Income", "Expense"), "Type")
    day = record["date"]
    if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("Date must use YYYY-MM-DD.")
    receipt = record.get("has_receipt", False)
    if not isinstance(receipt, bool):
        raise ValueError("Receipt availability must be true or false.")
    reference = clean_text(record.get("receipt_reference", ""), "Receipt reference", limit=120)
    identifier = clean_text(record["id"], "Transaction ID", required=True, limit=80)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", identifier):
        raise ValueError("Transaction ID may contain letters, digits, dots, underscores and dashes.")
    return {
        "id": identifier, "date": date.fromisoformat(day).isoformat(), "type": kind,
        "category": choice(record["category"], INCOME if kind == "Income" else EXPENSE, "Category"),
        "amount": str(amount(record["amount"])),
        "description": clean_text(record["description"], "Description", required=True),
        "payment_method": choice(record["payment_method"], PAYMENTS, "Payment method"),
        "counterparty": clean_text(record["counterparty"], "Counterparty", required=True, limit=120),
        "has_receipt": receipt or bool(reference), "receipt_reference": reference,
        "created_at": timestamp(record["created_at"]),
    }


def budget(record):
    return {
        "month": month_key(record["month"]),
        "category": choice(record["category"], EXPENSE, "Budget category"),
        "limit": str(amount(record["limit"], "Budget limit")),
    }


def review(record):
    return {
        "finding_id": clean_text(record["finding_id"], "Finding ID", required=True, limit=80),
        "status": choice(record["status"], STATUSES, "Review status"),
        "notes": clean_text(record["notes"], "Review notes", limit=2000),
        "updated_at": timestamp(record["updated_at"]),
    }


INT_SETTINGS = {
    "history_count": (3, 100), "split_days": (0, 14), "split_count": (2, 20),
    "split_min_share": (1, 99), "frequency_days": (1, 14),
    "frequency_count": (3, 100), "frequency_history_weeks": (2, 26),
}


def settings(record):
    if not isinstance(record, dict):
        raise ValueError("Settings must be a JSON object.")
    result = DEFAULT_SETTINGS | record
    result = {key: result[key] for key in DEFAULT_SETTINGS}
    choice(result["currency"], CURRENCIES, "Currency")
    choice(result["period"], PERIODS, "Reporting period")
    choice(result["sensitivity"], ("Conservative", "Standard", "Sensitive"), "Sensitivity")
    for key in ("large_threshold", "receipt_minimum", "unusual_minimum", "unusual_multiplier"):
        result[key] = str(amount(result[key], key.replace("_", " ").capitalize(),
                                 allow_zero=key in {"receipt_minimum", "unusual_minimum"}))
    if not Decimal("1.25") <= Decimal(result["unusual_multiplier"]) <= 20:
        raise ValueError("Unusual expense multiplier must be between 1.25 and 20.")
    for key, (lower, upper) in INT_SETTINGS.items():
        value = result[key]
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError(f"{key.replace('_', ' ').capitalize()} must be an integer from {lower} to {upper}.")
    return result
