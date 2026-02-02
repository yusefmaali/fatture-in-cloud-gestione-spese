# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Install package (requires venv activation)
source venv/bin/activate
pip install -e .

# Run the CLI - two options:
./fic-expenses list              # wrapper script (no activation needed)
fic-expenses list                # after activating venv
```

There are no tests currently configured.

## Architecture

This is a Typer-based CLI tool for managing expenses in Fatture in Cloud (Italian invoicing SaaS). The codebase follows a layered architecture:

```
cli.py          → Command definitions (Typer app)
    ↓
prompts.py      → Interactive wizard for expense creation
models.py       → Pydantic models for input validation
    ↓
api.py          → FICClient wrapper around fattureincloud-python-sdk
    ↓
display.py      → Rich tables and formatting
utils.py        → Date calculations (installments, end-of-month)
```

**Key patterns:**

- **FICClient** (`api.py`): Thin wrapper that handles authentication via `.env` and exposes high-level methods (`list_expenses`, `create_expense`, `mark_expense_paid`). Instantiated fresh in each CLI command.

- **Date handling**: Typer doesn't support `datetime.date` directly, so CLI uses strings with manual parsing via `parse_date()` in `cli.py`.

- **Payment installments**: Expenses can have multiple payments (pagamento rateale). The `payments_list` field contains `ReceivedDocumentPaymentsListItem` objects with `status` ("paid"/"not_paid"), `amount`, and `due_date`.

- **Recurrence**: The `create` command can generate multiple expenses at once by shifting dates according to `RecurrencePeriod` (monthly/biannual/yearly).

## FIC API Notes

- Expenses are "received documents" of type `expense` in the FIC API
- The SDK model uses `var_date` (not `date`) for the expense date field
- Supplier filtering uses FIC query syntax: `entity.name LIKE '%term%'`

**List vs Show API differences:**
- List API returns `payments_list = None` (not loaded to reduce payload)
- List API returns `next_due_date` field - use this for payment status:
  - `next_due_date is not None` → has unpaid payments
  - `next_due_date is None` → fully paid (or no payments configured)
- Show API returns full `payments_list` with detailed payment records

See: https://github.com/fattureincloud/fattureincloud-python-sdk/blob/master/docs/ReceivedDocument.md
