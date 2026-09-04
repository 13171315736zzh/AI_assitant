"""工时填报周期解析：本周/上周/X月第N周。"""

from __future__ import annotations

import re
from datetime import date

from src.integrations.work_calendar import compute_month_week_range

_CN_DIGIT = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_CN_MONTH = {
    "正": 1,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
    "腊": 12,
    "冬": 12,
}

_MONTH_WEEK_PATTERN = re.compile(
    r"(?:今年|本年)?\s*"
    r"(\d{1,2}|[一二三四五六七八九十]{1,3}|[正二三四五六七八九十冬腊]{1,2})\s*月(?:份)?"
    r"(?:\s*的)?\s*第?\s*([一二三四五六七八九十\d]{1,2})\s*周"
)


def cn_to_int(token: str) -> int | None:
    token = token.strip().replace("第", "")
    if not token:
        return None
    if token.isdigit():
        value = int(token)
        return value if value > 0 else None
    if token in _CN_DIGIT:
        return _CN_DIGIT[token]
    if token == "十":
        return 10
    if token.startswith("十") and len(token) > 1:
        return 10 + (_CN_DIGIT.get(token[1:], 0) or 0)
    if "十" in token:
        left, _, right = token.partition("十")
        tens = _CN_DIGIT.get(left, 1) if left else 1
        ones = _CN_DIGIT.get(right, 0) if right else 0
        return tens * 10 + ones
    return None


def parse_month_token(token: str) -> int | None:
    token = token.strip()
    if token.isdigit():
        month = int(token)
        return month if 1 <= month <= 12 else None
    if token in _CN_MONTH:
        return _CN_MONTH[token]
    value = cn_to_int(token)
    if value and 1 <= value <= 12:
        return value
    return None


def parse_month_week_period(
    text: str,
    today: date | None = None,
) -> tuple[date, date, str] | None:
    """解析「今年二月份第二周」「5月份第2周」等，返回起止日期与标签。"""
    today = today or date.today()
    match = _MONTH_WEEK_PATTERN.search(text)
    if not match:
        return None

    month = parse_month_token(match.group(1))
    week_index = cn_to_int(match.group(2))
    if not month or not week_index:
        return None

    year = today.year
    if re.search(r"去年|上年", text):
        year -= 1
    elif re.search(r"明年|下年", text):
        year += 1

    week_range = compute_month_week_range(year, month, week_index)
    if week_range is None:
        return None
    start, end = week_range
    label = f"{year}年{month}月第{week_index}周"
    return start, end, label


def has_month_week_intent(text: str) -> bool:
    return _MONTH_WEEK_PATTERN.search(text) is not None
