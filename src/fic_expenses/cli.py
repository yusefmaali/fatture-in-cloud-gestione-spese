"""CLI commands for FIC Expenses."""

from datetime import date
from typing import Annotated, Optional

import typer
from rich.console import Console

from . import __version__
from .api import FICClient, create_payment_installments
from .display import display_expenses_table, display_expense_details, confirm
from .models import ExpenseInput, PaymentFilter, RecurrencePeriod
from .prompts import prompt_expense_wizard, confirm_expense_creation
from .utils import add_months

app = typer.Typer(
    name="fic-expenses",
    help="CLI tool to manage expenses in Fatture in Cloud",
    no_args_is_help=True,
)
console = Console()


def parse_date(date_str: str | None) -> date | None:
    """Parse date string in YYYY-MM-DD format."""
    if date_str is None:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise typer.BadParameter(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def version_callback(value: bool):
    if value:
        console.print(f"fic-expenses version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
):
    """Manage expenses in Fatture in Cloud."""
    pass


# ============================================================================
# LIST COMMAND
# ============================================================================

@app.command()
def list(
    paid: Annotated[
        Optional[bool],
        typer.Option("--paid", help="Show only paid expenses"),
    ] = None,
    unpaid: Annotated[
        Optional[bool],
        typer.Option("--unpaid", help="Show only unpaid expenses"),
    ] = None,
    supplier: Annotated[
        Optional[str],
        typer.Option("--supplier", "-s", help="Filter by supplier name (partial match)"),
    ] = None,
    from_date: Annotated[
        Optional[str],
        typer.Option("--from", help="Filter from date (YYYY-MM-DD)"),
    ] = None,
    to_date: Annotated[
        Optional[str],
        typer.Option("--to", help="Filter to date (YYYY-MM-DD)"),
    ] = None,
    all_results: Annotated[
        bool,
        typer.Option("--all", "-a", help="Fetch all expenses (not just first 50)"),
    ] = False,
    limit: Annotated[
        Optional[int],
        typer.Option("--limit", "-l", help="Maximum number of expenses to show"),
    ] = None,
):
    """
    List expenses.

    By default shows the 50 most recent expenses. Use --all to fetch all.
    """
    try:
        client = FICClient()

        # Build filter
        filter_obj = PaymentFilter(
            supplier=supplier,
            from_date=parse_date(from_date),
            to_date=parse_date(to_date),
        )
        query = filter_obj.to_query()

        # --all ignores --limit (fetch everything, API uses max per_page internally)
        if all_results:
            if limit:
                console.print("[dim]Note: --limit ignored when using --all[/dim]")
            console.print("[dim]Fetching all expenses...[/dim]")

        # Determine per_page: use limit if no client-side filtering needed
        needs_client_filter = paid or unpaid
        if limit and not all_results and not needs_client_filter:
            # Can apply limit server-side (API will clamp to min 5)
            per_page = limit
        else:
            per_page = 50  # default

        expenses = client.list_expenses(q=query, sort="-date", fetch_all=all_results, per_page=per_page)

        # Filter by payment status using next_due_date field (available in list API)
        # next_due_date is None when fully paid, has a date when unpaid
        if paid:
            expenses = [e for e in expenses if e.next_due_date is None]
        elif unpaid:
            expenses = [e for e in expenses if e.next_due_date is not None]

        # Apply limit when needed (client-side filters, or limit < API min of 5)
        if limit is not None and limit > 0 and not all_results:
            if needs_client_filter or limit < 5:
                expenses = expenses[:limit]

        display_expenses_table(expenses)

    except typer.BadParameter:
        raise
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise typer.Exit(1)


# ============================================================================
# SHOW COMMAND
# ============================================================================

@app.command()
def show(
    expense_id: Annotated[int, typer.Argument(help="Expense ID to show")],
):
    """Show detailed view of a single expense."""
    try:
        client = FICClient()
        expense = client.get_expense(expense_id)
        display_expense_details(expense)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise typer.Exit(1)


# ============================================================================
# CONFIGS COMMAND
# ============================================================================

@app.command()
def configs():
    """Configure FIC credentials and default settings."""
    from .config import ConfigWizard

    wizard = ConfigWizard()
    if not wizard.run():
        raise typer.Exit(1)


def get_default_payment_account() -> int | None:
    """Get the default payment account ID from environment."""
    import os
    from dotenv import load_dotenv

    load_dotenv()
    account_id = os.getenv("FIC_DEFAULT_ACCOUNT_ID")
    if account_id:
        try:
            return int(account_id)
        except ValueError:
            return None
    return None


# ============================================================================
# PAY COMMAND
# ============================================================================

@app.command()
def pay(
    expense_id: Annotated[
        Optional[int],
        typer.Argument(help="Expense ID to mark as paid"),
    ] = None,
    installment: Annotated[
        Optional[int],
        typer.Option("--installment", "-i", help="Mark only this installment as paid (1-indexed)"),
    ] = None,
    payment_date: Annotated[
        Optional[str],
        typer.Option("--date", "-d", help="Payment date (default: today, format: YYYY-MM-DD)"),
    ] = None,
    supplier: Annotated[
        Optional[str],
        typer.Option("--supplier", "-s", help="Mark all expenses from this supplier as paid"),
    ] = None,
    from_date: Annotated[
        Optional[str],
        typer.Option("--from", help="Mark expenses from this date as paid"),
    ] = None,
    to_date: Annotated[
        Optional[str],
        typer.Option("--to", help="Mark expenses up to this date as paid"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation for batch operations"),
    ] = False,
):
    """
    Mark expense(s) as paid.

    Can mark a single expense, a specific installment, or batch by supplier/date range.
    Uses the default payment account (run 'fic-expenses configs' to set up).
    """
    try:
        # Get payment account from config
        payment_account_id = get_default_payment_account()
        if not payment_account_id:
            console.print("[red]Error:[/red] No default payment account configured.")
            console.print("Run [cyan]fic-expenses configs[/cyan] to set up your credentials and payment account.")
            raise typer.Exit(1)

        client = FICClient()
        actual_payment_date = parse_date(payment_date) or date.today()
        actual_from_date = parse_date(from_date)
        actual_to_date = parse_date(to_date)

        # Single expense
        if expense_id is not None:
            if installment:
                console.print(f"Marking installment {installment} of expense #{expense_id} as paid...")
            else:
                console.print(f"Marking expense #{expense_id} as paid...")

            expense = client.mark_expense_paid(
                document_id=expense_id,
                payment_account_id=payment_account_id,
                paid_date=actual_payment_date,
                installment_index=installment,
            )
            console.print(f"[green]✓[/green] Expense #{expense.id} updated")
            display_expense_details(expense)
            return

        # Batch by supplier or date range
        if not supplier and not actual_from_date and not actual_to_date:
            console.print("[red]Error:[/red] Provide expense_id or use --supplier/--from/--to for batch")
            raise typer.Exit(1)

        filter_obj = PaymentFilter(
            supplier=supplier,
            from_date=actual_from_date,
            to_date=actual_to_date,
        )
        query = filter_obj.to_query()
        expenses = client.list_expenses(q=query)

        # Filter to only unpaid using next_due_date (available in list API)
        unpaid_expenses = [e for e in expenses if e.next_due_date is not None]

        if not unpaid_expenses:
            console.print("[yellow]No unpaid expenses match the criteria.[/yellow]")
            return

        # Show what will be marked
        console.print(f"\n[bold]Found {len(unpaid_expenses)} unpaid expense(s):[/bold]")
        display_expenses_table(unpaid_expenses)

        # Confirm
        if not yes:
            if not confirm(f"Mark these {len(unpaid_expenses)} expense(s) as paid?"):
                console.print("[yellow]Cancelled.[/yellow]")
                return

        # Process
        for exp in unpaid_expenses:
            client.mark_expense_paid(
                document_id=exp.id,
                payment_account_id=payment_account_id,
                paid_date=actual_payment_date,
            )
            console.print(f"[green]✓[/green] Marked expense #{exp.id} as paid")

        console.print(f"\n[bold green]Done![/bold green] Marked {len(unpaid_expenses)} expense(s) as paid.")

    except typer.BadParameter:
        raise
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise typer.Exit(1)


# ============================================================================
# CREATE COMMAND
# ============================================================================

@app.command()
def create(
    supplier: Annotated[
        Optional[str],
        typer.Option("--supplier", "-s", help="Supplier name"),
    ] = None,
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-D", help="Expense description"),
    ] = None,
    category: Annotated[
        Optional[str],
        typer.Option("--category", "-c", help="Expense category"),
    ] = None,
    amount_net: Annotated[
        Optional[float],
        typer.Option("--amount-net", "-a", help="Net amount (before VAT)"),
    ] = None,
    vat_rate: Annotated[
        float,
        typer.Option("--vat-rate", "-v", help="VAT rate percentage"),
    ] = 22.0,
    expense_date: Annotated[
        Optional[str],
        typer.Option("--date", "-d", help="Expense date (YYYY-MM-DD)"),
    ] = None,
    installments: Annotated[
        int,
        typer.Option("--installments", "-n", help="Number of payment installments"),
    ] = 1,
    first_due: Annotated[
        Optional[str],
        typer.Option("--first-due", help="First installment due date (YYYY-MM-DD)"),
    ] = None,
    recurrence: Annotated[
        Optional[RecurrencePeriod],
        typer.Option("--recurrence", "-r", help="Recurrence period"),
    ] = None,
    occurrences: Annotated[
        int,
        typer.Option("--occurrences", "-o", help="Number of recurring expenses"),
    ] = 1,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation"),
    ] = False,
):
    """
    Create a new expense.

    Without arguments, starts an interactive wizard.
    With arguments, creates expense directly (use --yes to skip confirmation).
    """
    try:
        # Interactive mode if no supplier provided
        if supplier is None:
            expense_input = prompt_expense_wizard()
            if not confirm_expense_creation(expense_input):
                console.print("[yellow]Cancelled.[/yellow]")
                return
        else:
            # CLI mode - validate required fields
            if amount_net is None:
                console.print("[red]Error:[/red] --amount-net is required in CLI mode")
                raise typer.Exit(1)

            actual_expense_date = parse_date(expense_date) or date.today()
            actual_first_due = parse_date(first_due)

            expense_input = ExpenseInput(
                supplier=supplier,
                description=description,
                category=category,
                amount_net=amount_net,
                vat_rate=vat_rate,
                expense_date=actual_expense_date,
                installments=installments,
                first_due=actual_first_due,
                recurrence=recurrence,
                occurrences=occurrences,
            )

            # Show and confirm
            if not yes:
                if not confirm_expense_creation(expense_input):
                    console.print("[yellow]Cancelled.[/yellow]")
                    return

        # Create expense(s)
        client = FICClient()
        created_ids = []

        for i in range(expense_input.occurrences):
            # Calculate date shift for recurrence
            if i > 0 and expense_input.recurrence:
                months_shift = expense_input.recurrence.to_months() * i
                current_date = add_months(expense_input.expense_date, months_shift)
                current_first_due = add_months(expense_input.first_due, months_shift) if expense_input.first_due else None
            else:
                current_date = expense_input.expense_date
                current_first_due = expense_input.first_due

            # Create payment installments
            payments = None
            if expense_input.installments >= 1:
                payments = create_payment_installments(
                    total_amount=expense_input.amount_gross,
                    num_installments=expense_input.installments,
                    start_date=current_first_due or current_date,
                )

            # Create expense
            expense = client.create_expense(
                supplier_name=expense_input.supplier,
                description=expense_input.description,
                category=expense_input.category,
                amount_net=expense_input.amount_net,
                amount_vat=expense_input.amount_vat,
                expense_date=current_date,
                payments=payments,
            )

            created_ids.append(expense.id)
            year_suffix = f" ({current_date.year})" if expense_input.occurrences > 1 else ""
            console.print(f"[green]✓[/green] Created expense #{expense.id}{year_suffix}")

        console.print(f"\n[bold green]Done![/bold green] Created {len(created_ids)} expense(s).")

        # Show first created expense
        if created_ids:
            expense = client.get_expense(created_ids[0])
            display_expense_details(expense)

    except typer.BadParameter:
        raise
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
