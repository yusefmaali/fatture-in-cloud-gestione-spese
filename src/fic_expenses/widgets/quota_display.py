"""API quota display widget."""

from textual.reactive import reactive
from textual.widget import Widget
from textual.app import ComposeResult
from rich.text import Text

from ..api import QuotaInfo


class QuotaDisplay(Widget):
    """Compact API quota display for the header.

    Shows hourly and monthly API usage with color coding:
    - White: usage below 90%
    - Red: usage at or above 90%
    """

    DEFAULT_CSS = """
    QuotaDisplay {
        dock: right;
        width: auto;
        height: 1;
        padding: 0 1;
    }
    """

    quota: reactive[QuotaInfo | None] = reactive(None)

    def render(self) -> Text:
        """Render the quota display."""
        if self.quota is None:
            return Text("API: --/--h --/--m", style="dim")

        h_used = self.quota.hourly_used
        h_limit = self.quota.hourly_limit
        m_used = self.quota.monthly_used
        m_limit = self.quota.monthly_limit

        # Determine styles based on percentage
        h_style = "bold red" if self.quota.hourly_percent >= 0.9 else ""
        m_style = "bold red" if self.quota.monthly_percent >= 0.9 else ""

        text = Text("API: ")
        text.append(f"{h_used}/{h_limit}h", style=h_style)
        text.append(" ")
        text.append(f"{m_used}/{m_limit}m", style=m_style)

        return text

    def update_quota(self, quota: QuotaInfo | None) -> None:
        """Update the displayed quota information."""
        self.quota = quota
