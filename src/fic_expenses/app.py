"""Main FIC Expenses TUI Application."""

from datetime import datetime

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Footer

from fattureincloud_python_sdk.models import ReceivedDocument

from .api import FICClient, QuotaInfo
from .widgets.quota_display import QuotaDisplay
from .widgets.filter_bar import FilterBar
from .widgets.expenses_table import ExpensesTable
from .widgets.summary_bar import SummaryBar
from .widgets.stats_panel import StatsPanel
from .screens.loading import LoadingScreen
from .screens.error import ErrorScreen
from .screens.settings import SettingsScreen


class FICExpensesApp(App):
    """Fatture in Cloud Expenses TUI Application."""

    TITLE = "FIC Expenses"

    # Use Monokai theme
    theme = "monokai"

    CSS = """
    Screen {
        background: $surface;
    }

    #app-header {
        dock: top;
        height: 1;
        background: $primary;
        layout: horizontal;
    }

    #app-title {
        width: 1fr;
        padding: 0 1;
        text-style: bold;
    }

    #main-container {
        height: 1fr;
        layout: horizontal;
    }

    #table-container {
        width: 1fr;
    }

    #selection-bar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $primary;
        display: none;
    }

    #selection-bar.visible {
        display: block;
    }
    """

    BINDINGS = [
        Binding("n", "new_expense", "New", show=True),
        Binding("p", "pay", "Pay", show=True),
        Binding("s", "show_settings", "Settings", show=True),
        Binding("slash", "focus_search", "Search", show=False),
        Binding("x", "quit", "Exit", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._expenses: list[ReceivedDocument] = []
        self._filtered_expenses: list[ReceivedDocument] = []
        self._quota: QuotaInfo | None = None
        self._current_filters: dict = {}  # Track current filter state
        # Worker parameters (stored before worker starts)
        self._load_limit: int | None = 50  # None means fetch all
        self._load_query: str | None = None

    def compose(self) -> ComposeResult:
        """Create the main application layout."""
        # Header with title and quota display
        with Horizontal(id="app-header"):
            yield Static("FIC Expenses", id="app-title")
            yield QuotaDisplay(id="quota-display")

        # Main content
        yield FilterBar(id="filter-bar")

        with Container(id="main-container"):
            with Container(id="table-container"):
                yield ExpensesTable(id="expenses-table")
            yield StatsPanel(id="stats-panel")

        yield Static(id="selection-bar")
        yield SummaryBar(id="summary-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Load expenses when app starts."""
        self.load_expenses()

    def load_expenses(self, limit: int | None = 50, query: str | None = None) -> None:
        """Load expenses - stores params and dispatches to worker.

        Args:
            limit: Number of expenses to fetch. None means fetch all.
            query: FIC API query string for filtering.
        """
        # Store parameters for worker to read (avoids @work decorator arg issues)
        self._load_limit = limit
        self._load_query = query
        self._do_load_expenses()

    @work(thread=True, exclusive=True)
    def _do_load_expenses(self) -> None:
        """Load expenses from API in background thread."""
        # Read parameters stored before worker started
        limit = self._load_limit
        query = self._load_query
        fetch_all = limit is None

        # Show loading indicator
        if fetch_all:
            msg = "Fetching all expenses..."
        elif query:
            msg = "Applying filters..."
        else:
            msg = f"Loading {limit} expenses..."
        self.call_from_thread(self.push_screen, LoadingScreen(msg))

        try:
            client = FICClient()
            expenses = client.list_expenses(limit=limit, sort="-date", q=query)
            self._expenses = expenses

            # Update quota
            if client.last_quota:
                self._quota = client.last_quota
                self.call_from_thread(self._update_quota_display)

            # Update expenses and remove loading
            self.call_from_thread(self._show_expenses)

        except ValueError as e:
            # Missing credentials
            self.call_from_thread(
                self._show_error,
                "Configuration Required",
                "Please configure your API credentials",
                str(e),
            )
        except Exception as e:
            self.call_from_thread(
                self._show_error,
                "Connection Error",
                "Could not connect to Fatture in Cloud API",
                str(e),
            )

    def _show_expenses(self) -> None:
        """Show expenses with loaded data."""
        # Pop loading screen
        self.pop_screen()

        # Show notification with count
        count = len(self._expenses)
        limit = self._load_limit
        mode = "all" if limit is None else f"limit {limit}"
        self.notify(f"Loaded {count} expenses ({mode})")

        # Apply status filter client-side (other filters already applied via API)
        self._apply_status_filter()

        # Focus the expenses table for keyboard navigation
        try:
            table = self.query_one("#expenses-table", ExpensesTable)
            table.focus()
        except Exception:
            pass

    def _show_error(self, title: str, message: str, detail: str) -> None:
        """Show error screen."""
        # Pop loading screen if present
        try:
            self.pop_screen()
        except Exception:
            pass

        self.push_screen(ErrorScreen(title, message, detail))

    def _update_quota_display(self) -> None:
        """Update the quota display widget."""
        try:
            quota_display = self.query_one("#quota-display", QuotaDisplay)
            quota_display.update_quota(self._quota)
        except Exception:
            pass

    def update_quota(self, quota: QuotaInfo) -> None:
        """Public method to update quota from other screens."""
        self._quota = quota
        self._update_quota_display()

    def _apply_status_filter(self) -> None:
        """Apply status filter client-side (API doesn't support status filtering)."""
        status = self._current_filters.get("status", "all")

        filtered = self._expenses

        # Filter by status (client-side only - API doesn't support next_due_date filter)
        if status == "paid":
            filtered = [e for e in filtered if e.next_due_date is None]
        elif status == "unpaid":
            filtered = [e for e in filtered if e.next_due_date is not None]

        self._filtered_expenses = filtered

        # Update table
        table = self.query_one("#expenses-table", ExpensesTable)
        table.load_expenses(filtered)

        # Update summary
        self._update_summary()

        # Update stats panel
        self._update_stats_panel()

    def _update_summary(self) -> None:
        """Update summary bar with current statistics."""
        summary_bar = self.query_one("#summary-bar", SummaryBar)

        total_count = len(self._filtered_expenses)
        unpaid_count = 0
        unpaid_total = 0.0
        paid_count = 0
        paid_total = 0.0

        for expense in self._filtered_expenses:
            gross = (expense.amount_net or 0) + (expense.amount_vat or 0)
            if expense.next_due_date is not None:
                unpaid_count += 1
                unpaid_total += gross
            else:
                paid_count += 1
                paid_total += gross

        total_amount = unpaid_total + paid_total

        summary_bar.update_stats(
            total_count=total_count,
            unpaid_count=unpaid_count,
            unpaid_total=unpaid_total,
            paid_count=paid_count,
            paid_total=paid_total,
            total_amount=total_amount,
        )

    def _update_stats_panel(self) -> None:
        """Update stats panel with current filtered expenses."""
        try:
            stats_panel = self.query_one("#stats-panel", StatsPanel)
            stats_panel.update_stats(self._filtered_expenses)
        except Exception:
            pass

    def on_filter_bar_apply_filters(self, event: FilterBar.ApplyFilters) -> None:
        """Handle Apply button - reload data from API with filters."""
        # Store current filter state
        self._current_filters = {
            "status": event.status,
            "supplier": event.supplier,
            "from_date": event.from_date,
            "to_date": event.to_date,
        }

        # Build API query from filters
        filter_bar = self.query_one("#filter-bar", FilterBar)
        query = filter_bar.build_api_query()

        # Reload data from API with filters and limit
        self.load_expenses(limit=event.limit, query=query)

    def on_expenses_table_selection_changed(
        self, event: ExpensesTable.SelectionChanged
    ) -> None:
        """Handle selection changes in the table."""
        selection_bar = self.query_one("#selection-bar", Static)

        if event.selected_ids:
            count = len(event.selected_ids)
            total = event.selected_total
            selection_bar.update(
                f"{count} selected (€{total:,.2f}) │ P: Pay All │ Esc: Clear │ Ctrl+A: Select All"
            )
            selection_bar.add_class("visible")
        else:
            selection_bar.remove_class("visible")

    def on_expenses_table_expense_selected(
        self, event: ExpensesTable.ExpenseSelected
    ) -> None:
        """Handle expense selection (Enter key)."""
        from .screens.details import DetailsScreen
        self.push_screen(DetailsScreen(event.expense_id), self._on_detail_closed)

    def _on_detail_closed(self, result: None) -> None:
        """Handle detail screen closed - refresh data."""
        # Refresh to pick up any payment changes (re-apply status filter)
        self._apply_status_filter()

    def on_expenses_table_pay_requested(
        self, event: ExpensesTable.PayRequested
    ) -> None:
        """Handle pay request."""
        from .dialogs.pay import PayDialog

        # Get selected expenses
        expenses = []
        for expense_id in event.expense_ids:
            for e in self._filtered_expenses:
                if e.id == expense_id:
                    expenses.append(e)
                    break

        if expenses:
            self.push_screen(PayDialog(expenses), self._on_pay_dialog_result)

    def _on_pay_dialog_result(self, paid: bool) -> None:
        """Handle pay dialog result."""
        if paid:
            # Refresh expenses after payment
            self.load_expenses()

    def action_pay(self) -> None:
        """Trigger pay action on the expenses table."""
        try:
            table = self.query_one("#expenses-table", ExpensesTable)
            table.action_pay()
        except Exception:
            pass

    def action_new_expense(self) -> None:
        """Open create expense wizard."""
        from .dialogs.create.wizard import CreateWizard
        self.push_screen(CreateWizard(), self._on_create_wizard_result)

    def _on_create_wizard_result(self, created: bool) -> None:
        """Handle create wizard result."""
        if created:
            # Refresh expenses after creation
            self.load_expenses()

    def action_show_settings(self) -> None:
        """Show settings screen."""
        self.push_screen(SettingsScreen())

    def action_focus_search(self) -> None:
        """Focus the supplier filter input."""
        try:
            supplier_input = self.query_one("#supplier-filter")
            supplier_input.focus()
        except Exception:
            pass

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()


def main() -> None:
    """Main entry point for the TUI application."""
    app = FICExpensesApp()
    app.run()


if __name__ == "__main__":
    main()
