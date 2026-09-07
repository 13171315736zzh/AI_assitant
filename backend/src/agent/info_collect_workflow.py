"""信息收集流程：收集并确认用户核心个人信息（长期记忆）。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.agent.memory_extractor import (
    extract_structured_with_validation,
    merge_structured,
    sanitize_structured_seed,
)
from src.agent.memory_validators import validate_structured_fields
from src.agent.session_context import is_plan_revision_text, merge_user_texts
from src.agent.user_memory import extract_position, is_position_confirmed

_INFO_COLLECT_INTENT = re.compile(
    r"填信息|信息收集|信息采集|个人信息|个人资料|完善信息|完善资料|"
    r"录入信息|填写个人信息|长期记忆|核心信息|我的信息"
)

_CORE_FIELD_DEFS: tuple[tuple[str, str], ...] = (
    ("display_name", "姓名"),
    ("gender", "性别"),
    ("id_number", "身份证号"),
    ("employee_id", "工号"),
    ("job_role", "岗位"),
    ("position", "岗位类型"),
    ("base_location", "常驻地（Base）"),
    ("department", "部门"),
    ("email", "邮箱"),
    ("travel_mode_preference", "交通偏好"),
    ("related_projects", "关联项目"),
)


@dataclass
class PersonalInfoCollectPlan:
    structured: dict[str, Any] = field(default_factory=dict)
    field_errors: dict[str, str] = field(default_factory=dict)
    raw_goal: str = ""


def _empty_structured() -> dict[str, Any]:
    return {
        "display_name": "",
        "gender": "unknown",
        "id_number": "",
        "employee_id": "",
        "job_role": "",
        "position": "",
        "base_location": "",
        "department": "",
        "email": "",
        "travel_mode_preference": "",
        "related_projects": [],
    }


def _field_filled(key: str, value: Any) -> bool:
    if key == "gender":
        return bool(value and str(value).strip() not in ("", "unknown"))
    if key == "related_projects":
        return bool(value and isinstance(value, list) and len(value) > 0)
    return bool(value and str(value).strip())


def _format_field_value(key: str, value: Any) -> str:
    if key == "related_projects":
        if isinstance(value, list):
            return "、".join(str(v) for v in value if str(v).strip()) or "—"
        return "—"
    if key == "gender" and str(value).strip() in ("", "unknown"):
        return "—"
    text = str(value or "").strip()
    return text or "—"


def is_info_collect_workflow_intent(text: str) -> bool:
    from src.agent.workflow_queue import split_intent_segments

    segments = split_intent_segments(text)
    for segment in segments:
        if _INFO_COLLECT_INTENT.search(segment):
            return True
    return False


def is_info_collect_plan_update(text: str) -> bool:
    if is_plan_revision_text(text):
        return True
    if _INFO_COLLECT_INTENT.search(text):
        return True
    if extract_structured_with_validation(text).updates:
        return True
    if re.search(
        r"姓名|性别|身份证|工号|岗位|常驻|base|部门|邮箱|交通|项目|"
        r"男|女|@|0176|经理|事业部|前端|后端|算法|运维|运营|产品经理|"
        r"管理岗|非管理岗",
        text,
        re.I,
    ):
        return True
    return False


def merge_structured_from_messages(
    messages,
    existing: dict[str, Any],
    *,
    assistant_context: str | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    structured = merge_structured(_empty_structured(), sanitize_structured_seed(existing or {}))
    field_errors: dict[str, str] = {}
    user_texts = [
        record.content.strip()
        for record in messages
        if getattr(record, "role", None) == "user" and record.content.strip()
    ]
    for text in user_texts:
        extracted = extract_structured_with_validation(text)
        if not is_position_confirmed(structured.get("position")) or extracted.updates.get("position"):
            position = extract_position(text, assistant_context)
            if position and "position" not in extracted.updates:
                extracted.updates["position"] = position
        structured = merge_structured(structured, extracted.updates)
        field_errors.update(extracted.field_errors)

    for key, message in validate_structured_fields(structured).items():
        field_errors[key] = message
    return structured, field_errors


def build_personal_info_plan(
    messages,
    existing_structured: dict[str, Any] | None = None,
    *,
    assistant_context: str | None = None,
) -> PersonalInfoCollectPlan:
    combined = merge_user_texts(
        [
            record.content.strip()
            for record in messages
            if getattr(record, "role", None) == "user" and record.content.strip()
        ]
    )
    structured, field_errors = merge_structured_from_messages(
        messages,
        existing_structured or {},
        assistant_context=assistant_context,
    )
    return PersonalInfoCollectPlan(
        structured=structured,
        field_errors=field_errors,
        raw_goal=combined[:500],
    )


def missing_slots(plan: PersonalInfoCollectPlan) -> list[str]:
    missing: list[str] = []
    for key, label in _CORE_FIELD_DEFS:
        if not _field_filled(key, plan.structured.get(key)):
            missing.append(label)
    return missing


def filled_field_count(plan: PersonalInfoCollectPlan) -> int:
    return sum(
        1 for key, _ in _CORE_FIELD_DEFS if _field_filled(key, plan.structured.get(key))
    )


def is_ready_to_execute(plan: PersonalInfoCollectPlan) -> bool:
    return filled_field_count(plan) > 0 or bool(plan.field_errors)


def _format_field_error_lines(field_errors: dict[str, str]) -> list[str]:
    if not field_errors:
        return []
    lines = ["", "以下字段需要修改："]
    for message in field_errors.values():
        lines.append(f"- {message}")
    return lines


def build_info_collect_plan_confirm_items(plan: PersonalInfoCollectPlan) -> list[dict[str, str]]:
    return [
        {"label": label, "value": _format_field_value(key, plan.structured.get(key))}
        for key, label in _CORE_FIELD_DEFS
    ]


def build_info_collect_plan_confirm_content(
    plan: PersonalInfoCollectPlan, *, updated: bool = False
) -> str:
    intro = (
        "已根据您补充的信息更新核心个人信息，请核对："
        if updated
        else "请核对以下核心个人信息，确认后将写入长期记忆："
    )
    lines = [intro, ""]
    for item in build_info_collect_plan_confirm_items(plan):
        value = item["value"]
        if value != "—":
            lines.append(f"- **{item['label']}**：{value}")
        else:
            lines.append(f"- {item['label']}：—（未填写）")
    lines.extend(_format_field_error_lines(plan.field_errors))
    missing = missing_slots(plan)
    if missing:
        lines.extend(
            [
                "",
                f"您还可以继续补充：**{'、'.join(missing[:6])}**"
                + ("等" if len(missing) > 6 else ""),
            ]
        )
    lines.extend(
        [
            "",
            "👇 可在下方直接修改字段，确认后将保存到长期记忆（可在「长期记忆」页面查看）。",
        ]
    )
    return "\n".join(lines)


def build_info_collect_plan_confirm_metadata(plan: PersonalInfoCollectPlan) -> dict:
    meta: dict[str, Any] = {
        "status": "pending",
        "title": "核心个人信息",
        "items": build_info_collect_plan_confirm_items(plan),
        "structured": dict(plan.structured),
    }
    if plan.field_errors:
        meta["field_errors"] = dict(plan.field_errors)
    return {
        "info_collect_plan_confirm": meta,
    }


def build_execution_summary(plan: PersonalInfoCollectPlan) -> str:
    filled = filled_field_count(plan)
    missing = missing_slots(plan)
    lines = [
        "已将 **核心个人信息** 保存到长期记忆：",
        "",
        f"- 已录入 **{filled}** 项核心字段",
    ]
    if missing:
        lines.append(f"- 仍可补充：{'、'.join(missing[:8])}" + ("…" if len(missing) > 8 else ""))
    lines.extend(
        [
            "",
            "后续办理差旅、工包、请假等业务时，助手将自动参考这些信息，无需重复询问。",
            "您可随时在顶栏「长期记忆」中查看或修改。",
        ]
    )
    return "\n".join(lines)
