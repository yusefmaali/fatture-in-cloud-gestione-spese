"""Interactive wizard prompts for expense creation."""

from datetime import date
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt, FloatPrompt, IntPrompt, Confirm

from .models import ExpenseInput, RecurrencePeriod
from .utils import end_of_month

console = Console()


def prompt_expense_wizard() -> ExpenseInput:
    """Interactive wizard to create an expense."""
    console.print()
    console.print("[bold cyan]Create New Expense[/bold cyan]")
    console.print("─" * 30)
    console.print()

    # Basic info
    supplier = Prompt.ask("Supplier name")
    description = Prompt.ask("Description", default="")
    category = Prompt.ask("Category", default="")

    # Amounts
    console.print()
    console.print("[bold]Amounts[/bold]")
    amount_net = FloatPrompt.ask("Amount (net, €)")
    vat_rate = FloatPrompt.ask("VAT rate %", default=22.0)

    # Date
    today_str = date.today().isoformat()
    date_str = Prompt.ask("Date", default=today_str)
    expense_date = date.fromisoformat(date_str)

    # Payment options
    console.print()
    console.print("[bold]Payment Options[/bold]")
    console.print("─" * 30)
    installments = IntPrompt.ask("Number of installments", default=1)

    first_due: Optional[date] = None
    if installments > 1:
        # Default to end of next month
        default_month = expense_date.month + 1
        default_year = expense_date.year
        if default_month > 12:
            default_month = 1
            default_year += 1
        default_due = end_of_month(default_year, default_month)
        due_str = Prompt.ask("First payment due date", default=default_due.isoformat())
        first_due = date.fromisoformat(due_str)

    # Recurrence
    console.print()
    console.print("[bold]Recurrence[/bold]")
    console.print("─" * 30)
    is_recurring = Confirm.ask("Is this recurring?", default=False)

    recurrence: Optional[RecurrencePeriod] = None
    occurrences = 1

    if is_recurring:
        console.print()
        console.print("Recurrence period:")
        console.print("  1. Monthly")
        console.print("  2. Every 6 months")
        console.print("  3. Yearly")
        choice = IntPrompt.ask("Select", default=3, choices=["1", "2", "3"])

        recurrence = {
            1: RecurrencePeriod.MONTHLY,
            2: RecurrencePeriod.BIANNUAL,
            3: RecurrencePeriod.YEARLY,
        }[choice]

        occurrences = IntPrompt.ask(
            "How many occurrences (including this one)?",
            default=3
        )

    return ExpenseInput(
        supplier=supplier,
        description=description if description else None,
        category=category if category else None,
        amount_net=amount_net,
        vat_rate=vat_rate,
        expense_date=expense_date,
        installments=installments,
        first_due=first_due,
        recurrence=recurrence,
        occurrences=occurrences,
    )


def confirm_expense_creation(expense: ExpenseInput) -> bool:
    """Show expense summary and ask for confirmation."""
    console.print()
    console.print("[bold cyan]Expense Summary[/bold cyan]")
    console.print("═" * 40)
    console.print(f"  Supplier:     {expense.supplier}")
    console.print(f"  Description:  {expense.description or '-'}")
    console.print(f"  Category:     {expense.category or '-'}")
    console.print(f"  Date:         {expense.expense_date}")
    console.print(f"  Net:          €{expense.amount_net:.2f}")
    console.print(f"  VAT ({expense.vat_rate}%):   €{expense.amount_vat:.2f}")
    console.print(f"  Gross:        €{expense.amount_gross:.2f}")
    console.print("─" * 40)

    if expense.installments > 1:
        console.print(f"  Installments: {expense.installments}")
        console.print(f"  First due:    {expense.first_due}")

    if expense.recurrence:
        console.print(f"  Recurrence:   {expense.recurrence.value}")
        console.print(f"  Occurrences:  {expense.occurrences}")

    console.print("═" * 40)
    console.print()

    return Confirm.ask("Create this expense?", default=True)
