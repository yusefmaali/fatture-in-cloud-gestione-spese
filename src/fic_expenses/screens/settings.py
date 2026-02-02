"""Settings screen for configuring FIC credentials."""

from pathlib import Path

from dotenv import dotenv_values, set_key
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.validation import Function
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    OptionList,
    Static,
)
from textual.widgets.option_list import Option

import fattureincloud_python_sdk
from fattureincloud_python_sdk.api import InfoApi


def get_env_path() -> Path:
    """Get the path to the .env file."""
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        return cwd_env
    return cwd_env


def get_current_config() -> dict[str, str | None]:
    """Read current configuration from .env file."""
    env_path = get_env_path()
    if env_path.exists():
        values = dotenv_values(env_path)
        return {
            "access_token": values.get("FIC_ACCESS_TOKEN"),
            "company_id": values.get("FIC_COMPANY_ID"),
            "default_account_id": values.get("FIC_DEFAULT_ACCOUNT_ID"),
        }
    return {
        "access_token": None,
        "company_id": None,
        "default_account_id": None,
    }


def validate_credentials(access_token: str, company_id: str) -> tuple[bool, str]:
    """Validate credentials by making an API call."""
    if not access_token or not access_token.strip():
        return False, "Access token is required"

    if not company_id or not company_id.strip():
        return False, "Company ID is required"

    try:
        company_id_int = int(company_id.strip())
    except ValueError:
        return False, "Company ID must be a number"

    try:
        config = fattureincloud_python_sdk.Configuration()
        config.access_token = access_token.strip()

        api_client = fattureincloud_python_sdk.ApiClient(config)
        api = InfoApi(api_client)

        api.list_payment_accounts(company_id=company_id_int)
        return True, "Credentials valid!"

    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            return False, "Invalid access token"
        elif "403" in error_msg or "Forbidden" in error_msg:
            return False, "Access denied for this company"
        elif "404" in error_msg:
            return False, "Company not found"
        else:
            return False, f"API error: {error_msg[:50]}"


def fetch_payment_accounts(
    access_token: str, company_id: int
) -> list[tuple[int, str]]:
    """Fetch payment accounts from the API."""
    config = fattureincloud_python_sdk.Configuration()
    config.access_token = access_token

    api_client = fattureincloud_python_sdk.ApiClient(config)
    api = InfoApi(api_client)

    response = api.list_payment_accounts(company_id=company_id)
    accounts = response.data or []

    return [(acc.id, acc.name) for acc in accounts]


class SettingsScreen(Screen):
    """Settings screen for configuring API credentials and payment account."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("ctrl+s", "save", "Save", show=True),
    ]

    DEFAULT_CSS = """
    SettingsScreen {
        padding: 1 2;
    }

    SettingsScreen #settings-container {
        height: 1fr;
    }

    SettingsScreen .settings-section {
        margin-bottom: 2;
        padding: 1;
        border: solid $surface-lighten-2;
    }

    SettingsScreen .section-title {
        text-style: bold;
        padding-bottom: 1;
    }

    SettingsScreen .help-text {
        color: $text-muted;
        padding-bottom: 1;
    }

    SettingsScreen Label {
        padding: 1 0 0 0;
    }

    SettingsScreen Input {
        margin-bottom: 1;
    }

    SettingsScreen #validate-button {
        margin: 1 0;
    }

    SettingsScreen #validation-status {
        padding: 1;
        margin: 1 0;
    }

    SettingsScreen .status-success {
        color: $success;
        background: $success-darken-3;
    }

    SettingsScreen .status-error {
        color: $error;
        background: $error-darken-3;
    }

    SettingsScreen .status-pending {
        color: $warning;
    }

    SettingsScreen #account-list {
        height: 10;
        margin: 1 0;
    }

    SettingsScreen #current-account {
        color: $text-muted;
        padding: 1 0;
    }

    SettingsScreen #button-bar {
        dock: bottom;
        height: auto;
        padding: 1 0;
        border-top: solid $surface-lighten-2;
    }

    SettingsScreen #button-bar Button {
        margin-right: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.current_config = get_current_config()
        self.credentials_valid = False
        self.validated_token: str | None = None
        self.validated_company_id: int | None = None
        self.payment_accounts: list[tuple[int, str]] = []
        self.selected_account_id: int | None = None

        if self.current_config["default_account_id"]:
            try:
                self.selected_account_id = int(self.current_config["default_account_id"])
            except ValueError:
                pass

    def compose(self) -> ComposeResult:
        """Create settings screen layout."""
        with VerticalScroll(id="settings-container"):
            # API Credentials Section
            with Container(classes="settings-section"):
                yield Static("API Credentials", classes="section-title")
                yield Static(
                    "Get credentials from: https://fattureincloud.it/connessioni/",
                    classes="help-text",
                )

                yield Label("Access Token")
                yield Input(
                    value=self.current_config["access_token"] or "",
                    placeholder="Enter your access token",
                    password=True,
                    id="token-input",
                )

                yield Label("Company ID")
                yield Input(
                    value=self.current_config["company_id"] or "",
                    placeholder="Enter your company ID",
                    id="company-input",
                    validators=[
                        Function(
                            lambda v: v.isdigit() if v else True,
                            "Must be a number",
                        )
                    ],
                )

                yield Button("Validate Credentials", id="validate-button", variant="primary")
                yield Static("", id="validation-status")

            # Payment Account Section
            with Container(classes="settings-section", id="account-section"):
                yield Static("Default Payment Account", classes="section-title")
                yield Static(
                    "Select the account to use when marking expenses as paid",
                    classes="help-text",
                )

                yield OptionList(id="account-list")
                yield Static("Validate credentials to see available accounts", id="current-account")

        # Bottom buttons
        with Horizontal(id="button-bar"):
            yield Button("Save", id="save-button", variant="success")
            yield Button("Back", id="back-button", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Auto-validate existing credentials on mount."""
        if self.current_config["access_token"] and self.current_config["company_id"]:
            self.run_validation()

    @on(Button.Pressed, "#validate-button")
    def handle_validate(self) -> None:
        """Handle validate button press."""
        self.run_validation()

    @work(thread=True)
    def run_validation(self) -> None:
        """Run credential validation in background thread."""
        token = self.query_one("#token-input", Input).value
        company = self.query_one("#company-input", Input).value

        self.app.call_from_thread(self.show_validation_pending)
        valid, message = validate_credentials(token, company)

        if valid:
            self.validated_token = token.strip()
            self.validated_company_id = int(company.strip())
            self.credentials_valid = True

            try:
                self.payment_accounts = fetch_payment_accounts(
                    self.validated_token, self.validated_company_id
                )
            except Exception:
                self.payment_accounts = []

            self.app.call_from_thread(self.show_validation_success, message)
        else:
            self.credentials_valid = False
            self.app.call_from_thread(self.show_validation_error, message)

    def show_validation_pending(self) -> None:
        """Show validation in progress."""
        status = self.query_one("#validation-status", Static)
        status.update("Validating...")
        status.set_classes("status-pending")

    def show_validation_success(self, message: str) -> None:
        """Show validation success and populate account list."""
        status = self.query_one("#validation-status", Static)
        status.update(f"✓ {message}")
        status.set_classes("status-success")

        # Populate account list
        account_list = self.query_one("#account-list", OptionList)
        account_list.clear_options()

        for acc_id, acc_name in self.payment_accounts:
            is_current = acc_id == self.selected_account_id
            label = f"{acc_name} {'✓' if is_current else ''}"
            account_list.add_option(Option(label, id=str(acc_id)))

        # Update current account display
        if self.selected_account_id:
            current_name = next(
                (name for aid, name in self.payment_accounts if aid == self.selected_account_id),
                "Unknown",
            )
            self.query_one("#current-account", Static).update(
                f"Current: {current_name} (ID: {self.selected_account_id})"
            )
        elif self.payment_accounts:
            self.query_one("#current-account", Static).update(
                "Select an account from the list above"
            )
        else:
            self.query_one("#current-account", Static).update(
                "No payment accounts found. Create one in Fatture in Cloud first."
            )

    def show_validation_error(self, message: str) -> None:
        """Show validation error."""
        status = self.query_one("#validation-status", Static)
        status.update(f"✗ {message}")
        status.set_classes("status-error")

        # Clear account list
        self.query_one("#account-list", OptionList).clear_options()
        self.query_one("#current-account", Static).update(
            "Validate credentials to see available accounts"
        )

    @on(OptionList.OptionSelected, "#account-list")
    def handle_account_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle account selection."""
        if event.option.id:
            self.selected_account_id = int(event.option.id)
            account_name = next(
                (name for aid, name in self.payment_accounts if aid == self.selected_account_id),
                "Unknown",
            )
            self.query_one("#current-account", Static).update(
                f"Selected: {account_name} (ID: {self.selected_account_id})"
            )

    @on(Button.Pressed, "#save-button")
    def action_save(self) -> None:
        """Save configuration to .env file."""
        if not self.credentials_valid:
            self.notify("Please validate credentials first", severity="error")
            return

        env_path = get_env_path()

        if not env_path.exists():
            env_path.touch()

        set_key(str(env_path), "FIC_ACCESS_TOKEN", self.validated_token)
        set_key(str(env_path), "FIC_COMPANY_ID", str(self.validated_company_id))

        if self.selected_account_id:
            set_key(str(env_path), "FIC_DEFAULT_ACCOUNT_ID", str(self.selected_account_id))

        self.notify("Configuration saved!", severity="information")
        self.action_go_back()

    @on(Button.Pressed, "#back-button")
    def action_go_back(self) -> None:
        """Go back to previous screen."""
        self.app.pop_screen()
