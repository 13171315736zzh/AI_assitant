"""工时/工包查询接口（演示用，可替换为真实 HR/OA API）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta

from src.agent.workpackage_workflow import (
    DEFAULT_HOURS_PER_DAY,
    _WEEKDAY_NAMES,
    compute_this_week_range,
    format_date_range,
)


@dataclass
class TimesheetConflict:
    day_label: str
    day_date: str
    period: str
    existing_project: str
    person_days: float
    hours: float = 4.0

    def to_public_dict(self) -> dict:
        return asdict(self)


@dataclass
class TimesheetFillPlan:
    project: str
    period_label: str
    requested_days: float
    fillable_days: float
    entries: list[dict]
    conflicts: list[TimesheetConflict]

    def to_public_dict(self) -> dict:
        return {
            "project": self.project,
            "period_label": self.period_label,
            "requested_days": self.requested_days,
            "fillable_days": self.fillable_days,
            "entries": self.entries,
            "conflicts": [c.to_public_dict() for c in self.conflicts],
        }


def _weekday_label(day: date) -> str:
    return _WEEKDAY_NAMES[day.weekday()]


def _iter_weekdays(start: date, end: date) -> list[tuple[str, str]]:
    days: list[tuple[str, str]] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append((_weekday_label(current), current.isoformat()))
        current += timedelta(days=1)
    return days


async def query_weekly_fill_plan(
    project: str,
    *,
    fill_days: float = 5.0,
    period_hint: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    hours_per_day: float = DEFAULT_HOURS_PER_DAY,
) -> TimesheetFillPlan:
    """生成本周（周一至今天）填报计划，演示周三下午已有宁煤项目占用。"""
    if date_start and date_end:
        week_start = date.fromisoformat(date_start)
        week_end = date.fromisoformat(date_end)
    else:
        week_start, week_end, _ = compute_this_week_range()

    period_label = (
        format_date_range(week_start, week_end)
        if period_hint == "本周" or date_start
        else (period_hint or "本周")
    )
    days = _iter_weekdays(week_start, week_end)

    conflicts: list[TimesheetConflict] = []
    wed_in_range = any(label == "周三" for label, _ in days)
    if wed_in_range:
        wed_date = next(d for label, d in days if label == "周三")
        conflicts.append(
            TimesheetConflict(
                day_label="周三",
                day_date=wed_date,
                period="下午",
                existing_project="宁煤项目",
                person_days=0.5,
                hours=hours_per_day / 2,
            )
        )

    entries: list[dict] = []
    for label, day_date in days:
        if label == "周三" and wed_in_range:
            entries.append(
                {
                    "day_label": label,
                    "day_date": day_date,
                    "period": "上午",
                    "project": project,
                    "person_days": 0.5,
                    "hours": hours_per_day / 2,
                    "selected": True,
                }
            )
            continue
        entries.append(
            {
                "day_label": label,
                "day_date": day_date,
                "period": "全天",
                "project": project,
                "person_days": 1.0,
                "hours": hours_per_day,
                "selected": True,
            }
        )

    fillable = max(0.0, fill_days - (0.5 if wed_in_range else 0.0))

    return TimesheetFillPlan(
        project=project,
        period_label=period_label,
        requested_days=fill_days,
        fillable_days=fillable,
        entries=entries,
        conflicts=conflicts,
    )
