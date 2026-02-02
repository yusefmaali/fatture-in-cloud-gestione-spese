#!/usr/bin/env python3
"""
POC: Create a test expense in Fatture in Cloud

This script validates that we can:
1. Authenticate with the API
2. Create a received document (expense) with status "not_paid"
3. Split payment into multiple installments (pagamento rateale)
"""

import calendar
import os
import sys
from datetime import date
from dotenv import load_dotenv

import fattureincloud_python_sdk
from fattureincloud_python_sdk.models import (
    CreateReceivedDocumentRequest,
    ReceivedDocument,
    ReceivedDocumentType,
    Entity,
    ReceivedDocumentPaymentsListItem,
)
from fattureincloud_python_sdk.exceptions import ApiException


def end_of_month(year: int, month: int) -> date:
    """Return the last day of the given month."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def generate_installments(
    total_amount: float,
    num_installments: int,
    start_date: date
) -> list[ReceivedDocumentPaymentsListItem]:
    """
    Generate installment payments (pagamento rateale).

    Each installment is due at the end of consecutive months,
    starting from the month after start_date.
    """
    installments = []
    base_amount = round(total_amount / num_installments, 2)

    # Handle rounding: put any remainder in the last installment
    remainder = round(total_amount - (base_amount * num_installments), 2)

    year = start_date.year
    month = start_date.month

    for i in range(num_installments):
        # Move to next month
        month += 1
        if month > 12:
            month = 1
            year += 1

        due_date = end_of_month(year, month)

        # Add remainder to last installment
        amount = base_amount if i < num_installments - 1 else base_amount + remainder

        installments.append(
            ReceivedDocumentPaymentsListItem(
                amount=amount,
                due_date=due_date,
                status="not_paid"
            )
        )

    return installments


def main():
    # Load credentials from .env
    load_dotenv()

    access_token = os.getenv("FIC_ACCESS_TOKEN")
    company_id = os.getenv("FIC_COMPANY_ID")

    if not access_token or not company_id:
        print("ERROR: Missing credentials!")
        print("Copy .env.example to .env and fill in your credentials")
        sys.exit(1)

    company_id = int(company_id)

    # Configure API client
    configuration = fattureincloud_python_sdk.Configuration()
    configuration.access_token = access_token

    with fattureincloud_python_sdk.ApiClient(configuration) as api_client:
        api = fattureincloud_python_sdk.ReceivedDocumentsApi(api_client)

        # Test expense with installment payments (pagamento rateale)
        amount_net = 500.00
        amount_vat = 110.00  # 22% IVA
        total_gross = amount_net + amount_vat
        num_installments = 5

        # Generate 5 monthly installments, each due at end of month
        payments = generate_installments(
            total_amount=total_gross,
            num_installments=num_installments,
            start_date=date.today()
        )

        expense = ReceivedDocument(
            type=ReceivedDocumentType.EXPENSE,
            entity=Entity(name="TEST - Dell Technologies"),
            var_date=date.today(),
            description="[TEST] Laptop 5 rate - DELETE ME",
            category="Hardware",
            amount_net=amount_net,
            amount_vat=amount_vat,
            tax_deductibility=100.0,
            vat_deductibility=100.0,
            payments_list=payments
        )

        try:
            print("Creating test expense...")
            request = CreateReceivedDocumentRequest(data=expense)
            response = api.create_received_document(
                company_id=company_id,
                create_received_document_request=request
            )

            doc = response.data
            print("\n" + "=" * 50)
            print("SUCCESS! Expense created with installments")
            print("=" * 50)
            print(f"  ID:          {doc.id}")
            print(f"  Date:        {doc.var_date}")
            print(f"  Supplier:    {doc.entity.name}")
            print(f"  Description: {doc.description}")
            print(f"  Net:         €{doc.amount_net:.2f}")
            print(f"  VAT:         €{doc.amount_vat:.2f}")
            print(f"  Gross:       €{doc.amount_gross:.2f}")
            print("-" * 50)
            print(f"  Payment schedule ({len(doc.payments_list)} installments):")
            for i, payment in enumerate(doc.payments_list, 1):
                status_icon = "✓" if payment.status == "paid" else "○"
                print(f"    {status_icon} Rata {i}: €{payment.amount:.2f} - due {payment.due_date}")
            print("=" * 50)
            print(f"\nGo check it in Fatture in Cloud!")
            print(f"Remember to DELETE this test expense (ID: {doc.id})")

        except ApiException as e:
            print(f"\nAPI ERROR: {e.status} - {e.reason}")
            print(f"Body: {e.body}")
            sys.exit(1)


if __name__ == "__main__":
    main()
