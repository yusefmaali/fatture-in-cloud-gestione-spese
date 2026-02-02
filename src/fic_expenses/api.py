"""Thin wrapper around Fatture in Cloud SDK."""

import os
from dataclasses import dataclass
from datetime import date

from dotenv import load_dotenv
import fattureincloud_python_sdk
from fattureincloud_python_sdk.api import ReceivedDocumentsApi, InfoApi
from fattureincloud_python_sdk.models import (
    CreateReceivedDocumentRequest,
    ModifyReceivedDocumentRequest,
    ReceivedDocument,
    ReceivedDocumentType,
    Entity,
    ReceivedDocumentPaymentsListItem,
    PaymentAccount,
)


@dataclass
class QuotaInfo:
    """API quota information from response headers."""

    hourly_remaining: int
    hourly_limit: int
    monthly_remaining: int
    monthly_limit: int

    @classmethod
    def from_headers(cls, headers: dict) -> "QuotaInfo":
        """Create QuotaInfo from HTTP response headers.

        FIC API uses PascalCase headers like 'RateLimit-HourlyRemaining'.
        We normalize to lowercase for case-insensitive lookup.
        """
        # Normalize headers to lowercase for case-insensitive lookup
        lower_headers = {k.lower(): v for k, v in headers.items()}

        # Use remaining values, defaulting to limit (not 0) if not found
        hourly_limit = int(lower_headers.get("ratelimit-hourlylimit", 1000))
        monthly_limit = int(lower_headers.get("ratelimit-monthlylimit", 40000))

        return cls(
            hourly_remaining=int(lower_headers.get("ratelimit-hourlyremaining", hourly_limit)),
            hourly_limit=hourly_limit,
            monthly_remaining=int(lower_headers.get("ratelimit-monthlyremaining", monthly_limit)),
            monthly_limit=monthly_limit,
        )

    @property
    def hourly_used(self) -> int:
        """Number of hourly requests used."""
        return self.hourly_limit - self.hourly_remaining

    @property
    def monthly_used(self) -> int:
        """Number of monthly requests used."""
        return self.monthly_limit - self.monthly_remaining

    @property
    def hourly_percent(self) -> float:
        """Percentage of hourly quota used."""
        return self.hourly_used / self.hourly_limit if self.hourly_limit else 0

    @property
    def monthly_percent(self) -> float:
        """Percentage of monthly quota used."""
        return self.monthly_used / self.monthly_limit if self.monthly_limit else 0


class FICClient:
    """Client for Fatture in Cloud API."""

    # Class-level quota tracking (shared across instances)
    last_quota: QuotaInfo | None = None

    def __init__(self):
        """Initialize client from environment variables."""
        load_dotenv()

        self.access_token = os.getenv("FIC_ACCESS_TOKEN")
        self.company_id = os.getenv("FIC_COMPANY_ID")

        if not self.access_token or not self.company_id:
            raise ValueError(
                "Missing credentials! "
                "Set FIC_ACCESS_TOKEN and FIC_COMPANY_ID in .env file"
            )

        self.company_id = int(self.company_id)

        # Configure SDK
        self.config = fattureincloud_python_sdk.Configuration()
        self.config.access_token = self.access_token

    def _get_api(self) -> ReceivedDocumentsApi:
        """Get ReceivedDocuments API client instance."""
        api_client = fattureincloud_python_sdk.ApiClient(self.config)
        return ReceivedDocumentsApi(api_client)

    def _get_info_api(self) -> InfoApi:
        """Get Info API client instance."""
        api_client = fattureincloud_python_sdk.ApiClient(self.config)
        return InfoApi(api_client)

    def _update_quota(self, headers: dict) -> None:
        """Update quota info from response headers."""
        if headers:
            FICClient.last_quota = QuotaInfo.from_headers(headers)

    # API per_page constraints (enforced by SDK/API)
    MIN_PER_PAGE = 5
    MAX_PER_PAGE = 100

    def list_expenses(
        self,
        *,
        q: str | None = None,
        sort: str | None = None,
        limit: int | None = 50,
        fetch_all: bool = False,
    ) -> list[ReceivedDocument]:
        """
        List expenses (received documents of type 'expense').

        Args:
            q: Filter query (e.g., "entity.name = 'Amazon'")
            sort: Sort field (e.g., "-date" for descending)
            limit: Max number of expenses to fetch. None or fetch_all=True fetches all.
            fetch_all: If True, fetch all pages (equivalent to limit=None)

        Returns:
            List of expense documents
        """
        api = self._get_api()

        # fetch_all=True is equivalent to limit=None
        if fetch_all:
            limit = None

        # Use max per_page to minimize API calls
        per_page = self.MAX_PER_PAGE

        # Single page fetch optimization: if limit <= MAX_PER_PAGE, just fetch one page
        if limit is not None and limit <= self.MAX_PER_PAGE:
            per_page = max(self.MIN_PER_PAGE, limit)
            response = api.list_received_documents_with_http_info(
                company_id=self.company_id,
                type="expense",
                q=q,
                sort=sort,
                page=1,
                per_page=per_page,
            )
            self._update_quota(response.headers)
            return response.data.data or []

        # Multi-page fetch: either fetch_all or limit > MAX_PER_PAGE
        all_expenses = []
        page = 1
        while True:
            response = api.list_received_documents_with_http_info(
                company_id=self.company_id,
                type="expense",
                q=q,
                sort=sort,
                page=page,
                per_page=per_page,
            )
            self._update_quota(response.headers)
            expenses = response.data.data or []
            if not expenses:
                break
            all_expenses.extend(expenses)

            # If we have a limit, stop when we've collected enough
            if limit is not None and len(all_expenses) >= limit:
                return all_expenses[:limit]

            page += 1

        return all_expenses

    def get_expense(self, document_id: int) -> ReceivedDocument:
        """Get a single expense by ID."""
        api = self._get_api()
        response = api.get_received_document_with_http_info(
            company_id=self.company_id,
            document_id=document_id,
        )
        self._update_quota(response.headers)
        return response.data.data

    def list_payment_accounts(self) -> list[PaymentAccount]:
        """
        List available payment accounts.

        Returns:
            List of payment accounts (bank accounts, cash, cards, etc.)
        """
        api = self._get_info_api()
        response = api.list_payment_accounts_with_http_info(company_id=self.company_id)
        self._update_quota(response.headers)
        return response.data.data or []

    def create_expense(
        self,
        *,
        supplier_name: str,
        description: str | None = None,
        category: str | None = None,
        amount_net: float,
        amount_vat: float,
        expense_date: date | None = None,
        payments: list[ReceivedDocumentPaymentsListItem] | None = None,
        tax_deductibility: float = 100.0,
        vat_deductibility: float = 100.0,
    ) -> ReceivedDocument:
        """
        Create a new expense.

        Args:
            supplier_name: Name of the supplier/vendor
            description: Expense description
            category: Expense category
            amount_net: Net amount (before VAT)
            amount_vat: VAT amount
            expense_date: Date of the expense (defaults to today)
            payments: List of payment installments
            tax_deductibility: Tax deductibility percentage (0-100)
            vat_deductibility: VAT deductibility percentage (0-100)

        Returns:
            Created expense document
        """
        api = self._get_api()

        expense = ReceivedDocument(
            type=ReceivedDocumentType.EXPENSE,
            entity=Entity(name=supplier_name),
            var_date=expense_date or date.today(),
            description=description,
            category=category,
            amount_net=amount_net,
            amount_vat=amount_vat,
            tax_deductibility=tax_deductibility,
            vat_deductibility=vat_deductibility,
            payments_list=payments,
        )

        request = CreateReceivedDocumentRequest(data=expense)
        response = api.create_received_document_with_http_info(
            company_id=self.company_id,
            create_received_document_request=request,
        )
        self._update_quota(response.headers)
        return response.data.data

    def update_expense(
        self,
        document_id: int,
        expense: ReceivedDocument,
    ) -> ReceivedDocument:
        """
        Update an existing expense.

        Args:
            document_id: ID of the expense to update
            expense: Updated expense document

        Returns:
            Updated expense document
        """
        api = self._get_api()

        request = ModifyReceivedDocumentRequest(data=expense)
        response = api.modify_received_document_with_http_info(
            company_id=self.company_id,
            document_id=document_id,
            modify_received_document_request=request,
        )
        self._update_quota(response.headers)
        return response.data.data

    def mark_expense_paid(
        self,
        document_id: int,
        payment_account_id: int,
        paid_date: date | None = None,
        installment_index: int | None = None,
    ) -> ReceivedDocument:
        """
        Mark expense (or specific installment) as paid.

        NOTE: The FIC API requires a payment_account when marking payments as paid.
        Without it, the API silently ignores the payment update.

        Args:
            document_id: ID of the expense
            payment_account_id: ID of the payment account (bank, cash, card, etc.)
            paid_date: Date of payment. If None, each installment uses its own due_date
                      (falls back to expense date if due_date is also missing)
            installment_index: If provided, only mark this installment as paid (1-indexed)

        Returns:
            Updated expense document
        """
        payment_account = PaymentAccount(id=payment_account_id)

        # Get current expense
        expense = self.get_expense(document_id)

        if not expense.payments_list:
            raise ValueError(f"Expense {document_id} has no payment schedule")

        # Update payments
        for i, payment in enumerate(expense.payments_list):
            if installment_index is not None:
                # Only update specific installment (1-indexed)
                if i + 1 == installment_index:
                    payment.status = "paid"
                    # Use provided date, or installment's due_date, or expense date
                    payment.paid_date = paid_date or payment.due_date or expense.var_date
                    payment.payment_account = payment_account
            else:
                # Update all unpaid installments
                if payment.status != "paid":
                    payment.status = "paid"
                    # Each installment uses its own due_date if no explicit date provided
                    payment.paid_date = paid_date or payment.due_date or expense.var_date
                    payment.payment_account = payment_account

        return self.update_expense(document_id, expense)


def create_payment_installments(
    total_amount: float,
    num_installments: int,
    start_date: date,
) -> list[ReceivedDocumentPaymentsListItem]:
    """
    Create payment installments for an expense.

    Args:
        total_amount: Total gross amount
        num_installments: Number of installments
        start_date: Date to calculate first due date from

    Returns:
        List of payment installment items
    """
    from .utils import generate_installment_dates, split_amount

    dates = generate_installment_dates(start_date, num_installments)
    amounts = split_amount(total_amount, num_installments)

    return [
        ReceivedDocumentPaymentsListItem(
            amount=amount,
            due_date=due_date,
            status="not_paid",
        )
        for amount, due_date in zip(amounts, dates)
    ]
