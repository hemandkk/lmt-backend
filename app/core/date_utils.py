from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

# Business calendar for "today" / week / month KPIs (payment dates are local dates)
APP_TZ = ZoneInfo("Asia/Kolkata")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def today() -> date:
    return datetime.now(APP_TZ).date()


def start_of_week(d: Optional[date] = None) -> date:
    current = d or today()
    return current - timedelta(days=current.weekday())


def end_of_week(d: Optional[date] = None) -> date:
    return start_of_week(d) + timedelta(days=6)


def start_of_month(d: Optional[date] = None) -> date:
    current = d or today()
    return current.replace(day=1)


def end_of_month(d: Optional[date] = None) -> date:
    current = d or today()
    if current.month == 12:
        return current.replace(year=current.year + 1, month=1, day=1) - timedelta(
            days=1
        )
    return current.replace(month=current.month + 1, day=1) - timedelta(days=1)


def intersect_date_ranges(
    a_from: Optional[date],
    a_to: Optional[date],
    b_from: Optional[date],
    b_to: Optional[date],
) -> Tuple[Optional[date], Optional[date], bool]:
    """
    Intersect two inclusive date ranges.
    Returns (start, end, empty). empty=True means no overlapping days.
    """
    start = a_from
    end = a_to
    if b_from is not None and (start is None or b_from > start):
        start = b_from
    if b_to is not None and (end is None or b_to < end):
        end = b_to
    if start is not None and end is not None and start > end:
        return None, None, True
    return start, end, False


def resolve_date_range(
    period: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Tuple[Optional[date], Optional[date]]:
    """
    Resolve a named period or explicit custom range.
    period: today | this_week | this_month | total | custom
    """
    if date_from or date_to:
        return date_from, date_to

    if not period or period == "total":
        return None, None

    current = today()
    if period == "today":
        return current, current
    if period == "this_week":
        return start_of_week(current), end_of_week(current)
    if period == "this_month":
        return start_of_month(current), end_of_month(current)
    if period == "custom":
        return date_from, date_to

    return None, None


def datetime_range_bounds(
    date_from: Optional[date],
    date_to: Optional[date],
) -> Tuple[Optional[datetime], Optional[datetime]]:
    start_dt = (
        datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
        if date_from
        else None
    )
    end_dt = (
        datetime.combine(date_to, datetime.max.time()).replace(tzinfo=timezone.utc)
        if date_to
        else None
    )
    return start_dt, end_dt
