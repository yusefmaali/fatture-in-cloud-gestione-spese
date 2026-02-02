"""Error screen for displaying API or connection errors."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Horizontal
from textual.widgets import Static, Button


class ErrorScreen(Screen):
    """Error screen shown when API calls fail."""

    BINDINGS = [
        ("r", "retry", "Retry"),
        ("s", "settings", "Settings"),
        ("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    ErrorScreen {
        align: center middle;
    }

    ErrorScreen #error-container {
        width: 60;
        height: auto;
        padding: 2 4;
        background: $surface;
        border: solid $error;
    }

    ErrorScreen #error-icon {
        text-align: center;
        color: $error;
        text-style: bold;
        padding-bottom: 1;
    }

    ErrorScreen #error-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }

    ErrorScreen #error-message {
        text-align: center;
        color: $text-muted;
        padding-bottom: 2;
    }

    ErrorScreen #error-buttons {
        align: center middle;
        height: auto;
    }

    ErrorScreen Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        title: str = "Connection Error",
        message: str = "Could not connect to Fatture in Cloud API",
        error_detail: str | None = None,
    ) -> None:
        super().__init__()
        self.error_title = title
        self.error_message = message
        self.error_detail = error_detail

    def compose(self) -> ComposeResult:
        """Create error screen layout."""
        with Container(id="error-container"):
            yield Static("⚠️", id="error-icon")
            yield Static(self.error_title, id="error-title")

            message = self.error_message
            if self.error_detail:
                message += f"\n\nError: {self.error_detail}"
            yield Static(message, id="error-message")

            with Horizontal(id="error-buttons"):
                yield Button("🔄 Retry", variant="primary", id="retry-btn")
                yield Button("⚙️ Settings", variant="default", id="settings-btn")
                yield Button("Quit", variant="error", id="quit-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "retry-btn":
            self.action_retry()
        elif event.button.id == "settings-btn":
            self.action_settings()
        elif event.button.id == "quit-btn":
            self.action_quit()

    def action_retry(self) -> None:
        """Retry loading expenses."""
        self.app.pop_screen()
        self.app.load_expenses()

    def action_settings(self) -> None:
        """Go to settings screen."""
        from .settings import SettingsScreen
        self.app.push_screen(SettingsScreen())

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
