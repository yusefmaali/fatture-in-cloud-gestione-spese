# CLI Tool Plan: Fatture in Cloud Expense Manager

## Overview
A Python CLI tool using **Typer** to manage expenses (received documents) in Fatture in Cloud.

## User Requirements Summary
- List expenses (all / paid / unpaid)
- Mark expenses as paid (single, batch by date range or supplier)
- Mark single installment as paid
- Create expenses with interactive wizard + CLI args support
- Support installments (pagamento rateale)
- Support recurrence (auto-create future expenses)
- Help menu

## Architecture

### Project Structure
```
load_expenses/
├── .env.example
├── .env                    # git-ignored
├── .gitignore
├── pyproject.toml          # Project config + dependencies
├── poc_create_expense.py   # Keep for reference
└── src/
    └── fic_expenses/
        ├── __init__.py
        ├── cli.py          # Typer app + commands
        ├── api.py          # FIC API wrapper (thin layer)
        ├── models.py       # Pydantic models for input validation
        ├── prompts.py      # Interactive wizard logic
        ├── display.py      # Rich tables + formatting
        └── utils.py        # Date helpers (end_of_month, installments)
```

### Dependencies
```
fattureincloud-python-sdk
python-dotenv
typer[all]      # Includes rich + shellingham
pydantic        # Input validation
```

---

## Command Structure

```bash
fic-expenses [COMMAND] [OPTIONS]
```

### Commands

| Command | Description |
|---------|-------------|
| `list` | List expenses (default: all) |
| `list --paid` | List only paid expenses |
| `list --unpaid` | List only unpaid expenses |
| `list --supplier "Amazon"` | Filter by supplier name |
| `list --from 2024-01-01 --to 2024-12-31` | Filter by date range |
| `create` | Create new expense (interactive wizard) |
| `create --supplier "..." --amount 100 ...` | Create with CLI args |
| `pay <expense_id>` | Mark entire expense as paid |
| `pay --supplier "Amazon"` | Mark all from supplier as paid |
| `pay --from 2024-01-01 --to 2024-01-31` | Mark range as paid |
| `pay <expense_id> --installment 2` | Mark specific installment as paid |
| `show <expense_id>` | Show expense details + installments |
| `--help` | Show help menu |

---

## Feature Details

### 1. List Expenses (`list`)

**API Call:** `list_received_documents(company_id, type="expense", ...)`

**Filters (combinable):**
- `--paid` / `--unpaid` / (default: all)
- `--supplier TEXT` - partial match on entity name
- `--from DATE` / `--to DATE` - date range

**Output:** Rich table
```
┏━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ ID    ┃ Date       ┃ Supplier        ┃ Gross     ┃ Status   ┃ Next Due     ┃
┡━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ 12345 │ 2024-01-15 │ Amazon AWS      │ €122.00   │ 2/5 paid │ 2024-04-30   │
│ 12346 │ 2024-01-20 │ Dell            │ €610.00   │ Paid ✓   │ -            │
└───────┴────────────┴─────────────────┴───────────┴──────────┴──────────────┘
```

### 2. Show Expense Details (`show <id>`)

**API Call:** `get_received_document(company_id, document_id)`

**Output:** Full details + installment breakdown
```
Expense #12345
══════════════════════════════════════
  Supplier:    Amazon AWS
  Date:        2024-01-15
  Description: Cloud services
  Category:    Software
  Net:         €100.00
  VAT:         €22.00 (22%)
  Gross:       €122.00
──────────────────────────────────────
  Payment Schedule (5 installments):
    ✓ Rata 1: €24.40 - 2024-02-28 (paid 2024-02-25)
    ✓ Rata 2: €24.40 - 2024-03-31 (paid 2024-03-30)
    ○ Rata 3: €24.40 - 2024-04-30
    ○ Rata 4: €24.40 - 2024-05-31
    ○ Rata 5: €24.40 - 2024-06-30
══════════════════════════════════════
```

### 3. Create Expense (`create`)

**Two modes:**

#### A) Interactive Wizard (default when no args)
```
$ fic-expenses create

🧾 Create New Expense
─────────────────────
Supplier name: Amazon AWS
Description: Cloud hosting February
Category [Software]:
Amount (net, €): 100
VAT rate % [22]:
Date [2024-02-02]:

💳 Payment Options
─────────────────────
Number of installments [1]: 5
First payment due date [2024-03-31]:

🔄 Recurrence
─────────────────────
Is this recurring? [y/N]: y
Recurrence period:
  1. Monthly
  2. Every 6 months
  3. Yearly
Select [3]: 3
How many occurrences (including this one)? [3]: 3

Creating 3 expenses (2024, 2025, 2026)...
✓ Created expense #12345 (2024)
✓ Created expense #12346 (2025)
✓ Created expense #12347 (2026)
```

#### B) CLI Arguments (for scripting)
```bash
fic-expenses create \
  --supplier "Amazon AWS" \
  --description "Cloud hosting" \
  --amount-net 100 \
  --vat-rate 22 \
  --date 2024-02-02 \
  --installments 5 \
  --first-due 2024-03-31 \
  --recurrence yearly \
  --occurrences 3
```

**Recurrence Logic:**
- Creates N separate expenses in FIC
- Each with the same structure but dates shifted by the recurrence period
- Installment due dates also shifted accordingly

### 4. Mark as Paid (`pay`)

**Single expense:**
```bash
fic-expenses pay 12345
# Marks all remaining installments as paid today
```

**Single installment:**
```bash
fic-expenses pay 12345 --installment 3
# Marks only installment #3 as paid today
```

**With custom date:**
```bash
fic-expenses pay 12345 --date 2024-02-15
```

**Batch by supplier:**
```bash
fic-expenses pay --supplier "Amazon"
# Confirmation prompt: "Mark 5 expenses from 'Amazon' as paid? [y/N]"
```

**Batch by date range:**
```bash
fic-expenses pay --from 2024-01-01 --to 2024-01-31
# Confirmation prompt: "Mark 12 expenses from Jan 2024 as paid? [y/N]"
```

**API Call:** `modify_received_document()` updating `payments_list` with `status="paid"` and `paid_date`

---

## Implementation Phases

### Phase 1: Core Infrastructure
1. Set up `pyproject.toml` with dependencies
2. Create package structure (`src/fic_expenses/`)
3. Implement `api.py` - thin wrapper around FIC SDK
4. Implement `utils.py` - date helpers from POC
5. Implement `display.py` - Rich table formatters
6. Basic Typer app skeleton with `--help`

### Phase 2: Read Operations
1. `list` command with filters
2. `show` command with installment details

### Phase 3: Write Operations
1. `pay` command (single expense)
2. `pay` command (single installment)
3. `pay` command (batch operations with confirmation)

### Phase 4: Create Expense
1. `create` with CLI arguments
2. `create` interactive wizard (`prompts.py`)
3. Installments generation (reuse from POC)
4. Recurrence logic (create multiple expenses)

### Phase 5: Polish
1. Error handling improvements
2. Input validation with Pydantic
3. Edge cases (no results, API errors, etc.)

---

## Key Files to Create/Modify

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata + dependencies |
| `src/fic_expenses/__init__.py` | Package init |
| `src/fic_expenses/cli.py` | Typer commands (~150 lines) |
| `src/fic_expenses/api.py` | FIC API wrapper (~100 lines) |
| `src/fic_expenses/models.py` | Pydantic models for input (~50 lines) |
| `src/fic_expenses/prompts.py` | Interactive wizard (~80 lines) |
| `src/fic_expenses/display.py` | Rich formatting (~60 lines) |
| `src/fic_expenses/utils.py` | Date utilities (~40 lines) |

---

## Verification Plan

1. **Install the package:**
   ```bash
   pip install -e .
   ```

2. **Test help menu:**
   ```bash
   fic-expenses --help
   fic-expenses list --help
   ```

3. **Test list commands:**
   ```bash
   fic-expenses list
   fic-expenses list --unpaid
   fic-expenses list --supplier "TEST"
   ```

4. **Test create (interactive):**
   ```bash
   fic-expenses create
   # Walk through wizard, verify in FIC web UI
   ```

5. **Test create (CLI args):**
   ```bash
   fic-expenses create --supplier "Test CLI" --amount-net 50 --vat-rate 22 --installments 3
   ```

6. **Test pay commands:**
   ```bash
   fic-expenses pay <id> --installment 1
   fic-expenses show <id>  # Verify installment marked paid
   fic-expenses pay <id>   # Pay remaining
   ```

7. **Cleanup:** Delete test expenses from FIC web UI
