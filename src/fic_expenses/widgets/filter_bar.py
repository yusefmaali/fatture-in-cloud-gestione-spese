"""Filter bar widget for filtering expenses."""

from datetime import date
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Label, Select, Input, Button
from textual.widget import Widget
from textual import on


class FilterBar(Widget):
    """Filter controls for the expenses list."""

    DEFAULT_CSS = """
    FilterBar {
        height: 3;
        padding: 0 1;
        background: $surface-darken-1;
        layout: horizontal;
    }

    FilterBar Label {
        padding: 1 1 0 0;
        width: auto;
    }

    FilterBar Select {
        width: 12;
        margin-right: 2;
    }

    FilterBar #limit-filter {
        width: 13;
    }

    FilterBar #status-filter {
        width: 14;
    }

    FilterBar Input {
        width: 20;
        margin-right: 2;
    }

    FilterBar #supplier-filter {
        width: 30;
    }

    FilterBar .date-input {
        width: 18;
    }

    FilterBar #apply-btn {
        margin-left: 1;
    }
    """

    DEFAULT_LIMIT = 50

    class ApplyFilters(Message):
        """Posted when Apply button is pressed."""

        def __init__(
            self,
            status: str,
            supplier: str,
            from_date: str,
            to_date: str,
            limit: int | None,  # None means fetch all
        ) -> None:
            self.status = status
            self.supplier = supplier
            self.from_date = from_date
            self.to_date = to_date
            self.limit = limit
            super().__init__()

    def compose(self) -> ComposeResult:
        """Create filter bar layout."""
        with Horizontal():
            yield Label("Status:")
            yield Select(
                [
                    ("Unpaid", "unpaid"),
                    ("Paid", "paid"),
                ],
                id="status-filter",
                prompt="All",
                allow_blank=True,
            )

            yield Label("Supplier:")
            yield Input(id="supplier-filter", placeholder="Filter...")

            yield Label("From:")
            yield Input(
                id="from-date",
                placeholder="YYYY-MM-DD",
                classes="date-input",
            )

            yield Label("To:")
            yield Input(
                id="to-date",
                placeholder="YYYY-MM-DD",
                classes="date-input",
            )

            yield Label("Limit:")
            yield Select(
                [
                    ("50", 50),
                    ("100", 100),
                    ("200", 200),
                    ("All", -1),  # -1 means fetch all
                ],
                id="limit-filter",
                value=self.DEFAULT_LIMIT,
                allow_blank=False,
            )

            yield Button("Apply", id="apply-btn", variant="primary")

    @on(Button.Pressed, "#apply-btn")
    def handle_apply(self) -> None:
        """Handle Apply button press."""
        self._post_apply_filters()

    def _post_apply_filters(self) -> None:
        """Post an ApplyFilters message with current values."""
        limit_select = self.query_one("#limit-filter", Select)
        status_select = self.query_one("#status-filter", Select)
        supplier_input = self.query_one("#supplier-filter", Input)
        from_input = self.query_one("#from-date", Input)
        to_input = self.query_one("#to-date", Input)

        # Parse limit (-1 means fetch all, converted to None)
        limit_value = limit_select.value
        limit = None if limit_value == -1 else int(limit_value)

        # Select.BLANK is returned when no option is selected (allow_blank=True)
        status_value = status_select.value
        if status_value is Select.BLANK or status_value is None:
            status = "all"
        else:
            status = str(status_value)

        self.post_message(
            self.ApplyFilters(
                status=status,
                supplier=supplier_input.value,
                from_date=from_input.value,
                to_date=to_input.value,
                limit=limit,
            )
        )

    def get_filters(self) -> dict:
        """Get current filter values as a dictionary."""
        limit_select = self.query_one("#limit-filter", Select)
        status_select = self.query_one("#status-filter", Select)
        supplier_input = self.query_one("#supplier-filter", Input)
        from_input = self.query_one("#from-date", Input)
        to_input = self.query_one("#to-date", Input)

        # Parse limit (-1 means fetch all, converted to None)
        limit_value = limit_select.value
        limit = None if limit_value == -1 else int(limit_value)

        # Select.BLANK is returned when no option is selected (allow_blank=True)
        status_value = status_select.value
        if status_value is Select.BLANK or status_value is None:
            status = "all"
        else:
            status = str(status_value)

        return {
            "limit": limit,
            "status": status,
            "supplier": supplier_input.value,
            "from_date": from_input.value,
            "to_date": to_input.value,
        }

    def clear_filters(self) -> None:
        """Reset all filters to default values."""
        self.query_one("#limit-filter", Select).value = self.DEFAULT_LIMIT
        self.query_one("#status-filter", Select).value = Select.BLANK
        self.query_one("#supplier-filter", Input).value = ""
        self.query_one("#from-date", Input).value = ""
        self.query_one("#to-date", Input).value = ""

    def build_api_query(self) -> str | None:
        """Build FIC API query string from current filters.

        Returns None if no filters are set.
        Uses FIC query syntax: field = 'value' AND field LIKE '%value%'
        """
        filters = self.get_filters()
        conditions = []

        # Supplier filter (LIKE query)
        if filters["supplier"]:
            # Escape single quotes in supplier name
            supplier = filters["supplier"].replace("'", "''")
            conditions.append(f"entity.name LIKE '%{supplier}%'")

        # Date range filters
        if filters["from_date"]:
            conditions.append(f"date >= '{filters['from_date']}'")

        if filters["to_date"]:
            conditions.append(f"date <= '{filters['to_date']}'")

        # Note: Status (paid/unpaid) cannot be filtered via API query,
        # it will be handled client-side based on next_due_date

        if conditions:
            return " AND ".join(conditions)
        return None
