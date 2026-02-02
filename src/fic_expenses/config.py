"""Configuration wizard using Textual TUI."""

import os
from pathlib import Path

from dotenv import dotenv_values, set_key
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.validation import Function
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

import fattureincloud_python_sdk
from fattureincloud_python_sdk.api import InfoApi


def mask_token(token: str, visible_chars: int = 4) -> str:
    """Mask a token showing only first/last N characters."""
    if not token or len(token) <= visible_chars * 2:
        return token
    return f"{token[:visible_chars]}{'*' * 20}{token[-visible_chars:]}"


def get_env_path() -> Path:
    """Get the path to the .env file."""
    # Look in current directory first, then script directory
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        return cwd_env
    # Default to current directory for new files
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
    """
    Validate credentials by making an API call.

    Returns:
        Tuple of (is_valid, message)
    """
    if not access_token or not access_token.strip():
        return False, "Access token is required"

    if not company_id or not company_id.strip():
        return False, "Company ID is required"

    try:
        company_id_int = int(company_id.strip())
    except ValueError:
        return False, "Company ID must be a number"

    # Try to make an API call
    try:
        config = fattureincloud_python_sdk.Configuration()
        config.access_token = access_token.strip()

        api_client = fattureincloud_python_sdk.ApiClient(config)
        api = InfoApi(api_client)

        # This will fail with invalid credentials or wrong company
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
    """
    Fetch payment accounts from the API.

    Returns:
        List of (id, name) tuples
    """
    config = fattureincloud_python_sdk.Configuration()
    config.access_token = access_token

    api_client = fattureincloud_python_sdk.ApiClient(config)
    api = InfoApi(api_client)

    response = api.list_payment_accounts(company_id=company_id)
    accounts = response.data or []

    return [(acc.id, acc.name) for acc in accounts]


class ConfigWizard(App[bool]):
    """Textual app for configuring FIC credentials."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        padding: 1 2;
    }

    #tabs-container {
        height: auto;
        max-height: 100%;
    }

    .section-title {
        text-style: bold;
        margin-bottom: 1;
    }

    .help-text {
        color: $text-muted;
        margin-bottom: 1;
    }

    .input-label {
        margin-top: 1;
        margin-bottom: 0;
    }

    Input {
        margin-bottom: 1;
    }

    #validate-button {
        margin-top: 1;
        width: auto;
    }

    #validation-status {
        margin-top: 1;
        height: 1;
    }

    .status-success {
        color: $success;
    }

    .status-error {
        color: $error;
    }

    .status-pending {
        color: $warning;
    }

    #account-list {
        height: auto;
        max-height: 10;
        margin-top: 1;
    }

    #current-account {
        margin-top: 1;
        color: $text-muted;
    }

    #button-bar {
        dock: bottom;
        height: auto;
        padding: 1 2;
        background: $surface;
        border-top: solid $border;
    }

    #button-bar Button {
        margin-right: 1;
    }

    #save-button {
        background: $success;
    }

    #cancel-button {
        background: $error;
    }

    .disabled-tab-note {
        color: $text-muted;
        text-style: italic;
        margin-top: 2;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self):
        super().__init__()
        self.current_config = get_current_config()
        self.credentials_valid = False
        self.validated_token: str | None = None
        self.validated_company_id: int | None = None
        self.payment_accounts: list[tuple[int, str]] = []
        self.selected_account_id: int | None = None

        # If we have existing config, pre-validate
        if self.current_config["access_token"] and self.current_config["company_id"]:
            self.selected_account_id = (
                int(self.current_config["default_account_id"])
                if self.current_config["default_account_id"]
                else None
            )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)

        with Container(id="main-container"):
            with TabbedContent(id="tabs-container"):
                with TabPane("Auth", id="auth-tab"):
                    yield Static(
                        "Get credentials from: https://fattureincloud.it/connessioni/",
                        classes="help-text",
                    )

                    yield Label("Access Token", classes="input-label")
                    yield Input(
                        value=self.current_config["access_token"] or "",
                        placeholder="Enter your access token",
                        password=True,
                        id="token-input",
                    )

                    yield Label("Company ID", classes="input-label")
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

                    yield Button("Validate", id="validate-button", variant="primary")
                    yield Static("", id="validation-status")

                with TabPane("Account", id="account-tab", disabled=True):
                    yield Static(
                        "Select default payment account:",
                        classes="section-title",
                    )
                    yield OptionList(id="account-list")
                    yield Static("", id="current-account")
                    yield Static(
                        "Validate credentials first to see accounts",
                        classes="disabled-tab-note",
                        id="account-disabled-note",
                    )

        with Horizontal(id="button-bar"):
            yield Button("Save", id="save-button", variant="success")
            yield Button("Cancel", id="cancel-button", variant="error")

        yield Footer()

    def on_mount(self) -> None:
        """Focus the first input on mount."""
        self.title = "FIC Expenses Configuration"
        self.query_one("#token-input", Input).focus()

        # If we have existing credentials, validate them automatically
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

        self.call_from_thread(self.show_validation_pending)
        valid, message = validate_credentials(token, company)

        if valid:
            self.validated_token = token.strip()
            self.validated_company_id = int(company.strip())
            self.credentials_valid = True

            # Fetch payment accounts
            try:
                self.payment_accounts = fetch_payment_accounts(
                    self.validated_token, self.validated_company_id
                )
            except Exception:
                self.payment_accounts = []

            self.call_from_thread(self.show_validation_success, message)
        else:
            self.credentials_valid = False
            self.call_from_thread(self.show_validation_error, message)

    def show_validation_pending(self) -> None:
        """Show validation in progress."""
        status = self.query_one("#validation-status", Static)
        status.update("Validating...")
        status.set_classes("status-pending")

    def show_validation_success(self, message: str) -> None:
        """Show validation success and enable account tab."""
        status = self.query_one("#validation-status", Static)
        status.update(f"[green]{message}[/green]")
        status.set_classes("status-success")

        # Enable and populate account tab
        account_tab = self.query_one("#account-tab", TabPane)
        account_tab.disabled = False

        # Hide the disabled note
        self.query_one("#account-disabled-note", Static).display = False

        # Populate account list
        account_list = self.query_one("#account-list", OptionList)
        account_list.clear_options()

        for acc_id, acc_name in self.payment_accounts:
            is_current = acc_id == self.selected_account_id
            label = f"{acc_name} {'(current)' if is_current else ''}"
            account_list.add_option(Option(label, id=str(acc_id)))

        # Show current account info
        if self.selected_account_id:
            current_name = next(
                (name for aid, name in self.payment_accounts if aid == self.selected_account_id),
                "Unknown",
            )
            self.query_one("#current-account", Static).update(
                f"Current: [cyan]{current_name}[/cyan] (ID: {self.selected_account_id})"
            )

        if not self.payment_accounts:
            self.query_one("#current-account", Static).update(
                "[yellow]No payment accounts found. Create one in Fatture in Cloud first.[/yellow]"
            )

    def show_validation_error(self, message: str) -> None:
        """Show validation error."""
        status = self.query_one("#validation-status", Static)
        status.update(f"[red]{message}[/red]")
        status.set_classes("status-error")

        # Disable account tab
        account_tab = self.query_one("#account-tab", TabPane)
        account_tab.disabled = True

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
                f"Selected: [cyan]{account_name}[/cyan] (ID: {self.selected_account_id})"
            )

    @on(Button.Pressed, "#save-button")
    def action_save(self) -> None:
        """Save configuration to .env file."""
        if not self.credentials_valid:
            self.notify("Please validate credentials first", severity="error")
            return

        env_path = get_env_path()

        # Create .env if it doesn't exist
        if not env_path.exists():
            env_path.touch()

        # Save credentials
        set_key(str(env_path), "FIC_ACCESS_TOKEN", self.validated_token)
        set_key(str(env_path), "FIC_COMPANY_ID", str(self.validated_company_id))

        # Save default account if selected
        if self.selected_account_id:
            set_key(str(env_path), "FIC_DEFAULT_ACCOUNT_ID", str(self.selected_account_id))

        self.notify("Configuration saved!", severity="information")
        self.exit(True)

    @on(Button.Pressed, "#cancel-button")
    def action_cancel(self) -> None:
        """Cancel without saving."""
        self.exit(False)

    def key_escape(self) -> None:
        """Handle escape key."""
        self.action_cancel()
