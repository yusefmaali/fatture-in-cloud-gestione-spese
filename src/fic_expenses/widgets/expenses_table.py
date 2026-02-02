"""Expenses table widget with multi-selection support."""

from datetime import date

from textual.binding import Binding
from textual.events import Key
from textual.message import Message
from textual.widgets import DataTable
from textual.reactive import reactive
from rich.text import Text

from fattureincloud_python_sdk.models import ReceivedDocument


class ExpensesTable(DataTable):
    """DataTable for displaying expenses with multi-selection support."""

    BINDINGS = [
        Binding("enter", "select_cursor", "Details", show=True),
        Binding("space", "toggle_select", "Select", show=True),
        Binding("ctrl+a", "select_all_unpaid", "Select All Unpaid", show=False),
        Binding("escape", "clear_selection", "Clear", show=False),
    ]

    DEFAULT_CSS = """
    ExpensesTable {
        height: 1fr;
    }

    ExpensesTable > .datatable--header {
        background: $primary-darken-1;
        text-style: bold;
    }

    ExpensesTable > .datatable--cursor {
        background: $primary;
    }
    """

    selected_ids: reactive[set[int]] = reactive(set, init=False)

    class SelectionChanged(Message):
        """Posted when selection changes."""

        def __init__(self, selected_ids: set[int], selected_total: float) -> None:
            self.selected_ids = selected_ids
            self.selected_total = selected_total
            super().__init__()

    class ExpenseSelected(Message):
        """Posted when user presses Enter to view details."""

        def __init__(self, expense_id: int) -> None:
            self.expense_id = expense_id
            super().__init__()

    class PayRequested(Message):
        """Posted when user presses P to pay."""

        def __init__(self, expense_ids: set[int]) -> None:
            self.expense_ids = expense_ids
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(cursor_type="row", **kwargs)
        self.selected_ids = set()
        self._expenses: dict[str, ReceivedDocument] = {}  # row_key -> expense
        self._row_to_expense: dict[int, int] = {}  # row index -> expense id
        self._checkbox_column_key = None  # Store checkbox column key

    def on_mount(self) -> None:
        """Set up table columns when mounted."""
        column_keys = self.add_columns("", "ID", "Date", "Supplier", "Net", "VAT", "Gross", "Status", "Due")
        self._checkbox_column_key = column_keys[0]  # First column is checkbox
        self.cursor_type = "row"

    def on_key(self, event: Key) -> None:
        """Handle key events - Space for toggle selection."""
        if event.key == "space":
            self.action_toggle_select()
            event.stop()

    def load_expenses(self, expenses: list[ReceivedDocument]) -> None:
        """Load expenses into the table."""
        self.clear()
        self._expenses.clear()
        self._row_to_expense.clear()
        self.selected_ids = set()

        for idx, expense in enumerate(expenses):
            row_key = self._add_expense_row(expense)
            self._expenses[row_key] = expense
            if expense.id:
                self._row_to_expense[idx] = expense.id

        self._post_selection_changed()

    def _add_expense_row(self, expense: ReceivedDocument) -> str:
        """Add a single expense row to the table."""
        expense_id = expense.id or 0
        is_selected = expense_id in self.selected_ids

        # Selection checkbox
        checkbox = "☑" if is_selected else "☐"

        # Format expense date (verbose: "Jan 15, 2024")
        date_str = "-"
        if expense.var_date:
            date_str = expense.var_date.strftime("%b %d, %Y")

        # Format amounts
        net_amount = expense.amount_net or 0
        vat_amount = expense.amount_vat or 0
        gross_amount = net_amount + vat_amount
        net = f"€{net_amount:,.2f}" if net_amount else "-"
        vat = f"€{vat_amount:,.2f}" if vat_amount else "-"
        gross = f"€{gross_amount:,.2f}" if gross_amount else "-"

        # Get supplier name
        supplier = expense.entity.name if expense.entity else "-"
        if len(supplier) > 25:
            supplier = supplier[:22] + "..."

        # Get payment status
        status, next_due = self._get_payment_status(expense)

        # Format due date (verbose: "Jan 15, 2024")
        due_str = "-"
        if next_due:
            due_str = next_due.strftime("%b %d, %Y")

        row_key = self.add_row(
            checkbox,
            str(expense_id),
            date_str,
            supplier,
            net,
            vat,
            gross,
            status,
            due_str,
            key=str(expense_id),
        )

        return str(row_key)

    def _get_payment_status(self, expense: ReceivedDocument) -> tuple[Text, date | None]:
        """Get payment status and next due date for an expense."""
        # Use next_due_date from list API (payments_list is None in list response)
        if expense.next_due_date is not None:
            # Has unpaid payments
            status = Text("Unpaid", style="bold yellow")
            return status, expense.next_due_date
        else:
            # Fully paid or no payments configured
            status = Text("Paid ✓", style="bold green")
            return status, None

    def action_toggle_select(self) -> None:
        """Toggle selection of current row."""
        if self.cursor_row is None:
            return

        expense_id = self._get_current_expense_id()
        if expense_id is None:
            return

        # Toggle selection
        new_selected = set(self.selected_ids)
        if expense_id in new_selected:
            new_selected.discard(expense_id)
        else:
            new_selected.add(expense_id)

        self.selected_ids = new_selected
        self._update_checkbox(self.cursor_row, expense_id in new_selected)
        self._post_selection_changed()

    def action_clear_selection(self) -> None:
        """Clear all selections."""
        old_selected = set(self.selected_ids)
        self.selected_ids = set()

        # Update all checkboxes
        for row_idx in range(self.row_count):
            self._update_checkbox(row_idx, False)

        self._post_selection_changed()

    def action_select_all_unpaid(self) -> None:
        """Select all unpaid expenses."""
        new_selected = set()

        for row_idx, expense_id in self._row_to_expense.items():
            expense = self._expenses.get(str(expense_id))
            if expense and expense.next_due_date is not None:
                new_selected.add(expense_id)

        self.selected_ids = new_selected

        # Update all checkboxes
        for row_idx in range(self.row_count):
            expense_id = self._row_to_expense.get(row_idx)
            if expense_id:
                self._update_checkbox(row_idx, expense_id in new_selected)

        self._post_selection_changed()

    def action_select_cursor(self) -> None:
        """Open details for current expense."""
        expense_id = self._get_current_expense_id()
        if expense_id is not None:
            self.post_message(self.ExpenseSelected(expense_id))

    def action_pay(self) -> None:
        """Request payment for selected expenses (or current if none selected)."""
        if self.selected_ids:
            self.post_message(self.PayRequested(set(self.selected_ids)))
        else:
            expense_id = self._get_current_expense_id()
            if expense_id is not None:
                self.post_message(self.PayRequested({expense_id}))

    def _get_current_expense_id(self) -> int | None:
        """Get expense ID for current cursor row."""
        if self.cursor_row is None:
            return None
        return self._row_to_expense.get(self.cursor_row)

    def _update_checkbox(self, row_idx: int, selected: bool) -> None:
        """Update checkbox display for a row."""
        checkbox = "☑" if selected else "☐"
        try:
            # Get expense ID from row index, then use as row key
            expense_id = self._row_to_expense.get(row_idx)
            if expense_id is not None and self._checkbox_column_key is not None:
                row_key = str(expense_id)
                self.update_cell(row_key, self._checkbox_column_key, checkbox)
        except (IndexError, KeyError):
            pass

    def _post_selection_changed(self) -> None:
        """Post selection changed message with total amount."""
        total = 0.0
        for expense_id in self.selected_ids:
            expense = self._expenses.get(str(expense_id))
            if expense:
                total += (expense.amount_net or 0) + (expense.amount_vat or 0)

        self.post_message(self.SelectionChanged(set(self.selected_ids), total))

    def get_selected_expenses(self) -> list[ReceivedDocument]:
        """Get list of currently selected expenses."""
        return [
            self._expenses[str(expense_id)]
            for expense_id in self.selected_ids
            if str(expense_id) in self._expenses
        ]
