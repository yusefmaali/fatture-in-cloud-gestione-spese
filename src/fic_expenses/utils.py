"""Date and calculation utilities."""

import calendar
from datetime import date
from dateutil.relativedelta import relativedelta


def end_of_month(year: int, month: int) -> date:
    """Return the last day of the given month."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def add_months(d: date, months: int) -> date:
    """Add N months to a date, preserving end-of-month behavior."""
    return d + relativedelta(months=months)


def generate_installment_dates(
    start_date: date,
    num_installments: int,
) -> list[date]:
    """
    Generate due dates for installments.

    First installment is at end of start_date's month,
    subsequent installments at end of consecutive months.
    """
    dates = []
    year = start_date.year
    month = start_date.month

    for _ in range(num_installments):
        dates.append(end_of_month(year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1

    return dates


def split_amount(total: float, parts: int) -> list[float]:
    """
    Split a total amount into N equal parts, handling rounding.

    Any remainder from rounding is added to the last part.
    """
    if parts <= 0:
        return []

    base = round(total / parts, 2)
    amounts = [base] * parts

    # Fix rounding error by adjusting last installment
    actual_sum = sum(amounts)
    diff = round(total - actual_sum, 2)
    if diff != 0:
        amounts[-1] = round(amounts[-1] + diff, 2)

    return amounts
