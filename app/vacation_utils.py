from datetime import date, timedelta
from decimal import Decimal, InvalidOperation


ZERO_DAY = Decimal("0")
HALF_DAY = Decimal("0.5")
FULL_DAY = Decimal("1")


def _holiday_deduction(value):
    if value is True:
        return FULL_DAY
    if value in (False, None):
        return ZERO_DAY

    try:
        deduction = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return FULL_DAY

    return max(ZERO_DAY, min(FULL_DAY, deduction))


def holiday_deduction_map(holidays):
    if not holidays:
        return {}

    if hasattr(holidays, "items"):
        entries = holidays.items()
    else:
        entries = []
        for holiday in holidays:
            if isinstance(holiday, tuple) and len(holiday) == 2:
                entries.append(holiday)
            else:
                entries.append((holiday, FULL_DAY))

    deductions = {}
    for holiday_date, deduction in entries:
        if holiday_date is None:
            continue
        current = deductions.get(holiday_date, ZERO_DAY)
        deductions[holiday_date] = min(FULL_DAY, current + _holiday_deduction(deduction))
    return deductions


def count_vacation_days(start_date, end_date, holidays):
    return vacation_day_stats(start_date, end_date, holidays)["vacation_days"]


def vacation_day_stats(start_date, end_date, holidays):
    if end_date < start_date:
        raise ValueError("end-before-start")

    holiday_deductions = holiday_deduction_map(holidays)
    total_days = (end_date - start_date).days + 1
    weekend_days = 0
    holiday_weekdays = 0
    holiday_deduction_days = ZERO_DAY
    vacation_days = ZERO_DAY

    for offset in range(total_days):
        current = start_date + timedelta(days=offset)
        if current.weekday() >= 5:
            weekend_days += 1
            continue

        deduction = holiday_deductions.get(current, ZERO_DAY)
        if deduction:
            holiday_weekdays += 1
            holiday_deduction_days += deduction
            vacation_days += max(ZERO_DAY, FULL_DAY - deduction)
        else:
            vacation_days += FULL_DAY

    return {
        "total_days": total_days,
        "weekend_days": weekend_days,
        "holiday_weekdays": holiday_weekdays,
        "holiday_deduction_days": holiday_deduction_days,
        "vacation_days": vacation_days,
    }


def clip_range_to_year(start_date, end_date, year):
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    clipped_start = max(start_date, year_start)
    clipped_end = min(end_date, year_end)

    if clipped_end < clipped_start:
        return None

    return clipped_start, clipped_end


def dates_between(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)
