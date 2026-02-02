# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Install package (requires venv activation)
source venv/bin/activate
pip install -e .

# Run the TUI - two options:
./fic-expenses              # wrapper script (no activation needed)
fic-expenses                # after activating venv
```

There are no tests currently configured.

## Architecture

This is a Textual TUI application for managing expenses in Fatture in Cloud (Italian invoicing SaaS). The codebase follows a layered architecture:

```
app.py              → Main Textual App, entry point
    ↓
screens/
├── expenses.py     → Main expenses list screen with filtering
├── details.py      → Expense detail view with payment schedule
├── settings.py     → Settings screen (credentials, payment account)
├── loading.py      → Loading screen during API calls
└── error.py        → Error screen with retry option
    ↓
dialogs/
├── pay.py          → Pay dialog (single & batch payments)
└── create/
    └── wizard.py   → Multi-step expense creation wizard
    ↓
widgets/
├── expenses_table.py   → DataTable with multi-select support
├── filter_bar.py       → Status/supplier/date filters
├── summary_bar.py      → Totals and counts display
└── quota_display.py    → API quota in header
    ↓
api.py              → FICClient wrapper with quota tracking
models.py           → Pydantic models for input validation
utils.py            → Date calculations (installments, end-of-month)
    ↓
styles/app.tcss     → Textual CSS styles
```

**Key patterns:**

- **FICClient** (`api.py`): Thin wrapper that handles authentication via `.env` and exposes high-level methods (`list_expenses`, `create_expense`, `mark_expense_paid`). Tracks API quota via `_with_http_info` methods.

- **QuotaInfo** (`api.py`): Dataclass that parses rate limit headers from API responses. Displayed in the header via `QuotaDisplay` widget.

- **Screen navigation**: Uses Textual's screen stack. `ExpensesScreen` is the main screen; detail views and dialogs are pushed on top.

- **Multi-selection**: `ExpensesTable` supports selecting multiple expenses with Space key for batch operations (pay multiple at once).

- **Payment installments**: Expenses can have multiple payments (pagamento rateale). The detail screen shows the full payment schedule with ability to pay specific installments (1-9 keys).

- **Configuration**: Settings screen (`screens/settings.py`) validates credentials and selects default payment account. Configuration stored in `.env` using `dotenv.set_key()`.

## Key Bindings

### Global
- `Ctrl+Q`: Quit application
- `Ctrl+R`: Refresh data
- `F1`: Open settings

### Expenses Screen
- `↑/↓`: Navigate table rows
- `Enter`: Open expense details
- `Space`: Toggle row selection
- `P`: Pay selected (or current if none selected)
- `N`: New expense
- `Ctrl+A`: Select all unpaid
- `Esc`: Clear selection
- `/`: Focus search filter

### Detail Screen
- `Esc/Backspace`: Go back
- `P`: Pay all unpaid installments
- `1-9`: Pay specific installment

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

**Quota tracking:**
- API methods use `_with_http_info` variants to access response headers
- Rate limit headers: `x-ratelimit-hourly-remaining`, `x-ratelimit-monthly-remaining`
- QuotaDisplay widget shows usage, turns red at 90%+

**Pagination:**
- `MAX_PER_PAGE = 100` is defined in `FICClient` (SDK enforces this limit via Pydantic validation)
- `fetch_all=True` uses `MAX_PER_PAGE` internally to minimize API calls
- Rate limits: 300 requests/5 min, 1000/hour per company

**Marking payments as paid:**
- IMPORTANT: The API requires a `payment_account` when updating payment status
- Without a `payment_account`, the API silently ignores the payment update (no error)
- Use `InfoApi.list_payment_accounts()` to get available accounts (bank, cash, cards)
- Uses `FIC_DEFAULT_ACCOUNT_ID` from `.env` (set via Settings screen)

See:
- https://github.com/fattureincloud/fattureincloud-python-sdk/blob/master/docs/ReceivedDocument.md
- https://developers.fattureincloud.it/docs/guides
