# Finance & Audit Analytics

**Financial Management, Intelligent Monitoring & Automated Audit System**

A local Streamlit application for recording income and expenses, managing budgets, and reviewing financial risks. It was built for a university internship defense. The project demonstrates how a single ledger can feed operational reports, a transparent audit, and a simple expense forecast.

## Run in VS Code on Windows

Install Python 3.11 or newer, open the `finance_audit_analytics` folder in VS Code, and open a PowerShell terminal in that folder.

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If Streamlit displays its first-run email prompt, press **Enter** to skip it. Open [localhost on port 8501](http://127.0.0.1:8501) if the browser does not open automatically. Use **Ctrl+C** in the terminal to stop the server. In VS Code, **Python: Select Interpreter** can point to `.venv\Scripts\python.exe`.

If PowerShell blocks activation, run the virtual environment’s interpreter directly.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Run the tests from the same project folder.

```powershell
python -m pytest -q
```

## Modules

| Page | What it does |
| --- | --- |
| Overview | Filters by date and category and shows nine KPIs and five interactive charts. |
| Transactions | Creates, edits, and deletes ledger entries with confirmation. Includes history, search, sorting, filters, and CSV import and export. |
| Budgets | Edits calendar-month limits by expense category. Compares planned and actual spending and highlights utilization at 80% and 100%. |
| Audit Review | Lists potential risks, shows related transactions and a suggested action, and saves status and notes for each finding. |
| Audit Dashboard | Summarizes rule counts, severity, active exposure by transaction, and findings over time. |
| Financial Health | Reports savings rate, expense-to-income ratio, net cash flow, average spending, budget adherence, and suggestions tied to the figures. |
| Expense Forecast | Estimates next month’s expenses using weighted historical spending and checks whether recent history is sufficient. |
| Reports | Exports monthly finances, transactions, budget performance, audit findings, and financial health as timestamped CSV files. |
| Settings | Saves the currency label, reporting period, audit sensitivity and thresholds, and monthly category limits. |

## Architecture and technology

```text
finance_audit_analytics/
├── app.py                      Streamlit entry point and sidebar
├── demo_data.py                Reproducible fictional ledger generator
├── requirements.txt
├── README.md
├── DEFENSE_GUIDE.md
├── .gitignore
├── .streamlit/
│   └── config.toml
├── data/
│   ├── transactions.json
│   ├── budgets.json
│   ├── audit_reviews.json
│   └── settings.json
├── modules/
│   ├── __init__.py
│   ├── models.py
│   ├── storage.py
│   ├── transactions.py
│   ├── finance.py
│   ├── budgets.py
│   ├── audit_engine.py
│   ├── risk_scoring.py
│   ├── forecasting.py
│   └── reports.py
├── views/
│   ├── __init__.py
│   ├── common.py
│   ├── dashboard.py
│   ├── ledger.py
│   ├── budget.py
│   ├── audit.py
│   ├── health.py
│   ├── forecast.py
│   ├── reports.py
│   └── settings.py
└── tests/
    ├── conftest.py
    ├── test_finance.py
    ├── test_audit.py
    ├── test_storage.py
    └── test_app.py
```

Python handles validation, storage, calculations, and the interface. Streamlit supplies forms, navigation, tables, and downloads. Pandas structures display data for tables and charts, Plotly renders the interactive figures, and pytest runs service and UI tests. Monetary logic uses `Decimal` throughout. Only the display tables and charts convert values to floating point for rendering. [Streamlit AppTest documentation](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)

## Storage and CSV

The app creates missing JSON files on startup. A transaction stores its ID, date, type, category, decimal amount as a string, description, payment method, counterparty, receipt fields, and UTC creation timestamp. Edits keep the ID and timestamp. Each budget is keyed by month and category. A review stores its finding ID, status, notes, and UTC update timestamp. Findings are calculated from the current data and configuration on each relevant page.

The repository validates each new dataset, writes a temporary file in the same directory, flushes it, and replaces the original atomically. An in-process lock protects the read–modify–write sequence within one server. Malformed files display a warning. The app can show valid records from a partially invalid file and blocks writes to that file until it has been repaired. To back up a ledger, stop the app and copy the entire data folder.

The transaction CSV template is available under **Transactions → CSV exchange**. Required column names are `date,type,category,amount,description,payment_method,counterparty`. Use dates in `YYYY-MM-DD` and amounts such as `12500.50`. Fields `id`, `has_receipt`, `receipt_reference`, and `created_at` are optional. Blank IDs and timestamps are generated on import. Categories and payment methods use the same options as the transaction form. IDs are unique regardless of letter case. Each batch is checked before saving, and invalid rows cause the batch to be rejected with line numbers. App exports quote potentially executable spreadsheet text with an apostrophe and mark that encoding so direct re-import can restore the original text.

## Financial calculations

| Indicator | Calculation |
| --- | --- |
| Net cash flow | Selected income − selected expenses. The monthly KPI uses the last visible month. |
| Closing ledger balance | Opening net from all matching records before the start date + cumulative selected net cash flow through the reporting date. |
| Savings rate | 100 × net cash flow ÷ income. Unavailable at zero income. |
| Expense-to-income ratio | 100 × expenses ÷ income. Unavailable at zero income. |
| Average monthly expenses | Selected expenses ÷ number of calendar months touched by the selection, including months with zero recorded expenses. |
| Budget utilization | 100 × actual expenses ÷ planned limits. Only categories with limits contribute. |
| Budget adherence | 100 × category-month limits met ÷ configured limits in scope. Spending equal to the limit meets it. |
| Health score | Savings factor = clamp(savings rate ÷ 20%, 0, 1). Score = 60 × savings factor + 0.40 × adherence percentage. With no limits, the score is 100 × savings factor. Zero income sets the factor to zero. An empty selection has no score. |

Financial totals use the selected dates. Budget comparisons always use the full calendar months those dates touch. The default currency is KZT. Settings change the label of the single ledger currency and preserve the recorded amounts. Reports repeat the selected dates, currency, and UTC generation timestamp on each exported record.

## Audit rules

Rules run against the whole saved ledger so history and related transactions remain available when filtering. Date filters include findings that touch at least one selected transaction. The finding date is the most recent related transaction date. The review queue provides the current thresholds and related evidence.

| Rule | Method | Severity |
| --- | --- | --- |
| Large transaction | Amount strictly exceeds the approval threshold. At twice the threshold it becomes Critical. | High or Critical |
| Duplicate transaction | Group by type, date, exact amount, normalized counterparty, and normalized description. | High |
| Missing receipt | An expense meets the receipt amount floor and lacks both confirmation and a reference. | Low |
| Budget violation | Full-month category expenses strictly exceed the saved limit. | Medium, or High at 150% utilization |
| Unusual expense | Compare to the average of up to 20 prior expenses from earlier dates in the category. Drop the highest and lowest when the sample has at least five entries. Require a minimum history count, amount, and multiplier. | Medium |
| Possible transaction splitting | Look for a cluster of distinct expenses in the same category and counterparty within the configured day span. Each must be below the approval threshold and meet its configured minimum share. Their sum must reach the threshold. | High |
| Suspicious frequency | Find a counterparty’s burst of distinct expense records that meets both the minimum count and the multiplier over its previous average per equally sized window. Require earlier payments to that counterparty and ledger coverage for the baseline. | Medium |

Duplicate copies are excluded from unusual, split, and frequency calculations. Split and frequency checks report non-overlapping qualifying windows within each group. Sensitivity raises or lowers the unusual-expense multiplier, split count, and frequency count and multiplier. Other thresholds stay as configured in Settings.

Finding IDs use a stable digest of the rule name and sorted related transaction IDs. Reviews persist under that ID. Changes in the set of related records produce a new ID. Reviewers should revisit decisions after material edits to a transaction that keeps its ID.

### Audit risk score

Active statuses are **Open** and **Under Review**. Each selected transaction takes the highest active severity weight associated with it. Low is 10, Medium 25, High 55, and Critical 100. Unflagged transactions have weight 0.

`Risk = round(0.60 × highest weight + 0.40 × mean weight across selected transactions)`

Rounding is to the nearest whole number, with ties rounded up. With weights 55, 10, and 0, the score is 42. The score is zero for an empty selection. Audit findings are potential risks for manual review. The score measures rule exposure on a 0–100 scale.

### Forecast

The three most recent completed months receive weights 1, 2, and 3, from oldest to newest. The weighted sum is divided by 6. The first observed ledger month is excluded because its coverage may be partial. The current month is excluded. A forecast requires three eligible months and recorded expenses in at least two of them. The estimate is shown for the month after the current month.

## Demonstration data

The supplied ledger contains 284 fictional transactions and 72 monthly budget limits from February through October 2026. It triggers all seven audit rules with the default settings. Keep this folder as a sample, or choose a separate data folder for a blank or refreshed ledger. From the project directory in PowerShell, these commands create a fresh demonstration relative to the current month.

```powershell
$env:FINANCE_DATA_DIR = Join-Path (Get-Location) 'demo_fresh'
python demo_data.py
python -m streamlit run app.py
```

For the original dates, use `python demo_data.py --as-of 2026-11` against an empty data folder. The generator uses a fixed seed and derives IDs from the anchor month and row sequence. It refuses a target containing transactions, budgets, or reviews. For a blank ledger, set `FINANCE_DATA_DIR` to a new `private_data` folder and start Streamlit directly.

### Example walkthrough

1. Open **Overview** with all records and compare cash flow, balance, and risk.
2. Open **Budgets** and select October 2026 to compare planned spending with the equipment purchase and education installments.
3. In **Audit Review**, select the critical equipment purchase or the split training payments. Open the evidence, change the status to **Under Review**, and save a note.
4. Open **Audit Dashboard** and explain how severity and the proportion of flagged transactions affect the score.
5. Open **Financial Health** and **Expense Forecast**, then download a report. For a defense held well after the sample dates, refresh the fictional dataset first.

## Scope and possible future improvements

This is a single-user, local educational project with one ledger currency. JSON is read and written as whole files. The app relies on the operating system for local file access and backups. Receipt references are stored as text. Auditing uses date-level data and configurable heuristics. The forecast uses a short moving average and can be distorted by one-off costs or incomplete records. Concurrent use across independent server processes is outside the project scope.

Possible extensions include configurable category lists, receipt attachments, an immutable review history, and forecast backtesting against past months. The Russian-language presentation plan and teacher questions are in `DEFENSE_GUIDE.md`.
