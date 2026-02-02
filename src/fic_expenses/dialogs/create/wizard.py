"""Create expense wizard dialog."""

from datetime import date
from decimal import Decimal
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Button, Input, Label, Select
from textual.reactive import reactive
from rich.text import Text

from ...api import FICClient, create_payment_installments
from ...models import ExpenseInput
from ...utils import generate_installment_dates, split_amount


class CreateWizard(ModalScreen[bool]):
    """Multi-step wizard for creating expenses."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    DEFAULT_CSS = """
    CreateWizard {
        align: center middle;
    }

    CreateWizard #wizard-container {
        width: 75;
        height: auto;
        max-height: 90%;
        padding: 0;
        background: $surface;
        border: thick $primary;
    }

    CreateWizard #wizard-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $primary;
    }

    CreateWizard #wizard-tabs {
        height: 3;
        border-bottom: solid $surface-lighten-2;
        layout: horizontal;
    }

    CreateWizard .wizard-tab {
        width: 1fr;
        text-align: center;
        padding: 1;
        content-align: center middle;
    }

    CreateWizard .wizard-tab-active {
        color: white;
        text-style: bold;
    }

    CreateWizard .wizard-tab-completed {
        color: $success;
    }

    CreateWizard #wizard-content {
        padding: 1 2;
        height: auto;
        min-height: 15;
        max-height: 30;
    }

    CreateWizard .form-label {
        padding: 1 0 0 0;
    }

    CreateWizard .form-label-first {
        padding: 0;
    }

    CreateWizard .form-required {
        color: $error;
    }

    CreateWizard Input {
        margin-top: 0;
    }

    CreateWizard Select {
        margin-top: 0;
    }

    CreateWizard .preview-box {
        padding: 1;
        margin-top: 1;
        background: $surface-darken-1;
        border: solid $surface-lighten-2;
    }

    CreateWizard .calculated-value {
        padding: 0 0 0 2;
        color: $text-muted;
    }

    CreateWizard .summary-row {
        height: 1;
        layout: horizontal;
    }

    CreateWizard .summary-label {
        width: 16;
        color: $text-muted;
    }

    CreateWizard .summary-value {
        width: 1fr;
    }

    CreateWizard #wizard-buttons {
        height: auto;
        align: center middle;
        padding: 1;
        border-top: solid $surface-lighten-2;
    }

    CreateWizard Button {
        margin: 0 1;
    }

    CreateWizard #error-message {
        color: $error;
        padding: 0 1;
        display: none;
    }

    CreateWizard #error-message.visible {
        display: block;
    }

    CreateWizard #processing {
        text-align: center;
        color: $text-muted;
        padding: 1;
        display: none;
    }

    CreateWizard #processing.visible {
        display: block;
    }

    CreateWizard .recurrence-disabled {
        color: $text-muted;
    }

    CreateWizard .recurrence-preview {
        margin-top: 1;
        padding: 1;
        background: $surface-darken-1;
        border: solid $primary;
    }

    CreateWizard .recurrence-preview-item {
        color: $text;
    }
    """

    current_step: reactive[int] = reactive(1, init=False)

    # Total number of steps in the wizard
    TOTAL_STEPS = 5

    # Form data
    supplier: str = ""
    description: str = ""
    category: str = ""
    amount_net: float = 0.0
    vat_rate: float = 22.0
    expense_date: str = ""
    installments: int = 1
    first_due: str = ""

    # Recurrence data
    recurrence_enabled: bool = False
    recurrence_every_months: int = 3  # Every N months
    recurrence_count: int = 4  # Total number of occurrences

    def __init__(self) -> None:
        super().__init__()
        self.expense_date = date.today().strftime("%Y-%m-%d")

    def compose(self) -> ComposeResult:
        """Create wizard layout."""
        with Container(id="wizard-container"):
            yield Static("Create Expense", id="wizard-title")

            # Step tabs
            with Horizontal(id="wizard-tabs"):
                yield Static("1. Basics", id="tab-1", classes="wizard-tab wizard-tab-active")
                yield Static("2. Amount", id="tab-2", classes="wizard-tab")
                yield Static("3. Payment", id="tab-3", classes="wizard-tab")
                yield Static("4. Recur", id="tab-4", classes="wizard-tab")
                yield Static("5. Review", id="tab-5", classes="wizard-tab")

            # Content area
            with VerticalScroll(id="wizard-content"):
                yield from self._compose_step_1()

            # Error message
            yield Static("", id="error-message")

            # Processing indicator
            yield Static("Creating expense...", id="processing")

            # Buttons
            with Horizontal(id="wizard-buttons"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Next →", variant="primary", id="next-btn")

    def on_mount(self) -> None:
        """Focus first input when wizard opens."""
        self._focus_first_input()

    def _focus_first_input(self) -> None:
        """Focus the first Input or Select widget in the current step."""
        # Delay focus to allow widgets to be mounted
        self.set_timer(0.1, self._do_focus_first_input)

    def _do_focus_first_input(self) -> None:
        """Actually focus the first input (called after delay)."""
        try:
            content = self.query_one("#wizard-content", VerticalScroll)
            # Find first Input or Select widget
            for widget in content.query(Input):
                widget.focus()
                return
            for widget in content.query(Select):
                widget.focus()
                return
            # If no input/select (like Review step), focus the Next button
            self.query_one("#next-btn", Button).focus()
        except Exception:
            pass

    def _build_step_1(self) -> list:
        """Build step 1 widgets: Basic info."""
        return [
            Label(Text.assemble("Supplier ", ("*", "bold red")), classes="form-label-first"),
            Input(value=self.supplier, id="supplier-input", placeholder="e.g., Amazon AWS"),
            Label("Description", classes="form-label"),
            Input(value=self.description, id="description-input", placeholder="Optional"),
            Label("Category", classes="form-label"),
            Input(value=self.category, id="category-input", placeholder="e.g., Software"),
            Label("Expense Date", classes="form-label"),
            Input(value=self.expense_date, id="date-input", placeholder="YYYY-MM-DD"),
        ]

    def _compose_step_1(self) -> ComposeResult:
        """Compose step 1: Basic info (for initial compose only)."""
        for widget in self._build_step_1():
            yield widget

    def _build_step_2(self) -> list:
        """Build step 2 widgets: Amount."""
        vat_amount = self.amount_net * self.vat_rate / 100
        gross = self.amount_net + vat_amount

        return [
            Label(Text.assemble("Net Amount (before VAT) ", ("*", "bold red")), classes="form-label-first"),
            Input(
                value=str(self.amount_net) if self.amount_net else "",
                id="amount-input",
                placeholder="e.g., 100.00",
            ),
            Label("VAT Rate (%)", classes="form-label"),
            Select(
                [
                    ("22%", "22"),
                    ("10%", "10"),
                    ("4%", "4"),
                    ("0%", "0"),
                ],
                value=str(int(self.vat_rate)),
                id="vat-select",
                allow_blank=False,
            ),
            Static("Calculated:", classes="form-label"),
            Static(f"  VAT Amount: €{vat_amount:,.2f}", id="calc-vat"),
            Static(f"  Gross Total: €{gross:,.2f}", id="calc-gross"),
        ]

    def _compose_step_2(self) -> ComposeResult:
        """Compose step 2: Amount (for initial compose only)."""
        for widget in self._build_step_2():
            yield widget

    def _build_step_3(self) -> list:
        """Build step 3 widgets: Payment."""
        widgets = [
            Label("Number of Installments", classes="form-label-first"),
            Input(
                value=str(self.installments),
                id="installments-input",
                placeholder="1-12",
            ),
            Label("First Installment Due Date", classes="form-label"),
            Input(
                value=self.first_due,
                id="first-due-input",
                placeholder="YYYY-MM-DD (default: end of next month)",
            ),
        ]

        # Add preview widgets
        widgets.extend(self._build_installment_preview())
        return widgets

    def _build_installment_preview(self) -> list:
        """Build installment preview widgets."""
        if self.installments <= 0 or self.amount_net <= 0:
            return []

        # Calculate installments
        gross = self.amount_net * (1 + self.vat_rate / 100)

        try:
            if self.first_due:
                start_date = date.fromisoformat(self.first_due)
            else:
                # Default: end of next month
                from ...utils import end_of_month, add_months
                next_month = add_months(date.today(), 1)
                start_date = end_of_month(next_month.year, next_month.month)

            dates = generate_installment_dates(start_date, self.installments)
            amounts = split_amount(gross, self.installments)

            widgets = [Static("Preview:", classes="form-label")]
            for i, (amount, due_date) in enumerate(zip(amounts, dates), 1):
                widgets.append(Static(f"  Rata {i}: €{amount:,.2f} - due {due_date.strftime('%b %d, %Y')}"))
            return widgets
        except Exception:
            return []

    def _compose_step_3(self) -> ComposeResult:
        """Compose step 3: Payment (for initial compose only)."""
        for widget in self._build_step_3():
            yield widget

    def _build_step_4(self) -> list:
        """Build step 4 widgets: Recurrence."""
        widgets = [
            Label("Enable Recurrence", classes="form-label-first"),
            Select(
                [
                    ("No - single expense", "no"),
                    ("Yes - create recurring expenses", "yes"),
                ],
                value="yes" if self.recurrence_enabled else "no",
                id="recurrence-enabled-select",
                allow_blank=False,
            ),
        ]

        if self.recurrence_enabled:
            widgets.extend([
                Label("Repeat Every", classes="form-label"),
                Select(
                    [
                        ("1 month", "1"),
                        ("2 months", "2"),
                        ("3 months (quarterly)", "3"),
                        ("6 months (semi-annual)", "6"),
                        ("12 months (annual)", "12"),
                    ],
                    value=str(self.recurrence_every_months),
                    id="recurrence-every-select",
                    allow_blank=False,
                ),
                Label("Total Occurrences", classes="form-label"),
                Input(
                    value=str(self.recurrence_count),
                    id="recurrence-count-input",
                    placeholder="e.g., 4 (creates 4 separate expenses)",
                ),
            ])

            # Add recurrence preview
            widgets.extend(self._build_recurrence_preview())
        else:
            widgets.append(
                Static(
                    "Recurrence creates multiple separate expenses at regular intervals.\n"
                    "For example: quarterly rent, annual subscriptions.",
                    classes="recurrence-disabled",
                )
            )

        return widgets

    def _build_recurrence_preview(
        self,
        every_months: int | None = None,
        count: int | None = None,
    ) -> list:
        """Build recurrence preview showing all expenses that will be created.

        Args:
            every_months: Override for recurrence_every_months (uses class value if None)
            count: Override for recurrence_count (uses class value if None)

        Returns:
            List of widgets for the preview display.
        """
        # Use provided values or fall back to class state
        effective_every = every_months if every_months is not None else self.recurrence_every_months
        effective_count = count if count is not None else self.recurrence_count

        if not self.recurrence_enabled or effective_count <= 0:
            return []

        try:
            expense_date = date.fromisoformat(self.expense_date)
        except (ValueError, TypeError):
            expense_date = date.today()

        gross = self.amount_net * (1 + self.vat_rate / 100)

        widgets = [Static("Preview - expenses to be created:", classes="form-label")]

        # Generate dates for all occurrences
        from dateutil.relativedelta import relativedelta
        for i in range(min(effective_count, 12)):  # Show max 12 in preview
            occurrence_date = expense_date + relativedelta(months=i * effective_every)
            widgets.append(
                Static(
                    f"  {i + 1}. {occurrence_date.strftime('%b %d, %Y')} - €{gross:,.2f}",
                    classes="recurrence-preview-item",
                )
            )

        if effective_count > 12:
            widgets.append(Static(f"  ... and {effective_count - 12} more"))

        total = gross * effective_count
        widgets.append(Static(f"\n  Total: {effective_count} expenses = €{total:,.2f}"))

        return widgets

    def _compose_step_4(self) -> ComposeResult:
        """Compose step 4: Recurrence (for initial compose only)."""
        for widget in self._build_step_4():
            yield widget

    def _rebuild_recurrence_step(self) -> None:
        """Rebuild the recurrence step to show/hide options."""
        self.run_worker(self._rebuild_recurrence_async(), exclusive=True, group="wizard-content")

    async def _rebuild_recurrence_async(self) -> None:
        """Rebuild recurrence step asynchronously."""
        try:
            content = self.query_one("#wizard-content", VerticalScroll)
            await content.remove_children()
            await content.mount_all(self._build_step_4())
            self._focus_first_input()
        except Exception as e:
            self.app.notify(f"Rebuild error: {e}", severity="error")

    def _update_recurrence_preview(self) -> None:
        """Update the recurrence preview based on current input values.

        This method reads values directly from input widgets and passes them
        as parameters to _build_recurrence_preview(), avoiding class state
        mutation that could lead to corruption on exceptions.
        """
        try:
            # Read current values from widgets (don't mutate class state)
            enabled = self.query_one("#recurrence-enabled-select", Select).value == "yes"

            if not enabled:
                return

            every_select = self.query_one("#recurrence-every-select", Select)
            count_input = self.query_one("#recurrence-count-input", Input)

            every_months = int(every_select.value)
            try:
                count = int(count_input.value.strip())
            except (ValueError, TypeError):
                count = 0

            # Remove existing preview widgets
            content = self.query_one("#wizard-content", VerticalScroll)
            preview_widgets = []
            found_count_input = False
            for widget in list(content.children):
                if found_count_input:
                    preview_widgets.append(widget)
                elif isinstance(widget, Input) and widget.id == "recurrence-count-input":
                    found_count_input = True

            for widget in preview_widgets:
                widget.remove()

            # Build and mount new preview (pass values as parameters, no state mutation)
            for widget in self._build_recurrence_preview(every_months=every_months, count=count):
                content.mount(widget)

        except Exception as e:
            self.app.notify(f"Preview update error: {e}", severity="error")

    def _update_installment_preview(self) -> None:
        """Update the installment preview based on current input values."""
        try:
            # Read current values from inputs
            installments_str = self.query_one("#installments-input", Input).value.strip()
            first_due = self.query_one("#first-due-input", Input).value.strip()

            try:
                installments = int(installments_str)
            except (ValueError, TypeError):
                installments = 0

            # Remove existing preview widgets (those after the first-due-input)
            content = self.query_one("#wizard-content", VerticalScroll)
            preview_widgets = []
            found_first_due = False
            for widget in list(content.children):
                if found_first_due:
                    preview_widgets.append(widget)
                elif isinstance(widget, Input) and widget.id == "first-due-input":
                    found_first_due = True

            for widget in preview_widgets:
                widget.remove()

            # Build new preview
            if installments > 0 and self.amount_net > 0:
                gross = self.amount_net * (1 + self.vat_rate / 100)

                try:
                    if first_due:
                        start_date = date.fromisoformat(first_due)
                    else:
                        from ...utils import end_of_month, add_months
                        next_month = add_months(date.today(), 1)
                        start_date = end_of_month(next_month.year, next_month.month)

                    dates = generate_installment_dates(start_date, installments)
                    amounts = split_amount(gross, installments)

                    # Mount new preview widgets
                    content.mount(Static("Preview:", classes="form-label"))
                    for i, (amount, due_date) in enumerate(zip(amounts, dates), 1):
                        content.mount(Static(f"  Rata {i}: €{amount:,.2f} - due {due_date.strftime('%b %d, %Y')}"))
                except ValueError:
                    # Invalid date format - user is still typing, don't show error
                    pass
                except Exception as e:
                    self.app.notify(f"Installment preview error: {e}", severity="warning")
        except Exception as e:
            self.app.notify(f"Preview update error: {e}", severity="error")

    def _build_step_5(self) -> list:
        """Build step 5 widgets: Review."""
        vat_amount = self.amount_net * self.vat_rate / 100
        gross = self.amount_net + vat_amount
        first_due_str = self.first_due if self.first_due else "(end of next month)"

        widgets = [
            Static("Summary", classes="form-label-first"),
            Static(""),
            Static(f"  Supplier:      {self.supplier or '-'}"),
            Static(f"  Description:   {self.description or '-'}"),
            Static(f"  Date:          {self.expense_date}"),
            Static(f"  Category:      {self.category or '-'}"),
            Static(""),
            Static(f"  Net:           €{self.amount_net:,.2f}"),
            Static(f"  VAT ({self.vat_rate:.0f}%):      €{vat_amount:,.2f}"),
            Static(f"  Gross:         €{gross:,.2f}"),
            Static(""),
            Static(f"  Installments:  {self.installments} (first due {first_due_str})"),
        ]

        # Add recurrence summary
        if self.recurrence_enabled:
            widgets.append(Static(""))
            widgets.append(Static("  ─── Recurrence ───"))
            widgets.append(Static(f"  Repeat every:  {self.recurrence_every_months} month(s)"))
            widgets.append(Static(f"  Occurrences:   {self.recurrence_count}"))

            # Show total expenses created and total cost
            total_cost = gross * self.recurrence_count
            widgets.append(Static(""))
            widgets.append(Static(f"  Total expenses to create: {self.recurrence_count}"))
            widgets.append(Static(f"  Total cost: €{total_cost:,.2f}"))
        else:
            widgets.append(Static(""))
            widgets.append(Static("  Recurrence:    Disabled (single expense)"))

        return widgets

    def _compose_step_5(self) -> ComposeResult:
        """Compose step 5: Review (for initial compose only)."""
        for widget in self._build_step_5():
            yield widget

    def watch_current_step(self, step: int) -> None:
        """Update UI when step changes."""
        try:
            # Update tab styling
            for i in range(1, self.TOTAL_STEPS + 1):
                tab = self.query_one(f"#tab-{i}", Static)
                tab.remove_class("wizard-tab-active")
                tab.remove_class("wizard-tab-completed")
                if i < step:
                    tab.add_class("wizard-tab-completed")
                elif i == step:
                    tab.add_class("wizard-tab-active")
        except Exception as e:
            self.app.notify(f"Tab error: {e}", severity="error")

        # Update content asynchronously (use same group as _rebuild_recurrence_step to prevent race conditions)
        self.run_worker(self._update_step_content_async(step), exclusive=True, group="wizard-content")

        # Update button
        next_btn = self.query_one("#next-btn", Button)
        if step == self.TOTAL_STEPS:
            next_btn.label = "✓ Create"
            next_btn.variant = "success"
        else:
            next_btn.label = "Next →"
            next_btn.variant = "primary"

        # Add back button for steps > 1
        buttons = self.query_one("#wizard-buttons", Horizontal)
        try:
            back_btn = self.query_one("#back-btn", Button)
            if step == 1:
                back_btn.remove()
        except Exception:
            if step > 1:
                back_btn = Button("← Back", variant="default", id="back-btn")
                buttons.mount(back_btn, before=self.query_one("#cancel-btn"))

    async def _update_step_content_async(self, step: int) -> None:
        """Update the wizard content for the given step (async version)."""
        try:
            content = self.query_one("#wizard-content", VerticalScroll)
            await content.remove_children()

            # Build widgets for the step
            widgets = []
            if step == 1:
                widgets = self._build_step_1()
            elif step == 2:
                widgets = self._build_step_2()
            elif step == 3:
                widgets = self._build_step_3()
            elif step == 4:
                widgets = self._build_step_4()
            elif step == 5:
                widgets = self._build_step_5()

            await content.mount_all(widgets)
            self._focus_first_input()
        except Exception as e:
            self.app.notify(f"Content error: {e}", severity="error")

    def _save_current_step_data(self) -> bool:
        """Save data from current step. Returns True if valid."""
        try:
            if self.current_step == 1:
                self.supplier = self.query_one("#supplier-input", Input).value.strip()
                self.description = self.query_one("#description-input", Input).value.strip()
                self.category = self.query_one("#category-input", Input).value.strip()
                self.expense_date = self.query_one("#date-input", Input).value.strip()

                if not self.supplier:
                    self._show_error("Supplier is required")
                    return False

                # Validate date
                try:
                    date.fromisoformat(self.expense_date)
                except ValueError:
                    self._show_error("Invalid date format. Use YYYY-MM-DD.")
                    return False

            elif self.current_step == 2:
                amount_str = self.query_one("#amount-input", Input).value.strip()
                vat_select = self.query_one("#vat-select", Select)

                try:
                    self.amount_net = float(amount_str)
                    if self.amount_net <= 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    self._show_error("Net amount must be a positive number")
                    return False

                self.vat_rate = float(vat_select.value)

            elif self.current_step == 3:
                installments_str = self.query_one("#installments-input", Input).value.strip()
                self.first_due = self.query_one("#first-due-input", Input).value.strip()

                try:
                    self.installments = int(installments_str)
                    if self.installments < 1 or self.installments > 120:
                        raise ValueError()
                except (ValueError, TypeError):
                    self._show_error("Installments must be between 1 and 120")
                    return False

                if self.first_due:
                    try:
                        date.fromisoformat(self.first_due)
                    except ValueError:
                        self._show_error("Invalid first due date format. Use YYYY-MM-DD.")
                        return False

            elif self.current_step == 4:
                enabled_select = self.query_one("#recurrence-enabled-select", Select)
                self.recurrence_enabled = enabled_select.value == "yes"

                if self.recurrence_enabled:
                    every_select = self.query_one("#recurrence-every-select", Select)
                    count_input = self.query_one("#recurrence-count-input", Input)

                    self.recurrence_every_months = int(every_select.value)

                    try:
                        self.recurrence_count = int(count_input.value.strip())
                        if self.recurrence_count < 2 or self.recurrence_count > 120:
                            raise ValueError()
                    except (ValueError, TypeError):
                        self._show_error("Occurrences must be between 2 and 120")
                        return False

            return True
        except Exception as e:
            self._show_error(str(e))
            return False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "next-btn":
            self._handle_next()
        elif event.button.id == "back-btn":
            self._handle_back()
        elif event.button.id == "cancel-btn":
            self.action_cancel()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Update calculated values when inputs change."""
        if self.current_step == 2 and event.input.id == "amount-input":
            try:
                amount = float(event.value)
                vat_rate = float(self.query_one("#vat-select", Select).value)
                vat_amount = amount * vat_rate / 100
                gross = amount + vat_amount

                self.query_one("#calc-vat", Static).update(f"  VAT Amount: €{vat_amount:,.2f}")
                self.query_one("#calc-gross", Static).update(f"  Gross Total: €{gross:,.2f}")
            except (ValueError, TypeError):
                pass

        # Update installment preview in step 3
        if self.current_step == 3 and event.input.id in ("installments-input", "first-due-input"):
            self._update_installment_preview()

        # Update recurrence preview in step 4
        if self.current_step == 4 and event.input.id == "recurrence-count-input":
            self._update_recurrence_preview()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Update calculated values when Select changes."""
        if self.current_step == 2 and event.select.id == "vat-select":
            try:
                amount = float(self.query_one("#amount-input", Input).value)
                vat_rate = float(event.value)
                vat_amount = amount * vat_rate / 100
                gross = amount + vat_amount

                self.query_one("#calc-vat", Static).update(f"  VAT Amount: €{vat_amount:,.2f}")
                self.query_one("#calc-gross", Static).update(f"  Gross Total: €{gross:,.2f}")
            except (ValueError, TypeError):
                pass

        # Handle recurrence toggle
        if self.current_step == 4 and event.select.id == "recurrence-enabled-select":
            new_enabled = event.value == "yes"
            # IMPORTANT: Only rebuild if value actually changed to prevent infinite loop
            # (Select.Changed can fire on mount/focus, not just user interaction)
            if new_enabled != self.recurrence_enabled:
                self.recurrence_enabled = new_enabled
                self.set_timer(0.05, self._rebuild_recurrence_step)

        # Handle recurrence frequency change
        if self.current_step == 4 and event.select.id == "recurrence-every-select":
            self._update_recurrence_preview()

    def _handle_next(self) -> None:
        """Handle next button."""
        self._hide_error()

        if not self._save_current_step_data():
            return

        if self.current_step < self.TOTAL_STEPS:
            self.current_step += 1
        else:
            # Create expense(s)
            self._create_expense()

    def _handle_back(self) -> None:
        """Handle back button."""
        self._hide_error()
        self._save_current_step_data()  # Save but don't validate

        if self.current_step > 1:
            self.current_step -= 1

    def _create_expense(self) -> None:
        """Create the expense via API."""
        self._show_processing()
        self.run_worker(self._do_create_expense, exclusive=True, thread=True)

    def _do_create_expense(self) -> None:
        """Actually create the expense(s) (runs in thread)."""
        try:
            from dateutil.relativedelta import relativedelta

            client = FICClient()

            # Calculate amounts
            vat_amount = round(self.amount_net * self.vat_rate / 100, 2)
            gross = self.amount_net + vat_amount

            # Determine first due date
            if self.first_due:
                first_due_date = date.fromisoformat(self.first_due)
            else:
                from ...utils import end_of_month, add_months
                next_month = add_months(date.today(), 1)
                first_due_date = end_of_month(next_month.year, next_month.month)

            # Base expense date
            base_expense_date = date.fromisoformat(self.expense_date)

            # Determine how many expenses to create
            if self.recurrence_enabled:
                occurrences = self.recurrence_count
            else:
                occurrences = 1

            # Create expense(s)
            for i in range(occurrences):
                # Calculate date offset for this occurrence
                month_offset = i * self.recurrence_every_months if self.recurrence_enabled else 0

                # Expense date for this occurrence
                occurrence_expense_date = base_expense_date + relativedelta(months=month_offset)

                # Due date for this occurrence's first payment
                occurrence_due_date = first_due_date + relativedelta(months=month_offset)

                # Create payment installments for this expense
                payments = create_payment_installments(
                    total_amount=gross,
                    num_installments=self.installments,
                    start_date=occurrence_due_date,
                )

                # Create the expense
                client.create_expense(
                    supplier_name=self.supplier,
                    description=self.description or None,
                    category=self.category or None,
                    amount_net=self.amount_net,
                    amount_vat=vat_amount,
                    expense_date=occurrence_expense_date,
                    payments=payments,
                )

                # Update processing message to show progress
                if occurrences > 1:
                    self.app.call_from_thread(
                        self._update_processing,
                        f"Creating expense {i + 1} of {occurrences}...",
                    )

            # Update quota display
            if client.last_quota:
                self.app.update_quota(client.last_quota)

            self.app.call_from_thread(self._create_success, occurrences)
        except Exception as e:
            self.app.call_from_thread(self._show_error, str(e))
            self.app.call_from_thread(self._hide_processing)

    def _create_success(self, count: int = 1) -> None:
        """Handle successful creation."""
        if count > 1:
            self.app.notify(f"Created {count} recurring expenses")
        self.dismiss(True)

    def _update_processing(self, message: str) -> None:
        """Update the processing message."""
        try:
            processing = self.query_one("#processing", Static)
            processing.update(message)
        except Exception:
            pass

    def _show_error(self, message: str) -> None:
        """Show error message."""
        error = self.query_one("#error-message", Static)
        error.update(f"Error: {message}")
        error.add_class("visible")

    def _hide_error(self) -> None:
        """Hide error message."""
        self.query_one("#error-message", Static).remove_class("visible")

    def _show_processing(self) -> None:
        """Show processing indicator."""
        self.query_one("#processing", Static).add_class("visible")
        self.query_one("#next-btn", Button).disabled = True

    def _hide_processing(self) -> None:
        """Hide processing indicator."""
        self.query_one("#processing", Static).remove_class("visible")
        self.query_one("#next-btn", Button).disabled = False

    def action_cancel(self) -> None:
        """Cancel and close wizard."""
        self.dismiss(False)
