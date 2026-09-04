"""工时/工包查询接口（演示用，可替换为真实 HR/OA API）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from src.agent.workpackage_workflow import (
    DEFAULT_HOURS_PER_DAY,
    LeaveSlot,
    _WEEKDAY_NAMES,
    _hours_for_workday,
    compute_this_week_range,
    format_date_range,
)
from src.integrations.work_calendar import holiday_label, is_workday, list_rest_days, list_workdays


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
    skipped_days: list[dict]
    total_hours: float

    def to_public_dict(self) -> dict:
        return {
            "project": self.project,
            "period_label": self.period_label,
            "requested_days": self.requested_days,
            "fillable_days": self.fillable_days,
            "entries": self.entries,
            "conflicts": [c.to_public_dict() for c in self.conflicts],
            "skipped_days": self.skipped_days,
            "total_hours": self.total_hours,
        }


def _weekday_label(day: date) -> str:
    return _WEEKDAY_NAMES[day.weekday()]


def _build_skipped_days(week_start: date, week_end: date) -> list[dict]:
    skipped: list[dict] = []
    for item in list_rest_days(week_start, week_end):
        day = date.fromisoformat(item["day_date"])
        skipped.append(
            {
                **item,
                "day_label": _weekday_label(day),
            }
        )
    return skipped


async def query_weekly_fill_plan(
    project: str,
    *,
    fill_days: float = 5.0,
    period_hint: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    hours_per_day: float = DEFAULT_HOURS_PER_DAY,
    leave_slots: list[LeaveSlot] | None = None,
    full_week: bool = False,
) -> TimesheetFillPlan:
    """按当年法定工作日历与用户请假生成填报计划。"""
    leave_slots = leave_slots or []

    if date_start and date_end:
        week_start = date.fromisoformat(date_start)
        week_end = date.fromisoformat(date_end)
    else:
        week_start, week_end, _ = compute_this_week_range(full_week=full_week)

    period_label = (
        format_date_range(week_start, week_end)
        if period_hint == "本周" or date_start
        else (period_hint or "本周")
    )

    skipped_days = _build_skipped_days(week_start, week_end)
    work_dates = list_workdays(week_start, week_end)

    entries: list[dict] = []
    for day in work_dates:
        weekday = day.weekday()
        hours_info = _hours_for_workday(weekday, leave_slots, hours_per_day)
        if hours_info is None:
            label = _weekday_label(day)
            skipped_days.append(
                {
                    "day_date": day.isoformat(),
                    "day_label": label,
                    "reason": "请假",
                }
            )
            continue

        hours, period = hours_info
        person_days = round(hours / hours_per_day, 2) if hours_per_day else 0.0
        entries.append(
            {
                "day_label": _weekday_label(day),
                "day_date": day.isoformat(),
                "period": period,
                "project": project,
                "person_days": person_days,
                "hours": hours,
                "selected": True,
            }
        )

    total_hours = sum(entry["hours"] for entry in entries)
    requested_days = len(entries)
    fillable = total_hours / hours_per_day if hours_per_day else float(requested_days)

    _ = fill_days  # 实际以工作日历与请假结果为准

    return TimesheetFillPlan(
        project=project,
        period_label=period_label,
        requested_days=float(requested_days),
        fillable_days=fillable,
        entries=entries,
        conflicts=[],
        skipped_days=skipped_days,
        total_hours=total_hours,
    )
