"""Pydantic models for input validation."""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RecurrencePeriod(str, Enum):
    """Recurrence period options."""
    MONTHLY = "monthly"
    BIANNUAL = "biannual"
    YEARLY = "yearly"

    def to_months(self) -> int:
        """Convert to number of months."""
        return {
            RecurrencePeriod.MONTHLY: 1,
            RecurrencePeriod.BIANNUAL: 6,
            RecurrencePeriod.YEARLY: 12,
        }[self]


class ExpenseInput(BaseModel):
    """Input model for creating an expense."""

    supplier: str = Field(..., min_length=1, description="Supplier/vendor name")
    description: Optional[str] = Field(None, description="Expense description")
    category: Optional[str] = Field(None, description="Expense category")
    amount_net: float = Field(..., gt=0, description="Net amount (before VAT)")
    vat_rate: float = Field(22.0, ge=0, le=100, description="VAT rate percentage")
    expense_date: date = Field(default_factory=date.today, description="Expense date")
    installments: int = Field(1, ge=1, le=120, description="Number of payment installments")
    first_due: Optional[date] = Field(None, description="First installment due date")
    recurrence: Optional[RecurrencePeriod] = Field(None, description="Recurrence period")
    occurrences: int = Field(1, ge=1, le=10, description="Number of recurrence occurrences")

    @property
    def amount_vat(self) -> float:
        """Calculate VAT amount."""
        return round(self.amount_net * self.vat_rate / 100, 2)

    @property
    def amount_gross(self) -> float:
        """Calculate gross amount."""
        return round(self.amount_net + self.amount_vat, 2)

    @field_validator("first_due", mode="before")
    @classmethod
    def set_default_first_due(cls, v, info):
        """Set default first due date to end of next month."""
        if v is None:
            from .utils import end_of_month
            today = date.today()
            month = today.month + 1
            year = today.year
            if month > 12:
                month = 1
                year += 1
            return end_of_month(year, month)
        return v
