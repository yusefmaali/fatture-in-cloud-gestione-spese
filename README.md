# FIC Expenses

A CLI tool to manage expenses (received documents) in [Fatture in Cloud](https://www.fattureincloud.it/).

## Features

- **List expenses** - View all expenses with filters (paid/unpaid, supplier, date range)
- **Show details** - View full expense information including payment installments
- **Mark as paid** - Pay single expenses, specific installments, or batch by supplier/date
- **Create expenses** - Interactive wizard or CLI arguments with support for:
  - Multiple payment installments (pagamento rateale)
  - Recurring expenses (monthly, biannual, yearly)

## Installation

```bash
# Clone and enter the project
cd load_expenses

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the package
pip install -e .
```

## Configuration

Run the interactive configuration wizard:

```bash
fic-expenses configs
```

This will guide you through:
1. Setting your API credentials (get them from https://fattureincloud.it/connessioni/)
2. Selecting a default payment account

Alternatively, copy `.env.example` to `.env` and add credentials manually:

```bash
cp .env.example .env
```

```env
FIC_ACCESS_TOKEN=your_access_token_here
FIC_COMPANY_ID=your_company_id_here
FIC_DEFAULT_ACCOUNT_ID=123456  # Required for 'pay' command
```

## Usage

Two ways to run the CLI:

```bash
# Option 1: Use the wrapper script (no activation needed)
./fic-expenses list

# Option 2: Activate venv first
source venv/bin/activate
fic-expenses list
```

### List Expenses

```bash
# List all expenses
fic-expenses list

# Filter by payment status
fic-expenses list --paid
fic-expenses list --unpaid

# Filter by supplier (partial match)
fic-expenses list --supplier "Amazon"

# Filter by date range
fic-expenses list --from 2024-01-01 --to 2024-12-31

# Combine filters
fic-expenses list --unpaid --supplier "OVH" --from 2024-01-01
```

### Show Expense Details

```bash
fic-expenses show 12345
```

Output includes full details and payment schedule:
```
╭────────────────────╮
│ Expense #12345     │
╰────────────────────╯
  Supplier:       Amazon AWS
  Date:           2024-01-15
  Description:    Cloud services
  Category:       Software

  Net:            €100.00
  VAT:            €22.00
  Gross:          €122.00

Payment Schedule
──────────────────────────────────────────────────
  ✓ Rata 1: €24.40 - due 2024-02-28 (paid 2024-02-25)
  ✓ Rata 2: €24.40 - due 2024-03-31 (paid 2024-03-30)
  ○ Rata 3: €24.40 - due 2024-04-30
  ○ Rata 4: €24.40 - due 2024-05-31
  ○ Rata 5: €24.40 - due 2024-06-30
```

### Create Expense

**Interactive wizard** (recommended for first use):
```bash
fic-expenses create
```

**CLI arguments** (for scripting):
```bash
# Simple expense
fic-expenses create \
  --supplier "Amazon AWS" \
  --description "Cloud hosting" \
  --amount-net 100 \
  --vat-rate 22

# With installments
fic-expenses create \
  --supplier "Dell" \
  --amount-net 500 \
  --installments 5 \
  --first-due 2024-03-31

# Recurring expense (creates 3 yearly expenses)
fic-expenses create \
  --supplier "Software License" \
  --amount-net 200 \
  --recurrence yearly \
  --occurrences 3 \
  --yes
```

### Mark as Paid

The `pay` command uses the default payment account set by `fic-expenses configs`.

```bash
# Mark expense as paid
fic-expenses pay 12345

# Mark specific installment (1-indexed)
fic-expenses pay 12345 --installment 2

# Custom payment date
fic-expenses pay 12345 --date 2024-02-15

# Batch: mark all from supplier as paid
fic-expenses pay --supplier "Amazon"

# Batch: mark expenses in date range as paid
fic-expenses pay --from 2024-01-01 --to 2024-01-31

# Skip confirmation prompt for batch
fic-expenses pay --supplier "Amazon" --yes
```

## Command Reference

| Command | Description |
|---------|-------------|
| `fic-expenses list` | List expenses with optional filters |
| `fic-expenses show <id>` | Show expense details and installments |
| `fic-expenses pay <id>` | Mark expense or installment as paid |
| `fic-expenses create` | Create new expense (wizard or CLI args) |
| `fic-expenses configs` | Configure credentials and default settings |
| `fic-expenses --help` | Show help |
| `fic-expenses --version` | Show version |

## Options Summary

### List Options
| Option | Description |
|--------|-------------|
| `--paid` | Show only fully paid expenses |
| `--unpaid` | Show only expenses with unpaid installments |
| `--supplier`, `-s` | Filter by supplier name (partial match) |
| `--from` | Filter from date (YYYY-MM-DD) |
| `--to` | Filter to date (YYYY-MM-DD) |
| `--all`, `-a` | Fetch all expenses (ignores --limit, uses max per_page=100) |
| `--limit`, `-l` | Maximum number of expenses to show (ignored with --all) |

### Create Options
| Option | Description |
|--------|-------------|
| `--supplier`, `-s` | Supplier name (required in CLI mode) |
| `--description`, `-D` | Expense description |
| `--category`, `-c` | Expense category |
| `--amount-net`, `-a` | Net amount before VAT (required in CLI mode) |
| `--vat-rate`, `-v` | VAT percentage (default: 22) |
| `--date`, `-d` | Expense date (default: today) |
| `--installments`, `-n` | Number of payment installments (default: 1) |
| `--first-due` | First installment due date |
| `--recurrence`, `-r` | Recurrence: `monthly`, `biannual`, `yearly` |
| `--occurrences`, `-o` | Number of recurring expenses (default: 1) |
| `--yes`, `-y` | Skip confirmation |

### Pay Options
| Option | Description |
|--------|-------------|
| `--installment`, `-i` | Mark only this installment as paid (1-indexed) |
| `--date`, `-d` | Payment date (default: expense date) |
| `--supplier`, `-s` | Batch: mark all from supplier |
| `--from` | Batch: from date |
| `--to` | Batch: to date |
| `--yes`, `-y` | Skip confirmation for batch operations |

Note: The `pay` command uses the default payment account set via `fic-expenses configs`.

## API Documentation

This tool uses the Fatture in Cloud API via the official Python SDK:

- **Python SDK**: https://github.com/fattureincloud/fattureincloud-python-sdk
- **API Documentation**: https://developers.fattureincloud.it/
- **ReceivedDocument Model**: https://github.com/fattureincloud/fattureincloud-python-sdk/blob/master/docs/ReceivedDocument.md

## License

MIT
