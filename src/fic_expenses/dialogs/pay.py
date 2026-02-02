"""Pay dialog for marking expenses as paid."""

import os
from datetime import date
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Button, Input, Label
from rich.text import Text

from fattureincloud_python_sdk.models import ReceivedDocument

from ..api import FICClient


class PayDialog(ModalScreen[bool]):
    """Modal dialog for paying expenses."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "confirm", "Confirm", show=True),
    ]

    DEFAULT_CSS = """
    PayDialog {
        align: center middle;
    }

    PayDialog #dialog-container {
        width: 75;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        background: $surface;
        border: thick $primary;
    }

    PayDialog #dialog-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $surface-lighten-2;
        margin-bottom: 1;
    }

    PayDialog .expense-item {
        padding: 0 0 0 1;
    }

    PayDialog .expense-list {
        padding: 1;
        margin-bottom: 1;
        background: $surface-darken-1;
        max-height: 10;
    }

    PayDialog .total-line {
        text-style: bold;
        padding: 1;
        border-top: solid $surface-lighten-2;
    }

    PayDialog .form-group {
        margin: 1 0;
    }

    PayDialog Label {
        padding: 0 0 0 0;
    }

    PayDialog Input {
        margin-top: 0;
    }

    PayDialog #dialog-buttons {
        height: auto;
        align: center middle;
        padding-top: 1;
        border-top: solid $surface-lighten-2;
    }

    PayDialog Button {
        margin: 0 1;
    }

    PayDialog #error-message {
        color: $error;
        padding: 1;
        display: none;
    }

    PayDialog #error-message.visible {
        display: block;
    }

    PayDialog #processing {
        text-align: center;
        color: $text-muted;
        padding: 1;
        display: none;
    }

    PayDialog #processing.visible {
        display: block;
    }
    """

    def __init__(
        self,
        expenses: list[ReceivedDocument],
        installment_index: int | None = None,
    ) -> None:
        super().__init__()
        self.expenses = expenses
        self.installment_index = installment_index
        self._default_account_id = self._get_default_account_id()

    def _get_default_account_id(self) -> int | None:
        """Get default payment account ID from environment."""
        account_id = os.getenv("FIC_DEFAULT_ACCOUNT_ID")
        if account_id:
            try:
                return int(account_id)
            except ValueError:
                pass
        return None

    def compose(self) -> ComposeResult:
        """Create dialog layout."""
        with Container(id="dialog-container"):
            # Title
            if len(self.expenses) == 1:
                title = "Pay Expense"
                if self.installment_index:
                    title = f"Pay Installment #{self.installment_index}"
            else:
                title = f"Pay {len(self.expenses)} Expenses"
            yield Static(title, id="dialog-title")

            # Expense list
            with Vertical(classes="expense-list"):
                total_amount = 0.0
                for expense in self.expenses:
                    supplier = expense.entity.name if expense.entity else "Unknown"
                    amount = self._get_payable_amount(expense)
                    total_amount += amount

                    text = Text()
                    text.append(f"#{expense.id} ", style="dim")
                    text.append(supplier)
                    text.append(f"  €{amount:,.2f}", style="bold")

                    yield Static(text, classes="expense-item")

                yield Static(f"Total: €{total_amount:,.2f}", classes="total-line")

            # Payment date input
            with Container(classes="form-group"):
                # For batch: use each installment's due date by default (leave empty)
                # For single: default to installment due date (if specific) or expense date
                if len(self.expenses) == 1:
                    yield Label("Payment Date")
                    default_date = self._get_default_payment_date(self.expenses[0])
                    yield Input(
                        value=default_date,
                        placeholder="YYYY-MM-DD",
                        id="payment-date",
                    )
                else:
                    yield Label("Payment Date (leave empty to use each installment's due date)")
                    yield Input(
                        value="",
                        placeholder="YYYY-MM-DD or empty",
                        id="payment-date",
                    )

            # Error message
            yield Static("", id="error-message")

            # Processing indicator
            yield Static("Processing payment...", id="processing")

            # Buttons
            with Horizontal(id="dialog-buttons"):
                yield Button("Confirm", variant="primary", id="confirm-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def _get_default_payment_date(self, expense: ReceivedDocument) -> str:
        """Get the default payment date for display in the input field.

        For specific installment: use that installment's due_date
        For all installments: use expense date (each will use its own due_date on submit)
        """
        if self.installment_index and expense.payments_list:
            idx = self.installment_index - 1
            if idx < len(expense.payments_list):
                payment = expense.payments_list[idx]
                if payment.due_date:
                    return payment.due_date.strftime("%Y-%m-%d")
        # Fallback to expense date
        if expense.var_date:
            return expense.var_date.strftime("%Y-%m-%d")
        return ""

    def _get_payable_amount(self, expense: ReceivedDocument) -> float:
        """Get the amount to be paid for an expense."""
        if self.installment_index and expense.payments_list:
            # Specific installment
            if self.installment_index <= len(expense.payments_list):
                payment = expense.payments_list[self.installment_index - 1]
                if payment.status != "paid":
                    return payment.amount or 0.0
            return 0.0
        elif expense.payments_list:
            # All unpaid installments
            return sum(
                p.amount or 0.0
                for p in expense.payments_list
                if p.status != "paid"
            )
        else:
            # No payment schedule - use gross amount
            return (expense.amount_net or 0) + (expense.amount_vat or 0)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "confirm-btn":
            self.action_confirm()
        elif event.button.id == "cancel-btn":
            self.action_cancel()

    def action_confirm(self) -> None:
        """Process payment."""
        # Validate account ID
        if not self._default_account_id:
            self._show_error(
                "No payment account configured. Press 's' to open Settings."
            )
            return

        # Get and validate date (None means use each expense's date)
        date_input = self.query_one("#payment-date", Input)
        payment_date: date | None = None

        if date_input.value.strip():
            try:
                payment_date = date.fromisoformat(date_input.value)
            except ValueError:
                self._show_error("Invalid date format. Use YYYY-MM-DD.")
                return

        # Show processing indicator
        self._show_processing()

        # Process payments in worker thread
        self.run_worker(
            lambda: self._process_payments(payment_date),
            exclusive=True,
            thread=True,
        )

    def _process_payments(self, payment_date: date | None) -> None:
        """Process payments for all expenses (runs in thread).

        Args:
            payment_date: Date to use for all payments, or None to use each installment's due date.
        """
        try:
            client = FICClient()

            for expense in self.expenses:
                # Determine the payment date:
                # 1. User-provided date takes precedence
                # 2. For specific installment: use that installment's due_date
                # 3. For "pay all": pass None so API uses each installment's due_date
                if payment_date:
                    expense_payment_date = payment_date
                elif self.installment_index and expense.payments_list:
                    # Specific installment - use its due_date
                    idx = self.installment_index - 1
                    if idx < len(expense.payments_list):
                        expense_payment_date = expense.payments_list[idx].due_date
                    else:
                        expense_payment_date = None  # Let API handle fallback
                else:
                    # Pay all - let API use each installment's due_date
                    expense_payment_date = None

                client.mark_expense_paid(
                    document_id=expense.id,
                    payment_account_id=self._default_account_id,
                    paid_date=expense_payment_date,
                    installment_index=self.installment_index,
                )

            # Update quota display
            if client.last_quota:
                self.app.update_quota(client.last_quota)

            self.app.call_from_thread(self._payment_success)
        except Exception as e:
            self.app.call_from_thread(self._show_error, str(e))
            self.app.call_from_thread(self._hide_processing)

    def _payment_success(self) -> None:
        """Handle successful payment."""
        self.dismiss(True)

    def _show_error(self, message: str) -> None:
        """Show error message."""
        error_widget = self.query_one("#error-message", Static)
        error_widget.update(f"Error: {message}")
        error_widget.add_class("visible")

    def _show_processing(self) -> None:
        """Show processing indicator."""
        self.query_one("#processing", Static).add_class("visible")
        self.query_one("#confirm-btn", Button).disabled = True
        self.query_one("#cancel-btn", Button).disabled = True

    def _hide_processing(self) -> None:
        """Hide processing indicator."""
        self.query_one("#processing", Static).remove_class("visible")
        self.query_one("#confirm-btn", Button).disabled = False
        self.query_one("#cancel-btn", Button).disabled = False

    def action_cancel(self) -> None:
        """Cancel and close dialog."""
        self.dismiss(False)
