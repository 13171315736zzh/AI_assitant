"""用户长期记忆：注入 Agent 上下文、差旅推断、从对话抽取。"""

from __future__ import annotations

import re

# 占位职级/岗位，不算用户已确认
GENERIC_POSITIONS = frozenset({"", "员工", "管理员", "unknown"})

# 岗位类型仅两类（长期记忆 + 信息收集）
POSITION_TYPE_MANAGEMENT = "管理岗"
POSITION_TYPE_NON_MANAGEMENT = "非管理岗"
VALID_POSITION_TYPES = frozenset({POSITION_TYPE_MANAGEMENT, POSITION_TYPE_NON_MANAGEMENT})

# 交通偏好字典值
TRAVEL_MODE_PREFERENCES: tuple[str, ...] = ("飞机", "高铁", "自驾", "无偏好")

_ASK_POSITION_HINT = re.compile(r"职级|职位|职务|人员类别|岗位类型|您的职|管理岗|非管理岗")

# 项目/地点 → 常去目的地（用于与 base 地对比推断出差）
_PROJECT_DESTINATIONS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"神东|鄂尔多斯|伊旗|伊金霍洛"), "鄂尔多斯", "神东"),
    (re.compile(r"雁宝|燕宝|宁东"), "宁东", "雁宝"),
    (re.compile(r"北京|总部"), "北京", "北京"),
    (re.compile(r"上海"), "上海", "上海"),
)


def normalize_position_type(value: str | None) -> str | None:
    """统一岗位类型为「管理岗」或「非管理岗」。"""
    text = (value or "").strip()
    if not text:
        return None
    if text in VALID_POSITION_TYPES:
        return text
    if text in ("非领导岗", "非领导", "非管理", "其他人员", "普通员工", "一般员工", "职员", "项目经理"):
        return POSITION_TYPE_NON_MANAGEMENT
    if text in ("领导岗", "其他负责人", "主要负责人", "部门负责人", "副总", "负责人", "公司领导"):
        return POSITION_TYPE_MANAGEMENT
    return None


def extract_position_type_from_text(text: str) -> str | None:
    """从用户表述识别岗位类型（管理岗 / 非管理岗）。"""
    if not text.strip():
        return None
    if re.search(r"非管理岗|非领导岗", text):
        return POSITION_TYPE_NON_MANAGEMENT
    if re.search(r"非管理(?!岗)|非领导(?!岗)", text):
        return POSITION_TYPE_NON_MANAGEMENT
    explicit = re.search(
        r"岗位类型[是为：:\s]*(管理岗|非管理岗|非领导岗|领导岗)",
        text,
    )
    if explicit:
        return normalize_position_type(explicit.group(1))
    trailing = re.search(r"[，,、]\s*(非管理岗|非领导岗|管理岗|领导岗)\s*$", text)
    if trailing:
        return normalize_position_type(trailing.group(1))
    if re.search(r"(?:我是|属于)(非管理岗|非领导岗|管理岗|领导岗)", text):
        token = re.search(r"(?:我是|属于)(非管理岗|非领导岗|管理岗|领导岗)", text)
        if token:
            return normalize_position_type(token.group(1))
    if re.search(r"(?<![非])管理岗|领导岗", text):
        return POSITION_TYPE_MANAGEMENT
    return None


def normalize_travel_mode_preference(value: str | None) -> str | None:
    """统一交通偏好为：飞机 / 高铁 / 自驾 / 无偏好。"""
    text = (value or "").strip()
    if not text:
        return None
    if text in TRAVEL_MODE_PREFERENCES:
        return text
    if re.search(r"飞机|航班|机票|航空|经济舱|商务舱", text):
        return "飞机"
    if re.search(r"高铁|动车|火车|铁路", text):
        return "高铁"
    if re.search(r"自驾|开车|自驾车|自己开车", text):
        return "自驾"
    if re.search(r"无偏好|没有偏好|不限|都行|随便|无所谓", text):
        return "无偏好"
    return None


def extract_travel_mode_preference_from_text(text: str) -> str | None:
    if not text.strip():
        return None
    explicit = re.search(
        r"交通偏好[是为：:\s]*(飞机|高铁|自驾|无偏好)",
        text,
    )
    if explicit:
        return normalize_travel_mode_preference(explicit.group(1))
    if re.search(r"高铁优先|优先高铁|坐高铁|乘高铁", text):
        return "高铁"
    if re.search(r"飞机优先|优先飞机|坐飞机|乘飞机|要机票|订机票", text):
        return "飞机"
    if re.search(r"自驾|开车去|自己开车", text):
        return "自驾"
    return normalize_travel_mode_preference(text)


def is_position_confirmed(position: str | None) -> bool:
    return normalize_position_type(position) in VALID_POSITION_TYPES


def extract_position(user_content: str, assistant_context: str | None = None) -> str | None:
    text = (user_content or "").strip()
    if not text:
        return None
    found = extract_position_type_from_text(text)
    if found:
        return found
    asked = bool(assistant_context and _ASK_POSITION_HINT.search(assistant_context))
    if asked and len(text) <= 32:
        compact = text.replace("。", "").replace("，", "").strip()
        normalized = normalize_position_type(compact)
        if normalized:
            return normalized
    return None


def position_to_travel_staff_level(position: str | None) -> str | None:
    normalized = normalize_position_type(position)
    if normalized == POSITION_TYPE_NON_MANAGEMENT:
        return "其他人员"
    if normalized == POSITION_TYPE_MANAGEMENT:
        return "其他负责人"
    # 兼容差旅细则原文职级表述
    if position in ("主要负责人", "其他负责人", "其他人员"):
        return position
    return None


def resolve_travel_staff_level(
    *,
    memory_structured: dict | None = None,
    override: str | None = None,
    from_message: str | None = None,
) -> str:
    """优先长期记忆中的岗位类型，映射为差旅人员类别（住宿/交通标准）。"""
    for candidate in (override, from_message):
        if not candidate:
            continue
        mapped = position_to_travel_staff_level(candidate)
        if mapped:
            return mapped
    if memory_structured:
        pos = (memory_structured.get("position") or "").strip()
        if is_position_confirmed(pos):
            mapped = position_to_travel_staff_level(pos)
            if mapped:
                return mapped
    return "其他人员"


def _normalize_city(name: str) -> str:
    return name.replace("市", "").replace("区", "").replace("县", "").strip()


def resolve_destination_from_text(text: str, related_projects: list[str] | None = None) -> str | None:
    combined = text
    if related_projects:
        combined = f"{text} {' '.join(related_projects)}"
    for pattern, destination, _ in _PROJECT_DESTINATIONS:
        if pattern.search(combined):
            return destination
    dest_match = re.search(
        r"(?:去|到|前往|赴)\s*([\u4e00-\u9fff]{2,8}(?:市|区|县)?)",
        text,
    )
    if dest_match:
        return _normalize_city(dest_match.group(1))
    return None


def infer_travel_intent_from_memory(
    text: str,
    structured: dict,
) -> dict[str, object]:
    """
    结合长期记忆推断隐含差旅/订票意图。
    例：base=北京，提到神东项目开会 → 需出差+订票，目的地鄂尔多斯。
    """
    base = _normalize_city(str(structured.get("base_location") or ""))
    projects = list(structured.get("related_projects") or [])
    destination = resolve_destination_from_text(text, projects)
    if not destination:
        return {}

    mentions_remote_event = bool(
        re.search(
            r"开会|会议|出差|差旅|现场|驻场|培训|调研|办事|办公地点|到达|抵达|"
            r"住[两二三四\d]+天|去.{1,6}(?:项目|现场)",
            text,
        )
    )
    if not mentions_remote_event and not any(k in text for k in ("神东", "雁宝", "燕宝", "鄂尔多斯")):
        return {}

    origin = base or None
    needs_travel = bool(origin and _normalize_city(destination) != _normalize_city(origin))
    if not needs_travel and origin:
        return {}
    if not origin:
        needs_travel = True

    result: dict[str, object] = {
        "needs_travel": needs_travel,
        "needs_booking": needs_travel,
        "destination": destination,
        "origin": origin,
        "inferred_from_memory": True,
    }
    if re.search(r"订票|机票|航班|高铁|火车|车票", text):
        result["needs_booking"] = True
    return result


def build_user_memory_snippets(
    display_name: str,
    structured: dict,
    memory_items: list[dict],
    memory_enabled: bool = True,
) -> str:
    if not memory_enabled:
        return ""

    name = (structured.get("display_name") or display_name or "").strip()
    job_role = (structured.get("job_role") or "").strip()
    position = (structured.get("position") or "").strip()
    base_location = (structured.get("base_location") or "").strip()
    gender = (structured.get("gender") or "").strip()
    employee_id = (structured.get("employee_id") or "").strip()
    id_number = (structured.get("id_number") or "").strip()
    projects = structured.get("related_projects") or []

    lines = [
        "\n【当前用户长期记忆（必须优先使用，勿重复追问已知信息）】",
        f"- 姓名：{name or display_name}（写邮件/填单时直接使用，禁止再询问用户姓名）",
    ]

    if gender and gender != "unknown":
        lines.append(f"- 性别：{gender}")
    if employee_id:
        lines.append(f"- 工号：{employee_id}")
    if job_role:
        lines.append(f"- 岗位：{job_role}（已写入长期记忆，禁止再次询问）")
    if id_number:
        masked = id_number[:6] + "********" + id_number[-4:] if len(id_number) >= 14 else id_number
        lines.append(f"- 身份证号：{masked}（填单可用完整号码，勿向用户重复索要）")
    if base_location:
        lines.append(
            f"- 常驻地（Base）：{base_location}（推断出差时默认出发地；"
            f"用户提及外地项目/会议且未说「本地」时，应识别为出差并建议订票）"
        )
    if projects:
        lines.append(f"- 关联项目：{'、'.join(str(p) for p in projects[:8])}")

    if is_position_confirmed(position):
        display = normalize_position_type(position) or position
        lines.append(f"- 岗位类型：{display}（管理岗/非管理岗，已写入长期记忆，禁止再次询问）")
        travel_level = position_to_travel_staff_level(position)
        if travel_level:
            lines.append(f"- 差旅人员类别：{travel_level}（按此职级引用住宿/交通标准）")
    else:
        lines.append(
            "- 岗位类型：尚未确认（仅当办事确实需要且用户未提供时，可礼貌询问一次）"
        )

    dept = (structured.get("department") or "").strip()
    email = (structured.get("email") or "").strip()
    travel_pref = (structured.get("travel_mode_preference") or "").strip()
    if dept:
        lines.append(f"- 部门：{dept}")
    if email:
        lines.append(f"- 邮箱：{email}")
    if travel_pref:
        lines.append(f"- 交通偏好：{travel_pref}")

    shown_keys = {
        "姓名", "性别", "工号", "岗位", "身份证号", "常驻地", "关联项目", "岗位类型",
        "部门", "邮箱", "交通偏好", "差旅偏好", "职位",
    }
    for item in memory_items[:20]:
        key = (item.get("key") or "").strip()
        value = (item.get("value") or "").strip()
        if key and value and key not in shown_keys:
            lines.append(f"- {key}：{value}")

    return "\n".join(lines)
