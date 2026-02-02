"""Expense detail screen."""

from datetime import date
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Button, Rule
from rich.text import Text
from rich.panel import Panel

from fattureincloud_python_sdk.models import ReceivedDocument

if TYPE_CHECKING:
    from ..app import FICExpensesApp


class DetailsScreen(Screen):
    """Screen displaying expense details and payment schedule."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("backspace", "go_back", "Back", show=False),
        Binding("p", "pay_all", "Pay All", show=True),
        Binding("1", "pay_installment(1)", "Pay #1", show=False),
        Binding("2", "pay_installment(2)", "Pay #2", show=False),
        Binding("3", "pay_installment(3)", "Pay #3", show=False),
        Binding("4", "pay_installment(4)", "Pay #4", show=False),
        Binding("5", "pay_installment(5)", "Pay #5", show=False),
        Binding("6", "pay_installment(6)", "Pay #6", show=False),
        Binding("7", "pay_installment(7)", "Pay #7", show=False),
        Binding("8", "pay_installment(8)", "Pay #8", show=False),
        Binding("9", "pay_installment(9)", "Pay #9", show=False),
    ]

    DEFAULT_CSS = """
    DetailsScreen {
        padding: 1 2;
    }

    DetailsScreen #back-header {
        height: 1;
        margin-bottom: 1;
    }

    DetailsScreen #back-label {
        width: auto;
    }

    DetailsScreen #expense-id-label {
        dock: right;
        width: auto;
        color: $text-muted;
    }

    DetailsScreen #expense-header {
        height: auto;
        padding: 1;
        margin-bottom: 1;
        border: round $primary;
    }

    DetailsScreen #supplier-name {
        text-style: bold;
    }

    DetailsScreen #expense-description {
        color: $text-muted;
    }

    DetailsScreen .detail-section {
        margin-bottom: 1;
        padding: 1;
        border: solid $surface-lighten-2;
    }

    DetailsScreen .section-title {
        text-style: bold;
        padding-bottom: 1;
    }

    DetailsScreen .detail-row {
        height: auto;
        layout: horizontal;
    }

    DetailsScreen .detail-label {
        width: 16;
        color: $text-muted;
    }

    DetailsScreen .detail-value {
        width: 1fr;
    }

    DetailsScreen #payments-container {
        height: auto;
        max-height: 20;
    }

    DetailsScreen .payment-row {
        height: 1;
        padding: 0 1;
    }

    DetailsScreen .payment-paid {
        color: $success;
    }

    DetailsScreen .payment-unpaid {
        color: $warning;
    }

    DetailsScreen #loading-details {
        text-align: center;
        padding: 2;
        color: $text-muted;
    }
    """

    def __init__(self, expense_id: int) -> None:
        super().__init__()
        self.expense_id = expense_id
        self._expense: ReceivedDocument | None = None

    def compose(self) -> ComposeResult:
        """Create details screen layout."""
        with Horizontal(id="back-header"):
            yield Static("← Back (Esc)", id="back-label")
            yield Static(f"Expense #{self.expense_id}", id="expense-id-label")

        yield Static("Loading expense details...", id="loading-details")

    def on_mount(self) -> None:
        """Load expense details when mounted."""
        self._load_expense()

    def _load_expense(self) -> None:
        """Load expense details from API."""
        # If reloading, clear existing content and show loading indicator
        try:
            self.query_one("#loading-details", Static)
        except Exception:
            # Loading indicator doesn't exist - we're reloading
            # Remove existing content (VerticalScroll) and re-add loading
            try:
                content = self.query_one(VerticalScroll)
                content.remove()
            except Exception:
                pass
            self.mount(Static("Reloading expense details...", id="loading-details"))

        self.run_worker(self._fetch_expense, exclusive=True, thread=True)

    def _fetch_expense(self) -> None:
        """Fetch expense details in background thread."""
        from ..api import FICClient

        try:
            client = FICClient()
            expense = client.get_expense(self.expense_id)
            self.app.call_from_thread(self._display_expense, expense)

            # Update quota display
            if client.last_quota:
                self.app.update_quota(client.last_quota)
        except Exception as e:
            self.app.call_from_thread(self._display_error, str(e))

    def _display_expense(self, expense: ReceivedDocument) -> None:
        """Display expense details."""
        self._expense = expense

        # Remove loading message
        loading = self.query_one("#loading-details", Static)
        loading.remove()

        # Build detail view
        container = VerticalScroll()
        self.mount(container)

        # Header with supplier and description
        header = Container(id="expense-header")
        container.mount(header)

        supplier_name = expense.entity.name if expense.entity else "Unknown"
        header.mount(Static(supplier_name, id="supplier-name"))

        if expense.description:
            header.mount(Static(expense.description, id="expense-description"))

        # Basic info section
        info_section = Container(classes="detail-section")
        container.mount(info_section)

        info_section.mount(Static("Details", classes="section-title"))

        # Date
        date_row = Horizontal(classes="detail-row")
        info_section.mount(date_row)
        date_row.mount(Static("Date", classes="detail-label"))
        date_str = expense.var_date.strftime("%Y-%m-%d") if expense.var_date else "-"
        date_row.mount(Static(date_str, classes="detail-value"))

        # Category
        if expense.category:
            cat_row = Horizontal(classes="detail-row")
            info_section.mount(cat_row)
            cat_row.mount(Static("Category", classes="detail-label"))
            cat_row.mount(Static(expense.category, classes="detail-value"))

        # Amounts section
        amounts_section = Container(classes="detail-section")
        container.mount(amounts_section)

        amounts_section.mount(Static("Amounts", classes="section-title"))

        # Net
        net_row = Horizontal(classes="detail-row")
        amounts_section.mount(net_row)
        net_row.mount(Static("Net", classes="detail-label"))
        net_str = f"€{expense.amount_net:,.2f}" if expense.amount_net else "-"
        net_row.mount(Static(net_str, classes="detail-value"))

        # VAT
        vat_row = Horizontal(classes="detail-row")
        amounts_section.mount(vat_row)
        vat_row.mount(Static("VAT", classes="detail-label"))
        vat_str = f"€{expense.amount_vat:,.2f}" if expense.amount_vat else "-"
        vat_row.mount(Static(vat_str, classes="detail-value"))

        # Gross
        gross_row = Horizontal(classes="detail-row")
        amounts_section.mount(gross_row)
        gross_row.mount(Static("Gross", classes="detail-label"))
        gross = (expense.amount_net or 0) + (expense.amount_vat or 0)
        gross_row.mount(Static(f"€{gross:,.2f}", classes="detail-value"))

        # Payments section
        if expense.payments_list:
            payments_section = Container(classes="detail-section")
            container.mount(payments_section)

            payments_section.mount(Static("Payment Schedule", classes="section-title"))

            payments_container = Container(id="payments-container")
            payments_section.mount(payments_container)

            for i, payment in enumerate(expense.payments_list, 1):
                is_paid = payment.status == "paid"
                icon = "✓" if is_paid else "○"
                style_class = "payment-paid" if is_paid else "payment-unpaid"

                amount_str = f"€{payment.amount:,.2f}" if payment.amount else "-"
                due_str = payment.due_date.strftime("%b %d, %Y") if payment.due_date else "-"

                if is_paid and payment.paid_date:
                    paid_str = f"paid {payment.paid_date.strftime('%b %d')}"
                elif not is_paid:
                    paid_str = f"[press {i}]" if i <= 9 else ""
                else:
                    paid_str = ""

                text = Text()
                text.append(f" {icon} ", style="bold green" if is_paid else "bold yellow")
                text.append(f"Rata {i}")
                text.append(" │ ")
                text.append(amount_str)
                text.append(" │ ")
                text.append(f"due {due_str}")
                if paid_str:
                    text.append(" │ ")
                    text.append(paid_str, style="dim")

                payment_row = Static(text, classes=f"payment-row {style_class}")
                payments_container.mount(payment_row)

    def _display_error(self, error_message: str) -> None:
        """Display error message."""
        try:
            loading = self.query_one("#loading-details", Static)
            loading.update(f"Error loading expense: {error_message}")
        except Exception:
            # Loading indicator doesn't exist, mount an error message
            self.mount(Static(f"Error loading expense: {error_message}", id="loading-details"))

    def action_go_back(self) -> None:
        """Go back to expenses list."""
        self.app.pop_screen()

    def action_pay_all(self) -> None:
        """Pay all unpaid installments."""
        if self._expense:
            from ..dialogs.pay import PayDialog
            self.app.push_screen(PayDialog([self._expense]), self._on_pay_result)

    def action_pay_installment(self, installment: int) -> None:
        """Pay a specific installment."""
        if self._expense:
            from ..dialogs.pay import PayDialog
            self.app.push_screen(
                PayDialog([self._expense], installment_index=installment),
                self._on_pay_result,
            )

    def _on_pay_result(self, paid: bool) -> None:
        """Handle pay dialog result."""
        if paid:
            # Reload expense details
            self._load_expense()
