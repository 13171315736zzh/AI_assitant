"""从用户对话中规则抽取长期记忆字段。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.agent.memory_normalizer import (
    extract_base_location_from_text,
    extract_city_name,
    extract_project_hints_from_text,
)
from src.agent.user_memory import (
    GENERIC_POSITIONS,
    extract_position_type_from_text,
    extract_travel_mode_preference_from_text,
    normalize_position_type,
    normalize_travel_mode_preference,
)

MAX_MEMORY_ITEMS = 120
MAX_FIELD_VALUE_LEN = 512

CORE_STRUCTURED_FIELD_KEYS = frozenset({
    "display_name",
    "gender",
    "id_number",
    "employee_id",
    "job_role",
    "position",
    "base_location",
    "department",
    "email",
    "travel_mode_preference",
    "related_projects",
})

# 扩展记忆条目 reserved：与上方「核心个人信息」重复的键名不再展示
EXTENSION_ITEM_RESERVED_KEYS = frozenset({
    *CORE_STRUCTURED_FIELD_KEYS,
    "姓名",
    "性别",
    "身份证号",
    "身份证",
    "工号",
    "员工编号",
    "岗位",
    "岗位类型",
    "职位",
    "职级",
    "常驻地（Base）",
    "常驻地",
    "Base",
    "BASE",
    "Base地",
    "base地",
    "部门",
    "默认部门",
    "所属部门",
    "邮箱",
    "电子邮箱",
    "交通偏好",
    "出行偏好",
    "关联项目",
    "负责项目",
})

_RESERVED_KEY_FOLDED = frozenset(key.casefold() for key in EXTENSION_ITEM_RESERVED_KEYS)

_STRUCTURED_FIELD_RULES: tuple[tuple[str, re.Pattern[str], str | None], ...] = (
    ("display_name", re.compile(r"(?:我叫|姓名[是为：:]\s*|本人叫)\s*([\u4e00-\u9fff]{2,8})"), None),
    ("gender", re.compile(r"(?:性别[是为：:]\s*)?(男|女)(?:性)?"), None),
    (
        "id_number",
        re.compile(r"(?:身份证(?:号)?[是为：:]\s*)?(\d{17}[\dXx])"),
        None,
    ),
    (
        "employee_id",
        re.compile(r"(?:工号[是为：:\s]*|员工编号[是为：:\s]*)([A-Za-z0-9]{1,9})"),
        None,
    ),
    (
        "job_role",
        re.compile(
            r"(?:我的)?岗位[是为：:\s]*"
            r"(产品经理|前端(?:工程师|开发)?|后端(?:工程师|开发)?|算法(?:工程师)?|"
            r"运维(?:工程师)?|运营(?:专员)?|测试(?:工程师)?|UI设计(?:师)?|"
            r"产品(?:经理|专员)?|开发(?:工程师)?)"
        ),
        None,
    ),
    (
        "job_role",
        re.compile(
            r"(?:我是(?:一名)?|担任)\s*"
            r"(产品经理|前端(?:工程师|开发)?|后端(?:工程师|开发)?|算法(?:工程师)?|"
            r"运维(?:工程师)?|运营(?:专员)?|测试(?:工程师)?|UI设计(?:师)?)"
        ),
        None,
    ),
    (
        "base_location",
        re.compile(r"常驻地\s*[是为：:\s]*([\u4e00-\u9fff]{2,6}(?:市)?)"),
        None,
    ),
    (
        "base_location",
        re.compile(
            r"(?:Base|base|BASE)(?:地|城市)?\s*[是为：:\s]*"
            r"([\u4e00-\u9fff]{2,6}(?:市)?)"
        ),
        None,
    ),
    (
        "base_location",
        re.compile(
            r"(?:常驻|工作地|办公地)(?:地|城市)?\s*[是为：:\s]*"
            r"([\u4e00-\u9fff]{2,6}(?:市)?)"
        ),
        None,
    ),
    (
        "base_location",
        re.compile(r"我在([\u4e00-\u9fff]{2,6}(?:市)?)(?:工作|办公|上班)"),
        None,
    ),
    (
        "department",
        re.compile(r"(?:部门[是为：:]\s*|所属部门[是为：:]\s*)([\u4e00-\u9fffA-Za-z0-9（）()·\-\s]{2,32})"),
        None,
    ),
    (
        "email",
        re.compile(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"),
        None,
    ),
    (
        "travel_mode_preference",
        re.compile(r"交通偏好[是为：:\s]*(飞机|高铁|自驾|无偏好)"),
        None,
    ),
)

# 「我是智能矿山部的产品经理」：部门 + 岗位
_IAM_DEPT_AND_ROLE = re.compile(
    r"我是"
    r"([\u4e00-\u9fffA-Za-z0-9（）()·\-]{2,32}?(?:部|事业部|中心|处|科|室|组|分公司|集团)?)"
    r"(?:的)?"
    r"(产品经理|前端(?:工程师|开发)?|后端(?:工程师|开发)?|算法(?:工程师)?|"
    r"运维(?:工程师)?|运营(?:专员)?|测试(?:工程师)?|UI设计(?:师)?|"
    r"产品(?:经理|专员)?|开发(?:工程师)?)"
)

# 「我是产品经理」：仅岗位（无部门前缀）
_JOB_ROLE_FROM_IAM = re.compile(
    r"我是(?:一名)?\s*"
    r"(产品经理|前端(?:工程师|开发)?|后端(?:工程师|开发)?|算法(?:工程师)?|"
    r"运维(?:工程师)?|运营(?:专员)?|测试(?:工程师)?|UI设计(?:师)?|"
    r"产品(?:经理|专员)?|开发(?:工程师)?)"
)

_LOOSE_FIELD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("id_number", re.compile(r"身份证(?:号)?[是为：:\s]*([^\s，,。；;]{4,24})")),
    ("employee_id", re.compile(r"(?:工号|员工编号)[是为：:\s]*([^\s，,。；;]{1,24})")),
    ("email", re.compile(r"邮箱[是为：:\s]*([^\s，,。；;]+)")),
    (
        "travel_mode_preference",
        re.compile(r"交通偏好[是为：:\s]*([^\s，,。；;]{1,12})"),
    ),
)

_KV_RULES: tuple[tuple[str, re.Pattern[str], int], ...] = (
    ("常用出差目的地", re.compile(r"常去(.{2,20}?)(?:出差|办事)"), 1),
    ("常用联系人", re.compile(r"联系人[是为：:]\s*(.{2,24})"), 1),
    ("沟通偏好", re.compile(r"(简洁|详细|表格).{0,6}(?:回复|展示|说明)"), 0),
    ("差旅偏好", re.compile(r"(优先.{0,8}航班|经济舱|商务舱|高铁优先)"), 0),
    ("直属主管", re.compile(r"主管[是为叫：:]\s*([\u4e00-\u9fff]{2,4})"), 1),
    ("默认出发地", re.compile(r"从([\u4e00-\u9fff]{2,8}(?:市|机场)?)出发"), 1),
)


def _normalize_gender(value: str) -> str:
    if value in ("男", "male", "M"):
        return "男"
    if value in ("女", "female", "F"):
        return "女"
    return value


def _clean_value(value: str) -> str:
    return value.strip("，,。；; \t")[:MAX_FIELD_VALUE_LEN]


def _is_placeholder(field: str, value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if field == "position":
        return text in GENERIC_POSITIONS
    return False


def is_reserved_extension_memory_key(key: str) -> bool:
    normalized = (key or "").strip()
    if not normalized:
        return True
    if normalized in EXTENSION_ITEM_RESERVED_KEYS:
        return True
    return normalized.casefold() in _RESERVED_KEY_FOLDED


def filter_extension_memory_items(items: list[dict]) -> list[dict]:
    """过滤与核心 structured 字段重复的扩展记忆条目。"""
    filtered: list[dict] = []
    for item in items:
        key = str(item.get("key", "")).strip()
        value = str(item.get("value", "")).strip()
        if not key or not value or is_reserved_extension_memory_key(key):
            continue
        filtered.append({"key": key, "value": value})
    return filtered[:MAX_MEMORY_ITEMS]


@dataclass
class StructuredExtractResult:
    updates: dict[str, Any]
    field_errors: dict[str, str]


def _apply_validated_field(
    field: str,
    raw_value: str,
    updates: dict[str, Any],
    field_errors: dict[str, str],
) -> None:
    from src.agent.memory_validators import (
        format_field_error,
        normalize_employee_id,
        normalize_id_number,
        validate_email,
        validate_employee_id,
        validate_id_number,
    )

    if field == "id_number":
        value = normalize_id_number(raw_value)
        error = validate_id_number(value)
        updates[field] = value
        if error:
            field_errors[field] = format_field_error(field, error)
        return

    if field == "employee_id":
        value = normalize_employee_id(raw_value)
        error = validate_employee_id(value)
        updates[field] = value
        if error:
            field_errors[field] = format_field_error(field, error)
        return

    if field == "email":
        value = _clean_value(raw_value)
        error = validate_email(value)
        updates[field] = value
        if error:
            field_errors[field] = format_field_error(field, error)
        return

    if field == "travel_mode_preference":
        value = _clean_value(raw_value)
        normalized = normalize_travel_mode_preference(value)
        if normalized:
            updates[field] = normalized
        else:
            updates[field] = value
            field_errors[field] = format_field_error(
                field,
                "请从飞机、高铁、自驾、无偏好中选择",
            )
        return

    updates[field] = raw_value


def _extract_loose_validated_fields(
    text: str,
    updates: dict[str, Any],
    field_errors: dict[str, str],
) -> None:
    for field, pattern in _LOOSE_FIELD_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw = _clean_value(match.group(1))
        if not raw:
            continue
        # 宽松匹配覆盖 strict 的部分截取，保留用户完整输入以便提示修改
        _apply_validated_field(field, raw, updates, field_errors)


def _apply_iam_department_and_role(
    text: str,
    updates: dict[str, Any],
) -> None:
    match = _IAM_DEPT_AND_ROLE.search(text)
    if match:
        dept = _clean_value(match.group(1))
        role = _clean_value(match.group(2))
        if dept and "department" not in updates:
            updates["department"] = dept
        if role and "job_role" not in updates:
            updates["job_role"] = role
        return

    iam_match = _JOB_ROLE_FROM_IAM.search(text)
    if iam_match and "job_role" not in updates:
        updates["job_role"] = _clean_value(iam_match.group(1))


def extract_structured_with_validation(text: str) -> StructuredExtractResult:
    """从单条用户消息抽取结构化字段，并保留格式不合规的填写值供用户修改。"""
    if not text.strip():
        return StructuredExtractResult({}, {})

    updates: dict[str, Any] = {}
    field_errors: dict[str, str] = {}
    for field, pattern, _ in _STRUCTURED_FIELD_RULES:
        match = pattern.search(text)
        if not match:
            continue
        value = _clean_value(match.group(1) if match.lastindex else match.group(0))
        if not value:
            continue
        if field == "gender":
            value = _normalize_gender(value)
        if field == "base_location":
            city = extract_city_name(value)
            if city:
                value = city
            else:
                continue
        if field in ("id_number", "employee_id", "email"):
            _apply_validated_field(field, value, updates, field_errors)
            continue
        if field not in updates:
            updates[field] = value

    _extract_loose_validated_fields(text, updates, field_errors)

    base_from_text = extract_base_location_from_text(text)
    if base_from_text:
        updates["base_location"] = base_from_text

    _apply_iam_department_and_role(text, updates)

    position_type = extract_position_type_from_text(text)
    if position_type:
        updates["position"] = position_type

    travel_pref = extract_travel_mode_preference_from_text(text)
    if travel_pref and "travel_mode_preference" not in updates:
        updates["travel_mode_preference"] = travel_pref

    projects = extract_project_hints_from_text(text)
    if projects:
        updates["_new_projects"] = projects

    return StructuredExtractResult(updates=updates, field_errors=field_errors)


def extract_structured_updates(text: str) -> dict[str, Any]:
    """从单条用户消息抽取结构化字段更新。"""
    return extract_structured_with_validation(text).updates


def extract_memory_item_updates(text: str) -> list[dict[str, str]]:
    """从单条用户消息抽取扩展 KV 记忆。"""
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for key, pattern, group in _KV_RULES:
        match = pattern.search(text)
        if not match:
            continue
        value = _clean_value(match.group(group) if group else match.group(0))
        if not value or key in seen:
            continue
        seen.add(key)
        items.append({"key": key, "value": value})
    return items


def merge_structured(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """合并结构化更新：非空更新一律以最新值为准。"""
    from src.agent.memory_validators import normalize_employee_id, normalize_id_number

    merged = dict(existing)
    new_projects = updates.pop("_new_projects", None)
    replace_projects = bool(updates.pop("_replace_projects", False))

    if "related_projects" in updates and updates["related_projects"] is not None:
        merged["related_projects"] = list(updates.pop("related_projects") or [])[:20]

    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if key == "position":
            normalized = normalize_position_type(str(value))
            if not normalized:
                continue
            value = normalized
        elif key == "travel_mode_preference":
            normalized = normalize_travel_mode_preference(str(value))
            if not normalized:
                continue
            value = normalized
        elif key == "id_number":
            value = normalize_id_number(str(value))
        elif key == "employee_id":
            value = normalize_employee_id(str(value))
        merged[key] = value

    if new_projects and not replace_projects:
        current_projects = list(merged.get("related_projects") or [])
        for project in new_projects:
            if project not in current_projects:
                current_projects.append(project)
        merged["related_projects"] = current_projects[:20]
    elif new_projects and replace_projects:
        merged["related_projects"] = new_projects[:20]
    return merged


def sanitize_structured_seed(existing: dict[str, Any] | None) -> dict[str, Any]:
    """清除占位默认值，避免误导确认面板。"""
    data = dict(existing or {})
    for key in ("position", "job_role"):
        if _is_placeholder(key, data.get(key)):
            data[key] = ""
    pos = normalize_position_type(str(data.get("position") or ""))
    if pos:
        data["position"] = pos
    pref = normalize_travel_mode_preference(str(data.get("travel_mode_preference") or ""))
    if pref:
        data["travel_mode_preference"] = pref
    elif data.get("travel_mode_preference"):
        data["travel_mode_preference"] = ""
    return data


def merge_memory_items(existing: list[dict], updates: list[dict]) -> list[dict]:
    item_map = {
        str(item.get("key", "")).strip(): dict(item)
        for item in existing
        if str(item.get("key", "")).strip()
    }
    for item in updates:
        key = str(item.get("key", "")).strip()
        value = _clean_value(str(item.get("value", "")))
        if not key or not value:
            continue
        item_map[key] = {"key": key, "value": value}
    items = list(item_map.values())
    return filter_extension_memory_items(items)


def count_memory_fields(structured: dict, memory_items: list[dict]) -> int:
    count = 0
    for key, value in structured.items():
        if key.startswith("_"):
            continue
        if value not in (None, "", [], "unknown"):
            if isinstance(value, list):
                count += len(value)
            else:
                count += 1
    count += len(memory_items)
    return count
