"""Rich display formatters for expenses."""

from datetime import date
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


def format_currency(amount: float | None) -> str:
    """Format amount as Euro currency."""
    if amount is None:
        return "-"
    return f"€{amount:,.2f}"


def get_payment_status(
    payments: list[Any] | None,
    next_due_date: date | None = None,
) -> tuple[str, date | None]:
    """
    Get payment status summary and next due date.

    Args:
        payments: List of payment items (from show API) or None (from list API)
        next_due_date: Next due date field from the expense (available in list API)

    Returns:
        Tuple of (status_text, next_due_date)
    """
    # If payments_list is available (from show API), use detailed info
    if payments is not None:
        if len(payments) == 0:
            return ("No payments", None)

        paid_count = sum(1 for p in payments if p.status == "paid")
        total_count = len(payments)

        if paid_count == total_count:
            return ("Paid ✓", None)

        # Find next unpaid due date
        unpaid = [p for p in payments if p.status != "paid"]
        unpaid_dates = [p.due_date for p in unpaid if p.due_date]
        next_due = min(unpaid_dates) if unpaid_dates else None

        if total_count == 1:
            return ("Unpaid", next_due)

        return (f"{paid_count}/{total_count} paid", next_due)

    # payments_list is None (list API) - use next_due_date field
    if next_due_date is not None:
        return ("Unpaid", next_due_date)
    else:
        return ("Paid ✓", None)


def calculate_expenses_stats(expenses: list[Any]) -> dict:
    """Calculate statistics for a list of expenses."""
    today = date.today()

    # Initialize counters
    total_gross = 0.0
    paid_count = 0
    paid_total = 0.0
    unpaid_count = 0
    unpaid_total = 0.0
    overdue_count = 0
    dates = []
    suppliers = set()

    for exp in expenses:
        amount = exp.amount_gross or 0.0
        total_gross += amount

        # Payment status (using next_due_date from list API)
        if exp.next_due_date is None:
            paid_count += 1
            paid_total += amount
        else:
            unpaid_count += 1
            unpaid_total += amount
            # Check if overdue
            if exp.next_due_date < today:
                overdue_count += 1

        # Collect dates
        if exp.var_date:
            dates.append(exp.var_date)

        # Collect suppliers
        if exp.entity and exp.entity.name:
            suppliers.add(exp.entity.name)

    return {
        "total_count": len(expenses),
        "total_gross": total_gross,
        "paid_count": paid_count,
        "paid_total": paid_total,
        "unpaid_count": unpaid_count,
        "unpaid_total": unpaid_total,
        "overdue_count": overdue_count,
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
        "suppliers_count": len(suppliers),
    }


def display_expenses_stats(stats: dict) -> None:
    """Display expense statistics."""
    console.print()
    console.print(f"[bold]Total: {stats['total_count']} expense(s)[/bold]  •  {format_currency(stats['total_gross'])}")

    # Payment status line
    paid_str = f"[green]Paid: {stats['paid_count']} ({format_currency(stats['paid_total'])})[/green]"
    unpaid_str = f"[red]Unpaid: {stats['unpaid_count']} ({format_currency(stats['unpaid_total'])})[/red]"
    console.print(f"├─ {paid_str}  •  {unpaid_str}")

    # Overdue line (only if there are unpaid expenses)
    if stats['overdue_count'] > 0:
        console.print(f"├─ [bold red]Overdue: {stats['overdue_count']}[/bold red]")

    # Period and suppliers line
    period_parts = []
    if stats['date_min'] and stats['date_max']:
        if stats['date_min'] == stats['date_max']:
            period_parts.append(f"Date: {stats['date_min']}")
        else:
            period_parts.append(f"Period: {stats['date_min']} → {stats['date_max']}")

    period_parts.append(f"Suppliers: {stats['suppliers_count']}")

    console.print(f"└─ [dim]{' • '.join(period_parts)}[/dim]")


def display_expenses_table(expenses: list[Any]) -> None:
    """Display a table of expenses."""
    if not expenses:
        console.print("[yellow]No expenses found.[/yellow]")
        return

    table = Table(title="Expenses", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Date", justify="center")
    table.add_column("Supplier", style="bold")
    table.add_column("Description")
    table.add_column("Gross", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Next Due", justify="center")

    for exp in expenses:
        status, next_due = get_payment_status(exp.payments_list, exp.next_due_date)

        # Color status
        if "✓" in status:
            status_text = f"[green]{status}[/green]"
        elif "Unpaid" in status:
            status_text = f"[red]{status}[/red]"
        else:
            status_text = f"[yellow]{status}[/yellow]"

        table.add_row(
            str(exp.id),
            str(exp.var_date) if exp.var_date else "-",
            exp.entity.name if exp.entity else "-",
            (exp.description[:30] + "...") if exp.description and len(exp.description) > 30 else (exp.description or "-"),
            format_currency(exp.amount_gross),
            status_text,
            str(next_due) if next_due else "-",
        )

    console.print(table)

    # Calculate and display stats
    stats = calculate_expenses_stats(expenses)
    display_expenses_stats(stats)


def display_expense_details(expense: Any) -> None:
    """Display detailed view of a single expense."""
    # Header
    console.print()
    console.print(Panel(
        f"[bold]Expense #{expense.id}[/bold]",
        style="cyan",
        expand=False
    ))

    # Main details
    details = Table(show_header=False, box=None, padding=(0, 2))
    details.add_column("Label", style="dim")
    details.add_column("Value")

    details.add_row("Supplier:", expense.entity.name if expense.entity else "-")
    details.add_row("Date:", str(expense.var_date) if expense.var_date else "-")
    details.add_row("Description:", expense.description or "-")
    details.add_row("Category:", expense.category or "-")
    details.add_row("", "")
    details.add_row("Net:", format_currency(expense.amount_net))
    details.add_row("VAT:", format_currency(expense.amount_vat))
    details.add_row("Gross:", f"[bold]{format_currency(expense.amount_gross)}[/bold]")

    console.print(details)

    # Payment schedule
    if expense.payments_list:
        console.print()
        console.print("[bold]Payment Schedule[/bold]")
        console.print("─" * 50)

        for i, payment in enumerate(expense.payments_list, 1):
            if payment.status == "paid":
                icon = "[green]✓[/green]"
                paid_info = f" [dim](paid {payment.paid_date})[/dim]" if payment.paid_date else ""
            else:
                icon = "[yellow]○[/yellow]"
                paid_info = ""

            console.print(
                f"  {icon} Rata {i}: {format_currency(payment.amount)} - "
                f"due {payment.due_date}{paid_info}"
            )

    console.print()


def confirm(message: str) -> bool:
    """Ask for confirmation."""
    from rich.prompt import Confirm
    return Confirm.ask(message)
