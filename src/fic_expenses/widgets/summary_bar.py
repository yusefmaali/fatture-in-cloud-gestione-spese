"""Summary bar widget showing expense totals."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static
from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text


class SummaryBar(Widget):
    """Summary bar showing expense counts and totals."""

    DEFAULT_CSS = """
    SummaryBar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
        border-top: solid $primary-darken-2;
    }

    SummaryBar Horizontal {
        height: 1;
    }

    SummaryBar .summary-item {
        width: auto;
        padding: 0 2 0 0;
    }
    """

    total_count: reactive[int] = reactive(0)
    unpaid_count: reactive[int] = reactive(0)
    unpaid_total: reactive[float] = reactive(0.0)
    paid_count: reactive[int] = reactive(0)
    paid_total: reactive[float] = reactive(0.0)
    total_amount: reactive[float] = reactive(0.0)

    def compose(self) -> ComposeResult:
        """Create summary bar layout."""
        with Horizontal():
            yield Static(id="count-summary", classes="summary-item")
            yield Static(id="unpaid-summary", classes="summary-item")
            yield Static(id="paid-summary", classes="summary-item")
            yield Static(id="total-summary", classes="summary-item")

    def watch_total_count(self, count: int) -> None:
        """Update count display when value changes."""
        self._update_display()

    def watch_unpaid_total(self, total: float) -> None:
        """Update display when unpaid total changes."""
        self._update_display()

    def watch_paid_total(self, total: float) -> None:
        """Update display when paid total changes."""
        self._update_display()

    def _update_display(self) -> None:
        """Update all summary displays."""
        try:
            count_widget = self.query_one("#count-summary", Static)
            unpaid_widget = self.query_one("#unpaid-summary", Static)
            paid_widget = self.query_one("#paid-summary", Static)
            total_widget = self.query_one("#total-summary", Static)

            count_widget.update(f"{self.total_count} expenses")

            unpaid_text = Text()
            unpaid_text.append("Unpaid: ", style="dim")
            unpaid_text.append(f"€{self.unpaid_total:,.2f}", style="bold yellow")
            unpaid_widget.update(unpaid_text)

            paid_text = Text()
            paid_text.append("Paid: ", style="dim")
            paid_text.append(f"€{self.paid_total:,.2f}", style="bold green")
            paid_widget.update(paid_text)

            total_text = Text()
            total_text.append("Total: ", style="dim")
            total_text.append(f"€{self.total_amount:,.2f}", style="bold")
            total_widget.update(total_text)
        except Exception:
            pass  # Widgets not yet mounted

    def update_stats(
        self,
        total_count: int,
        unpaid_count: int,
        unpaid_total: float,
        paid_count: int,
        paid_total: float,
        total_amount: float,
    ) -> None:
        """Update all statistics at once."""
        self.total_count = total_count
        self.unpaid_count = unpaid_count
        self.unpaid_total = unpaid_total
        self.paid_count = paid_count
        self.paid_total = paid_total
        self.total_amount = total_amount
