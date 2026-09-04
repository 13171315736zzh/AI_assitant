"""长期记忆字段：解析后标准化（城市、关联项目等）。"""

from __future__ import annotations

import re
from typing import Any, Protocol

from src.agent.travel_policy_knowledge import normalize_city as strip_city_suffix

# 常见城市（用于从杂乱文本中识别城市名）
_KNOWN_CITIES: tuple[str, ...] = (
    "北京",
    "上海",
    "天津",
    "重庆",
    "石家庄",
    "太原",
    "呼和浩特",
    "沈阳",
    "大连",
    "长春",
    "哈尔滨",
    "南京",
    "杭州",
    "宁波",
    "合肥",
    "福州",
    "厦门",
    "南昌",
    "济南",
    "青岛",
    "郑州",
    "武汉",
    "长沙",
    "广州",
    "深圳",
    "珠海",
    "汕头",
    "南宁",
    "海口",
    "成都",
    "贵阳",
    "昆明",
    "拉萨",
    "西安",
    "兰州",
    "西宁",
    "银川",
    "乌鲁木齐",
    "鄂尔多斯",
    "包头",
    "赤峰",
    "海拉尔",
    "呼伦贝尔",
    "宁东",
    "苏州",
    "无锡",
)

_CITY_NO_SHI_SUFFIX = frozenset({"海拉尔", "神东", "宁东"})

_JUNK_CITY_PREFIX = re.compile(r"^[地城市是在为：:\s]+")

_PROJECT_SUFFIX = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9（）()·\-]{1,20}?(?:项目|工程(?!师)))"
)
_RESPONSIBLE_SEGMENT = re.compile(
    r"(?:我)?(?:负责|分管|参与|跟进|做)(?:的)?(.+?)(?:[。；!！?？]|$)"
)
_SPLIT_CONJUNCTION = re.compile(r"[和与及以及、,，]+")
_PROJECT_PREFIX = re.compile(r"^(?:我)?(?:负责|分管|参与|跟进|做|的|在)+")


class _ProjectMappingLike(Protocol):
    project_name: str
    aliases: str


def extract_base_location_from_text(text: str) -> str | None:
    """从用户消息抽取常驻地城市（仅城市核心名）。"""
    if not text.strip():
        return None
    patterns = (
        re.compile(r"常驻地\s*[是为：:\s]*([\u4e00-\u9fff]{2,6}(?:市)?)"),
        re.compile(
            r"(?:Base|base|BASE)(?:地|城市)?\s*[是为：:\s]*([\u4e00-\u9fff]{2,6}(?:市)?)"
        ),
        re.compile(
            r"(?:常驻|工作地|办公地)(?:地|城市)?\s*[是为：:\s]*"
            r"([\u4e00-\u9fff]{2,6}(?:市)?)"
        ),
        re.compile(r"我在([\u4e00-\u9fff]{2,6}(?:市)?)(?:工作|办公|上班)"),
    )
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        city = extract_city_name(match.group(1))
        if city:
            return city
    return None


def extract_city_name(raw: str) -> str | None:
    """从可能含杂质的片段中识别城市名（不含「市」后缀）。"""
    text = (raw or "").strip()
    if not text:
        return None
    text = _JUNK_CITY_PREFIX.sub("", text)
    text = text.strip("，,。；; \t")
    if not text:
        return None

    for city in sorted(_KNOWN_CITIES, key=len, reverse=True):
        core = strip_city_suffix(city)
        if core in text or f"{core}市" in text:
            return core

    match = re.search(r"([\u4e00-\u9fff]{2,6})市?", text)
    if not match:
        return None
    candidate = match.group(1)
    if candidate in ("地是", "城市", "驻地", "办公", "工作", "常驻地"):
        return None
    return candidate


def standardize_city_name(city: str) -> str:
    """将城市名规范为存储格式，如 北京 → 北京市。"""
    core = strip_city_suffix((city or "").strip())
    if not core:
        return ""
    if core in _CITY_NO_SHI_SUFFIX:
        return core
    if (city or "").endswith("区") or (city or "").endswith("县"):
        return city.strip()
    return f"{core}市"


def normalize_base_location(raw: str) -> str:
    """标准化常驻地：先识别城市，再补全「市」。"""
    city = extract_city_name(raw)
    if not city:
        return ""
    return standardize_city_name(city)


def _clean_project_hint(name: str) -> str:
    text = (name or "").strip("，,。；; \t和与及 ")
    text = _PROJECT_PREFIX.sub("", text)
    return text.strip("，,。；; \t和与及 ")


def extract_project_hints_from_text(text: str) -> list[str]:
    """从用户消息抽取项目简称/别名（如 宁煤项目、神东项目）。"""
    if not text.strip():
        return []

    hints: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        hint = _clean_project_hint(raw)
        if not hint or hint in seen:
            return
        if len(hint) < 2:
            return
        seen.add(hint)
        hints.append(hint)

    responsible = _RESPONSIBLE_SEGMENT.search(text)
    if responsible:
        segment = responsible.group(1)
        for part in _SPLIT_CONJUNCTION.split(segment):
            part = part.strip()
            if not part:
                continue
            for match in _PROJECT_SUFFIX.finditer(part):
                add(match.group(1))

    for match in _PROJECT_SUFFIX.finditer(text):
        add(match.group(1))

    return hints


def _split_aliases(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.replace("，", ",").split(",") if part.strip()]


def _score_project_match(hint: str, candidate: str) -> int:
    hint_core = re.sub(r"(?:项目|工程)$", "", hint)
    cand_core = re.sub(r"(?:项目|工程)$", "", candidate)
    if hint == candidate:
        return len(candidate) + 200
    if hint_core and hint_core == cand_core:
        return len(candidate) + 150
    if candidate in hint or hint in candidate:
        return len(candidate) + (120 if candidate in hint else 80)
    if hint_core and (hint_core in candidate or cand_core in hint):
        return len(candidate) + 60
    return 0


def resolve_project_hint(
    hint: str, mappings: list[_ProjectMappingLike]
) -> str | None:
    """将项目简称/别名解析为映射表中的标准项目名称。"""
    hint = _clean_project_hint(hint)
    if not hint:
        return None
    best_score = 0
    best_name: str | None = None
    for record in mappings:
        candidates = [record.project_name, *_split_aliases(record.aliases)]
        for name in candidates:
            if not name:
                continue
            score = _score_project_match(hint, name)
            if score > best_score:
                best_score = score
                best_name = record.project_name
    return best_name if best_score >= 60 else None


def resolve_projects_from_text(
    text: str, mappings: list[_ProjectMappingLike]
) -> list[str]:
    """结合抽取与映射表，返回标准项目名称列表（去重、保序）。"""
    resolved: list[str] = []
    seen: set[str] = set()

    def append(name: str) -> None:
        if name and name not in seen:
            seen.add(name)
            resolved.append(name)

    for hint in extract_project_hints_from_text(text):
        name = resolve_project_hint(hint, mappings)
        append(name or hint)

    if mappings:
        candidates: list[tuple[int, str, str]] = []
        for record in mappings:
            for name in [record.project_name, *_split_aliases(record.aliases)]:
                if name and name in text:
                    candidates.append((len(name), record.project_name, name))
        for _, project_name, _ in sorted(candidates, key=lambda item: item[0], reverse=True):
            append(project_name)

    return resolved[:20]


def normalize_related_projects(
    projects: list[str],
    mappings: list[_ProjectMappingLike],
    *,
    source_text: str = "",
) -> list[str]:
    """将关联项目列表规范为标准全称；无法映射时丢弃明显非项目片段。"""
    normalized: list[str] = []
    seen: set[str] = set()

    seeds = list(projects)
    if source_text.strip():
        seeds.extend(extract_project_hints_from_text(source_text))

    for item in seeds:
        hint = _clean_project_hint(str(item))
        if not hint:
            continue
        if re.search(r"^(我负责|负责|和|与|及|以及)$", hint):
            continue
        name = resolve_project_hint(hint, mappings)
        final = name or (hint if _PROJECT_SUFFIX.search(hint) else None)
        if not final:
            continue
        if final not in seen:
            seen.add(final)
            normalized.append(final)

    return normalized[:20]


def normalize_structured_fields(
    structured: dict[str, Any],
    mappings: list[_ProjectMappingLike],
    *,
    source_text: str = "",
) -> dict[str, Any]:
    """标准化长期记忆结构化字段（保存/展示前调用）。"""
    data = dict(structured)
    base = str(data.get("base_location") or "").strip()
    if base:
        data["base_location"] = normalize_base_location(base)

    projects = list(data.get("related_projects") or [])
    if projects or source_text.strip():
        data["related_projects"] = normalize_related_projects(
            projects, mappings, source_text=source_text
        )
    return data
