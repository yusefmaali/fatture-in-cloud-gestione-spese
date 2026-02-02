# FIC Expenses

A Terminal User Interface (TUI) to manage expenses (received documents) in [Fatture in Cloud](https://www.fattureincloud.it/).

![TUI Screenshot](docs/screenshot.png)

## Features

- **Interactive expense list** - Browse expenses with real-time filtering and sorting
- **Multi-selection** - Select multiple expenses for batch payment operations
- **Expense details** - View full information including payment schedule
- **Quick payment** - Pay single expenses, specific installments, or batch operations
- **Create wizard** - Step-by-step expense creation with installment preview
- **API quota tracking** - Real-time display of API rate limit usage

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

Launch the TUI and press `F1` to open Settings, or run:

```bash
fic-expenses
# Then press F1 for Settings
```

The Settings screen will guide you through:
1. Setting your API credentials (get them from https://fattureincloud.it/connessioni/)
2. Selecting a default payment account (required for paying expenses)

Alternatively, create a `.env` file manually:

```env
FIC_ACCESS_TOKEN=your_access_token_here
FIC_COMPANY_ID=your_company_id_here
FIC_DEFAULT_ACCOUNT_ID=123456  # Required for payments
```

## Usage

```bash
# Option 1: Use the wrapper script (no activation needed)
./fic-expenses

# Option 2: Activate venv first
source venv/bin/activate
fic-expenses
```

## Keyboard Shortcuts

### Global
| Key | Action |
|-----|--------|
| `Ctrl+Q` | Quit application |
| `Ctrl+R` | Refresh data |
| `F1` | Open settings |

### Expenses Screen
| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate table rows |
| `Enter` | Open expense details |
| `Space` | Toggle row selection |
| `P` | Pay selected (or current if none) |
| `N` | Create new expense |
| `Ctrl+A` | Select all unpaid |
| `Esc` | Clear selection |
| `/` | Focus search filter |

### Detail Screen
| Key | Action |
|-----|--------|
| `Esc` / `Backspace` | Go back |
| `P` | Pay all unpaid installments |
| `1`-`9` | Pay specific installment |

### Dialogs
| Key | Action |
|-----|--------|
| `Enter` | Confirm / Submit |
| `Esc` | Cancel / Close |
| `Tab` | Next field |

## Screens

### Expenses List
The main screen displays all your expenses in a filterable table:
- Filter by status (All / Paid / Unpaid)
- Filter by supplier name
- Filter by date range
- Summary bar shows totals and counts

### Expense Details
Press `Enter` on any expense to see:
- Full supplier and description
- Date and category
- Net, VAT, and Gross amounts
- Complete payment schedule with status

### Create Wizard
Press `N` to open the 4-step creation wizard:
1. **Basics** - Supplier, description, category, date
2. **Amount** - Net amount and VAT rate with calculated totals
3. **Payment** - Number of installments and first due date
4. **Review** - Summary before creation

### Pay Dialog
Press `P` to pay expenses:
- Single expense payment
- Batch payment for multiple selected expenses
- Choose payment date
- Uses the default payment account from Settings

### Settings
Press `F1` to configure:
- API credentials (Access Token and Company ID)
- Validate credentials against the API
- Select default payment account

## API Quota Display

The header shows real-time API usage:
```
API: 42/1000h 156/5000m
```
- `h` = hourly limit (resets each hour)
- `m` = monthly limit
- Turns red when usage exceeds 90%

## API Documentation

This tool uses the Fatture in Cloud API via the official Python SDK:

- **Python SDK**: https://github.com/fattureincloud/fattureincloud-python-sdk
- **API Documentation**: https://developers.fattureincloud.it/
- **ReceivedDocument Model**: https://github.com/fattureincloud/fattureincloud-python-sdk/blob/master/docs/ReceivedDocument.md

## License

MIT
