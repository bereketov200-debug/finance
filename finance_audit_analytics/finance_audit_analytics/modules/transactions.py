"""Transaction CRUD, filtering, and all-or-nothing CSV import."""

import csv
import io
from uuid import uuid4

from .models import amount, now, transaction


REQUIRED_COLUMNS = ("date", "type", "category", "amount", "description",
                    "payment_method", "counterparty")
TRANSACTION_COLUMNS = ("id", *REQUIRED_COLUMNS, "has_receipt", "receipt_reference", "created_at")
MAX_CSV_BYTES = 5 * 1024 * 1024
TEXT_ENCODING = "apostrophe-v1"
TEXT_COLUMNS = ("description", "counterparty", "receipt_reference")


def guard_csv(value):
    if isinstance(value, str) and (value.startswith("'") or value.lstrip().startswith(("=", "+", "-", "@"))):
        return "'" + value
    return value


def filter_transactions(rows, start=None, end=None, categories=(), kind=None, search=""):
    query = search.strip().casefold()
    return [
        row for row in rows
        if (start is None or row["date"] >= start)
        and (end is None or row["date"] <= end)
        and (not categories or row["category"] in categories)
        and (kind is None or row["type"] == kind)
        and (not query or any(query in str(row[key]).casefold()
                              for key in ("id", "description", "counterparty", "receipt_reference")))
    ]


def sort_transactions(rows, field="date", descending=True):
    return sorted(rows, key=lambda row: (
        amount(row["amount"]) if field == "amount" else row[field].casefold(), row["id"]
    ), reverse=descending)


def add(store, fields):
    item = transaction(fields | {"id": uuid4().hex, "created_at": now()})
    store.update("transactions", lambda rows: [*rows, item])
    return item


def edit(store, identifier, fields):
    def change(rows):
        for index, row in enumerate(rows):
            if row["id"] == identifier:
                rows[index] = transaction(row | fields | {"id": identifier, "created_at": row["created_at"]})
                return rows
        raise ValueError("Transaction no longer exists.")

    store.update("transactions", change)


def delete(store, identifier):
    def change(rows):
        remaining = [row for row in rows if row["id"] != identifier]
        if len(remaining) == len(rows):
            raise ValueError("Transaction no longer exists.")
        return remaining

    store.update("transactions", change)


def parse_csv(payload, existing_ids=()):
    if len(payload) > MAX_CSV_BYTES:
        raise ValueError("CSV must be 5 MB or smaller.")
    try:
        source = io.StringIO(payload.decode("utf-8-sig"), newline="")
        reader = csv.DictReader(source, strict=True)
        headers = reader.fieldnames or []
        missing = sorted(set(REQUIRED_COLUMNS) - set(headers))
        if missing:
            raise ValueError(f"Missing columns: {', '.join(missing)}.")
        if len(headers) != len(set(headers)):
            raise ValueError("CSV column names must be unique.")
        seen = {identifier.casefold() for identifier in existing_ids}
        imported, problems = [], []
        for row in reader:
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("Column count differs from the header.")
                row = {key: value.strip() for key, value in row.items()}
                if row.get("csv_text_encoding") == TEXT_ENCODING:
                    for key in TEXT_COLUMNS:
                        if row.get(key, "").startswith("'"):
                            row[key] = row[key][1:]
                receipt = row.get("has_receipt", "").casefold()
                if receipt not in {"", "true", "false", "yes", "no", "1", "0"}:
                    raise ValueError("has_receipt must be true, false, yes, no, 1, or 0.")
                row["has_receipt"] = receipt in {"true", "yes", "1"}
                row["created_at"] = row.get("created_at") or now()
                row["id"] = row.get("id") or uuid4().hex
                item = transaction(row)
                key = item["id"].casefold()
                if key in seen:
                    raise ValueError(f"Duplicate transaction ID {item['id']}.")
                seen.add(key)
                imported.append(item)
            except ValueError as error:
                problems.append(f"Line {reader.line_num}: {error}")
                if len(problems) == 8:
                    break
    except (UnicodeError, csv.Error) as error:
        raise ValueError(f"Expected a valid UTF-8 comma-separated file: {error}") from error
    if problems:
        raise ValueError("\n".join(problems))
    if not imported:
        raise ValueError("The CSV has no transaction rows.")
    return imported


def import_csv(store, payload):
    imported = []

    def change(rows):
        imported.extend(parse_csv(payload, (row["id"] for row in rows)))
        return rows + imported

    store.update("transactions", change)
    return len(imported)
