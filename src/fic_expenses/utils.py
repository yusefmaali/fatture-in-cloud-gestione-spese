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

    First installment is on start_date, subsequent installments
    are on the same day of consecutive months.

    Example: start_date=2026-02-15 with 3 installments:
        -> [2026-02-15, 2026-03-15, 2026-04-15]

    If the day doesn't exist in a month (e.g., Jan 31 -> Feb),
    relativedelta adjusts to the last valid day (Feb 28/29).
    """
    dates = []
    for i in range(num_installments):
        dates.append(start_date + relativedelta(months=i))
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
