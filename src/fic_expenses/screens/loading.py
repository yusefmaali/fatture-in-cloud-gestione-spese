"""Loading screen displayed while fetching data."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Center, Middle, Vertical
from textual.widgets import Static, LoadingIndicator


class LoadingScreen(Screen):
    """Loading screen shown while fetching expenses from the API."""

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    LoadingScreen {
        background: $surface;
    }

    LoadingScreen #loading-box {
        width: 50;
        height: 9;
        padding: 2 4;
        border: round $primary;
        background: $surface-darken-1;
        align: center middle;
    }

    LoadingScreen LoadingIndicator {
        width: 100%;
        height: 1;
        content-align: center middle;
    }

    LoadingScreen #loading-message {
        width: 100%;
        text-align: center;
        padding-top: 1;
        color: $text;
    }
    """

    def __init__(self, message: str = "Loading expenses...") -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        """Create loading screen layout."""
        with Center():
            with Middle():
                with Vertical(id="loading-box"):
                    yield LoadingIndicator()
                    yield Static(self.message, id="loading-message")

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
