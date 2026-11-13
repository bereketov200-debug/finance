"""Generate nine months of reproducible fictional KZT data for a clean ledger."""

import argparse
from datetime import date
from random import Random
from uuid import NAMESPACE_URL, uuid5

from modules.finance import shift_month
from modules.models import month_key
from modules.storage import StorageError, Store


SEED = 20261108
RECURRING = {
    "Food": (7, 4_200, 13_000, ("Juniper Market (demo)", "Paper Kite Cafe (demo)")),
    "Transportation": (4, 1_800, 9_500, ("Copper Tram (demo)", "Cloud Route (demo)")),
    "Shopping": (3, 12_000, 29_000, ("Orchid Shop (demo)", "Blue Loom (demo)")),
    "Education": (2, 10_000, 23_000, ("Horizon Learning (demo)",)),
    "Entertainment": (3, 4_000, 13_000, ("Mint Theatre (demo)", "Sky Arcade (demo)")),
    "Utilities": (2, 15_000, 24_000, ("Cobalt Utilities (demo)",)),
    "Healthcare": (2, 6_000, 14_000, ("Fern Clinic (demo)",)),
    "Other": (2, 4_500, 9_500, ("Aster Services (demo)",)),
}
LIMITS = {
    "Food": 85_000, "Transportation": 39_000, "Shopping": 74_000, "Education": 90_000,
    "Entertainment": 39_000, "Utilities": 48_000, "Healthcare": 36_000, "Other": 22_000,
}


def make_demo(anchor_month):
    rng = Random(SEED)
    transactions, budgets = [], []
    anchor_month = month_key(anchor_month)

    def entry(month, day, kind, category, amount, counterparty, description, *, receipt=True, method="Card"):
        day = f"{month}-{day:02d}"
        sequence = len(transactions)
        identifier = uuid5(NAMESPACE_URL, f"finance-audit-demo/{SEED}/{anchor_month}/{sequence}").hex
        transactions.append({
            "id": identifier, "date": day, "type": kind, "category": category, "amount": str(amount),
            "description": description, "payment_method": method, "counterparty": counterparty,
            "has_receipt": receipt,
            "receipt_reference": f"DEMO-{sequence + 1:04d}" if receipt and kind == "Expense" else "",
            "created_at": f"{day}T09:00:00+00:00",
        })

    for offset in range(-9, 0):
        month = shift_month(anchor_month, offset)
        for day in (1, 15):
            entry(month, day, "Income", "Salary", rng.randrange(235, 276) * 1000,
                  "Larkspur Studio (demo)", "Semi-monthly payroll", method="Bank transfer")
        entry(month, 20, "Income", "Freelance", rng.randrange(35, 102) * 1000,
              "Ivory Pixel (demo)", "Design and research contract", method="Bank transfer")
        for category, (count, low, high, vendors) in RECURRING.items():
            for day in sorted(rng.sample(range(2, 27), count)):
                entry(month, day, "Expense", category, rng.randrange(low // 100, high // 100) * 100,
                      rng.choice(vendors), f"{category} purchase {day}")
        for day in (4, 13):
            entry(month, day, "Expense", "Food", 4200, "Saffron Pantry (demo)", f"Pantry restock {day}")
        budgets.extend({"month": month, "category": category, "limit": str(limit)
                        } for category, limit in LIMITS.items())

    final_month = shift_month(anchor_month, -1)
    entry(final_month, 20, "Expense", "Shopping", 650_000, "Granite Supply (demo)",
          "Equipment purchase for demonstration", method="Bank transfer")
    for _ in range(2):
        entry(final_month, 19, "Expense", "Utilities", 18_500, "Cobalt Utilities (demo)", "Invoice DEMO-U019")
    entry(final_month, 21, "Expense", "Transportation", 7800, "Copper Tram (demo)",
          "Travel reimbursement awaiting receipt", receipt=False)
    entry(final_month, 24, "Expense", "Healthcare", 108_000, "Fern Clinic (demo)", "Annual screening package")
    for day, value in ((25, 104_000), (26, 107_000), (27, 109_000)):
        entry(final_month, day, "Expense", "Education", value, "Horizon Learning (demo)",
              f"Training package installment {day - 24}", method="Bank transfer")
    for index in range(6):
        entry(final_month, 25 + index // 3, "Expense", "Food", 2500 + index * 50,
              "Saffron Pantry (demo)", f"Same-window pantry order {index + 1}")
    return transactions, budgets


def seed_store(store, anchor_month):
    transactions, budgets = make_demo(anchor_month)
    datasets = ("transactions", "budgets", "audit_reviews")
    existing = [store.read(name) for name in datasets]
    if any(existing) or store.warnings:
        raise ValueError("Demo generation requires empty transactions, budgets, and reviews. Use a new --data-dir.")

    def replace_empty(current, incoming):
        if current:
            raise ValueError("Demo generation stopped because the destination is no longer empty.")
        return incoming

    store.update("transactions", lambda rows: replace_empty(rows, transactions))
    store.update("budgets", lambda rows: replace_empty(rows, budgets))
    return len(transactions), len(budgets)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat()[:7], metavar="YYYY-MM",
                        help="Anchor month. The generated ledger covers the preceding nine months.")
    parser.add_argument("--data-dir", help="Generate into a separate empty data folder.")
    args = parser.parse_args()
    try:
        store = Store(args.data_dir)
        count, budget_count = seed_store(store, args.as_of)
    except (ValueError, StorageError) as error:
        parser.exit(1, f"Demo data was not fully generated. {error}\n")
    print(f"Generated {count} fictional transactions and {budget_count} budget limits in {store.root}.")


if __name__ == "__main__":
    main()
