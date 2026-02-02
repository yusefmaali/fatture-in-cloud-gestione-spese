"""Right-side statistics panel widget."""

from collections import defaultdict
from datetime import date, datetime
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static
from textual.widget import Widget
from rich.text import Text

from fattureincloud_python_sdk.models import ReceivedDocument


class StatsPanel(Widget):
    """Panel showing expense statistics."""

    DEFAULT_CSS = """
    StatsPanel {
        width: 32;
        height: 100%;
        background: $surface-darken-1;
        border-left: solid $primary;
        padding: 1;
    }

    StatsPanel .stats-section {
        margin-bottom: 1;
    }

    StatsPanel .stats-header {
        text-style: bold;
        color: $primary-lighten-2;
        margin-bottom: 0;
    }

    StatsPanel .stats-value {
        padding-left: 1;
    }

    StatsPanel .stats-value-highlight {
        padding-left: 1;
        color: $error;
    }

    StatsPanel .stats-divider {
        color: $primary-darken-1;
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        """Create the stats panel layout."""
        with Vertical():
            # Overdue section
            yield Static("⚠ OVERDUE", classes="stats-header")
            yield Static("0 expenses (€0.00)", id="overdue-stats", classes="stats-value")

            yield Static("─" * 28, classes="stats-divider")

            # Time-based section
            yield Static("📅 TIME PERIODS", classes="stats-header")
            yield Static("This month: €0.00", id="this-month", classes="stats-value")
            yield Static("Last month: €0.00", id="last-month", classes="stats-value")
            yield Static("Year to date: €0.00", id="ytd", classes="stats-value")
            yield Static("Monthly avg: €0.00", id="monthly-avg", classes="stats-value")

            yield Static("─" * 28, classes="stats-divider")

            # Supplier section
            yield Static("🏢 TOP SUPPLIERS", classes="stats-header")
            yield Static("", id="top-supplier-1", classes="stats-value")
            yield Static("", id="top-supplier-2", classes="stats-value")
            yield Static("", id="top-supplier-3", classes="stats-value")

            yield Static("─" * 28, classes="stats-divider")

            yield Static("📊 BY SUPPLIER", classes="stats-header")
            yield Static("", id="supplier-count", classes="stats-value")

    def update_stats(self, expenses: list[ReceivedDocument]) -> None:
        """Update all statistics from the expense list."""
        self._update_overdue(expenses)
        self._update_time_periods(expenses)
        self._update_supplier_insights(expenses)

    def _update_overdue(self, expenses: list[ReceivedDocument]) -> None:
        """Update overdue statistics."""
        today = date.today()
        overdue_count = 0
        overdue_total = 0.0

        for expense in expenses:
            if expense.next_due_date is not None and expense.next_due_date < today:
                overdue_count += 1
                overdue_total += (expense.amount_net or 0) + (expense.amount_vat or 0)

        widget = self.query_one("#overdue-stats", Static)
        text = f"{overdue_count} expenses (€{overdue_total:,.2f})"

        if overdue_count > 0:
            widget.update(Text(text, style="bold red"))
            widget.add_class("stats-value-highlight")
            widget.remove_class("stats-value")
        else:
            widget.update(Text(text, style="green"))
            widget.remove_class("stats-value-highlight")
            widget.add_class("stats-value")

    def _update_time_periods(self, expenses: list[ReceivedDocument]) -> None:
        """Update time-based aggregate statistics."""
        today = date.today()
        this_month_start = today.replace(day=1)

        # Calculate last month start/end
        if today.month == 1:
            last_month_start = today.replace(year=today.year - 1, month=12, day=1)
        else:
            last_month_start = today.replace(month=today.month - 1, day=1)
        last_month_end = this_month_start

        # Year start
        year_start = today.replace(month=1, day=1)

        this_month_total = 0.0
        last_month_total = 0.0
        ytd_total = 0.0
        monthly_totals: dict[tuple[int, int], float] = defaultdict(float)

        for expense in expenses:
            if not expense.var_date:
                continue

            gross = (expense.amount_net or 0) + (expense.amount_vat or 0)
            exp_date = expense.var_date

            # This month
            if exp_date >= this_month_start:
                this_month_total += gross

            # Last month
            if last_month_start <= exp_date < last_month_end:
                last_month_total += gross

            # Year to date
            if exp_date >= year_start:
                ytd_total += gross

            # Monthly totals for average calculation
            monthly_totals[(exp_date.year, exp_date.month)] += gross

        # Calculate monthly average (exclude current month if incomplete)
        completed_months = [
            (y, m) for y, m in monthly_totals.keys()
            if (y, m) != (today.year, today.month)
        ]
        if completed_months:
            avg_total = sum(monthly_totals[k] for k in completed_months)
            monthly_avg = avg_total / len(completed_months)
        else:
            monthly_avg = 0.0

        # Update widgets
        self.query_one("#this-month", Static).update(
            f"This month: €{this_month_total:,.2f}"
        )
        self.query_one("#last-month", Static).update(
            f"Last month: €{last_month_total:,.2f}"
        )
        self.query_one("#ytd", Static).update(
            f"Year to date: €{ytd_total:,.2f}"
        )
        self.query_one("#monthly-avg", Static).update(
            f"Monthly avg: €{monthly_avg:,.2f}"
        )

    def _update_supplier_insights(self, expenses: list[ReceivedDocument]) -> None:
        """Update supplier statistics."""
        supplier_totals: dict[str, float] = defaultdict(float)
        supplier_counts: dict[str, int] = defaultdict(int)

        for expense in expenses:
            supplier = expense.entity.name if expense.entity else "Unknown"
            gross = (expense.amount_net or 0) + (expense.amount_vat or 0)
            supplier_totals[supplier] += gross
            supplier_counts[supplier] += 1

        # Top 3 suppliers by total amount
        sorted_suppliers = sorted(
            supplier_totals.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        for i, (supplier, total) in enumerate(sorted_suppliers, 1):
            widget = self.query_one(f"#top-supplier-{i}", Static)
            # Truncate long supplier names
            display_name = supplier[:18] + "..." if len(supplier) > 21 else supplier
            widget.update(f"{i}. {display_name}: €{total:,.2f}")

        # Clear remaining slots if less than 3 suppliers
        for i in range(len(sorted_suppliers) + 1, 4):
            self.query_one(f"#top-supplier-{i}", Static).update("")

        # Supplier count summary
        unique_suppliers = len(supplier_counts)
        self.query_one("#supplier-count", Static).update(
            f"{unique_suppliers} unique suppliers"
        )
