"""工包/工时填报流程：槽位收集、冲突检测与确认。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

_WORKPACKAGE_INTENT = re.compile(r"工包|工时|填报|人天|人日")
_PROJECT_PATTERN = re.compile(r"([\u4e00-\u9fffA-Za-z0-9·]{2,12}(?:售前|售后|可视化|能源|数据)?项目)")
_THIS_WEEK_PATTERN = re.compile(r"本周")
_WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
DEFAULT_HOURS_PER_DAY = 8.0


@dataclass
class WorkpackagePlan:
    project: str | None = None
    total_person_days: float | None = None
    fill_days: float | None = None
    period_hint: str | None = None
    date_start: str | None = None
    date_end: str | None = None
    hours_per_day: float = DEFAULT_HOURS_PER_DAY
    content: str | None = None
    raw_goal: str = ""
    project_options: list[str] = field(default_factory=list)


def is_workpackage_workflow_intent(text: str) -> bool:
    if not _WORKPACKAGE_INTENT.search(text):
        return False
    if _PROJECT_PATTERN.search(text):
        return True
    if _THIS_WEEK_PATTERN.search(text) and re.search(r"工时|工包", text):
        return True
    return False


def compute_this_week_range(today: date | None = None) -> tuple[date, date, int]:
    """本周一至今天（含）的工作日范围。"""
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    work_days = today.weekday() + 1
    return week_start, today, work_days


def format_date_range(start: date, end: date) -> str:
    return f"{start.isoformat()} ~ {end.isoformat()}"


def normalize_workpackage_plan(plan: WorkpackagePlan) -> WorkpackagePlan:
    combined = plan.raw_goal
    if plan.period_hint == "本周" or (plan.period_hint is None and "本周" in combined):
        plan.period_hint = plan.period_hint or "本周"
        week_start, week_end, work_days = compute_this_week_range()
        plan.date_start = week_start.isoformat()
        plan.date_end = week_end.isoformat()
        if not plan.fill_days:
            plan.fill_days = float(work_days)
    return plan


def _merge_user_text(messages) -> str:
    parts: list[str] = []
    for record in messages:
        if record.role == "user" and record.content.strip():
            parts.append(record.content.strip())
    return "\n".join(parts)


def build_workpackage_plan(messages) -> WorkpackagePlan:
    combined = _merge_user_text(messages)
    plan = WorkpackagePlan(raw_goal=combined[:200])

    proj = _PROJECT_PATTERN.search(combined)
    if proj:
        plan.project = proj.group(1)
    yanbao = re.search(r"[燕雁]宝(?:售前|售后)?项目", combined)
    if yanbao:
        plan.project = yanbao.group(0)

    total_match = re.search(r"(\d+(?:\.\d+)?)\s*个?\s*人[天日]", combined)
    if total_match:
        plan.total_person_days = float(total_match.group(1))

    fill_match = re.search(r"(\d+(?:\.\d+)?)\s*天", combined)
    if fill_match:
        plan.fill_days = float(fill_match.group(1))
    elif re.search(r"本周.*5\s*天|5\s*天.*本周", combined):
        plan.fill_days = 5.0

    if "本周" in combined:
        plan.period_hint = "本周"
    elif "本月" in combined:
        plan.period_hint = "本月"

    hours_match = re.search(r"(\d+(?:\.\d+)?)\s*小时", combined)
    if hours_match:
        plan.hours_per_day = float(hours_match.group(1))

    content_match = re.search(r"(?:内容|工作)[：:]\s*(.{2,40})", combined)
    if content_match:
        plan.content = content_match.group(1).strip()

    return normalize_workpackage_plan(plan)


def apply_project_options(plan: WorkpackagePlan, options: list[str]) -> WorkpackagePlan:
    plan.project_options = options
    if not plan.project and len(options) == 1:
        plan.project = options[0]
    return plan


def missing_slots(plan: WorkpackagePlan) -> list[str]:
    missing: list[str] = []
    if not plan.fill_days and plan.period_hint != "本周":
        missing.append("填报天数")
    if not plan.project and not plan.project_options:
        missing.append("项目名称")
    return missing


def needs_project_selection(plan: WorkpackagePlan) -> bool:
    return not plan.project and len(plan.project_options) > 1


def is_ready_to_execute(plan: WorkpackagePlan) -> bool:
    if needs_project_selection(plan):
        return False
    return len(missing_slots(plan)) == 0


def _plan_item(label: str, value: str | int | float | None) -> dict[str, str]:
    if value is None or value == "":
        display = "—"
    else:
        display = str(value)
    return {"label": label, "value": display}


def workpackage_plan_confirm_items(plan: WorkpackagePlan) -> list[dict[str, str]]:
    period_display = plan.period_hint or "本周"
    if plan.date_start and plan.date_end:
        period_display = format_date_range(
            date.fromisoformat(plan.date_start),
            date.fromisoformat(plan.date_end),
        )
    items = [
        _plan_item("项目名称", plan.project or ("请选择" if plan.project_options else None)),
        _plan_item("填报天数", f"{plan.fill_days:g} 天" if plan.fill_days else None),
        _plan_item("填报周期", period_display),
        _plan_item("每日工时", f"{plan.hours_per_day:g} 小时"),
    ]
    if plan.total_person_days:
        items.append(_plan_item("项目总人天", f"{plan.total_person_days:g} 人天"))
    if plan.content:
        items.append(_plan_item("工作内容", plan.content))
    return items


def build_workpackage_plan_confirm_content(plan: WorkpackagePlan) -> str:
    period_display = plan.period_hint or "本周"
    if plan.date_start and plan.date_end:
        period_display = format_date_range(
            date.fromisoformat(plan.date_start),
            date.fromisoformat(plan.date_end),
        )
    lines = [
        "信息已齐全，请核对以下工时填报信息：",
        "",
        f"- 项目：**{plan.project or '待选择'}**",
        f"- 填报天数：**{plan.fill_days:g} 天**" if plan.fill_days else "- 填报天数：—",
        f"- 填报周期：**{period_display}**",
        f"- 每日工时：**{plan.hours_per_day:g} 小时**（默认）",
        "",
    ]
    if needs_project_selection(plan):
        lines.append("👇 请先点击选择项目，再点击「确认开始办理」。")
    elif not plan.project:
        lines.append("👇 请先补充项目名称（可直接在对话中说明），再点击「确认开始办理」。")
    else:
        lines.append("👇 请确认无误后点击下方「确认开始办理」，无需再用文字回复。")
    return "\n".join(lines)


def build_workpackage_plan_confirm_metadata(plan: WorkpackagePlan) -> dict:
    return {
        "interactive": True,
        "workpackage_plan_confirm": {
            "status": "pending",
            "title": f"{plan.project or '本周'}工时填报",
            "items": workpackage_plan_confirm_items(plan),
            "project_options": plan.project_options,
            "selected_project": plan.project,
            "date_start": plan.date_start,
            "date_end": plan.date_end,
            "hours_per_day": plan.hours_per_day,
            "requires_project": not plan.project and not plan.project_options,
        },
    }


def build_workpackage_confirm_content(plan: WorkpackagePlan, fill_plan: dict) -> str:
    conflicts = fill_plan.get("conflicts") or []
    fillable = fill_plan.get("fillable_days", plan.fill_days)
    requested = fill_plan.get("requested_days", plan.fill_days)
    period_label = fill_plan.get("period_label") or plan.period_hint or "本周"
    lines = [
        f"已查询 **{period_label}** 工时填报情况，准备为 **{plan.project}** 填报 {requested:g} 天。",
        f"每日默认 **{plan.hours_per_day:g} 小时**，请在下方勾选需要填报的日期并确认。",
        "",
    ]
    if conflicts:
        for c in conflicts:
            lines.append(
                f"- **{c.get('day_label')}**{c.get('period')}已使用 "
                f"**{c.get('existing_project')}** 完成 {c.get('hours', 4):g} 小时填报"
            )
        lines.extend(
            [
                "",
                f"其余 **{fillable:g} 天** 仍可使用 **{plan.project}** 进行填报。",
            ]
        )
    else:
        lines.append("未发现冲突，请勾选下方日期并确认填报计划。")
    return "\n".join(lines)


def build_workpackage_confirm_metadata(plan: WorkpackagePlan, fill_plan: dict) -> dict:
    return {
        "interactive": True,
        "workpackage_confirm": {
            "status": "pending",
            "project": plan.project or "",
            "period_label": fill_plan.get("period_label") or plan.period_hint or "本周",
            "requested_days": fill_plan.get("requested_days", plan.fill_days),
            "fillable_days": fill_plan.get("fillable_days"),
            "total_budget_days": plan.total_person_days,
            "hours_per_day": plan.hours_per_day,
            "conflicts": fill_plan.get("conflicts") or [],
            "entries": fill_plan.get("entries") or [],
        },
    }


def build_execution_summary(plan: WorkpackagePlan, task_id: str, fill_plan: dict) -> str:
    entries = fill_plan.get("entries") or []
    lines = [
        f"工包填报计划已确认，已为您启动 **{plan.project}** 填报流程：",
        "",
        "一、填报明细",
    ]
    for entry in entries:
        hours = entry.get("hours", plan.hours_per_day)
        lines.append(f"- {entry.get('day_label')}（{entry.get('day_date')}）：{hours:g} 小时")
    total_hours = sum(e.get("hours", plan.hours_per_day) for e in entries)
    lines.extend(
        [
            f"- 合计：**{total_hours:g} 小时**",
            "",
            "二、后续步骤",
            "- 已生成工包填报表单，请在任务卡片中查看并确认提交",
            "",
            "请点击下方任务卡片查看详情。",
        ]
    )
    return "\n".join(lines)


def build_task_metadata(plan: WorkpackagePlan, task_id: str) -> dict:
    return {
        "task_id": task_id,
        "task_title": f"{plan.project or '工包'}填报",
        "progress": "1/2",
        "progress_percent": 50,
        "steps_desc": "工包填报 · 用户确认",
    }
