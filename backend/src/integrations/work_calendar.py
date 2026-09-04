"""中国法定节假日与调休工作日查询（基于 chinese-calendar，可替换为 OA/HR 排班接口）。"""

from __future__ import annotations

from datetime import date, timedelta

try:
    import chinese_calendar as cc

    _HAS_CHINESE_CALENDAR = True
except ImportError:  # pragma: no cover
    cc = None  # type: ignore[assignment]
    _HAS_CHINESE_CALENDAR = False


def is_workday(day: date) -> bool:
    if _HAS_CHINESE_CALENDAR:
        return bool(cc.is_workday(day))
    return day.weekday() < 5


_HOLIDAY_NAME_ZH: dict[str, str] = {
    "new year's day": "元旦",
    "spring festival": "春节",
    "tomb-sweeping day": "清明节",
    "labour day": "劳动节",
    "dragon boat festival": "端午节",
    "mid-autumn festival": "中秋节",
    "national day": "国庆节",
}


def localize_holiday_name(name: str) -> str:
    """将 chinese-calendar 返回的英文节日名转为中文。"""
    key = name.strip().lower()
    if key in _HOLIDAY_NAME_ZH:
        return _HOLIDAY_NAME_ZH[key]
    if any("\u4e00" <= ch <= "\u9fff" for ch in name):
        return name.strip()
    return name.strip()


def holiday_label(day: date) -> str | None:
    if not _HAS_CHINESE_CALENDAR:
        return None
    try:
        on_holiday, name = cc.get_holiday_detail(day)
    except Exception:  # noqa: BLE001
        return None
    if on_holiday and name:
        return localize_holiday_name(name)
    return None


def iter_dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def list_workdays(start: date, end: date) -> list[date]:
    return [day for day in iter_dates(start, end) if is_workday(day)]


def list_rest_days(start: date, end: date) -> list[dict]:
    """返回区间内非工作日（含周末与法定节假日）。"""
    rests: list[dict] = []
    for day in iter_dates(start, end):
        if is_workday(day):
            continue
        label = holiday_label(day) or ("周末" if day.weekday() >= 5 else "休息")
        rests.append({"day_date": day.isoformat(), "reason": label})
    return rests


def count_workdays(start: date, end: date) -> int:
    return len(list_workdays(start, end))


def compute_month_week_range(
    year: int,
    month: int,
    week_index: int,
) -> tuple[date, date] | None:
    """按月内自然周（周一到周日）计算：第1周=含该月1日的那一周，第2周=下一整周，以此类推。"""
    import calendar

    if week_index < 1:
        return None

    first_of_month = date(year, month, 1)
    _, days_in_month = calendar.monthrange(year, month)
    last_of_month = date(year, month, days_in_month)

    # 含当月 1 日的那一周的周一
    first_week_monday = first_of_month - timedelta(days=first_of_month.weekday())
    week_start = first_week_monday + timedelta(weeks=week_index - 1)
    if week_start > last_of_month:
        return None
    week_end = week_start + timedelta(days=6)
    return week_start, week_end
