"""确认卡片与用户补充文字合并。

字段冲突时的优先级（同一字段）：
1. 对话历史解析出的基础值
2. 本次输入框（文本框）补充文字解析出的更新
3. 确认卡片上用户填写/点选的值 —— **最终以卡片非空字段为准**
"""

from __future__ import annotations

from typing import Any

from src.agent.memory_extractor import extract_structured_updates, merge_structured


def merge_card_structured(base: dict[str, Any], card: dict[str, Any] | None) -> dict[str, Any]:
    """卡片上用户填写/点选的内容覆盖同名字段（非空才覆盖；冲突时以卡片为准）。"""
    if not card:
        return dict(base)
    merged = dict(base)
    for key, value in card.items():
        if key.startswith("_"):
            continue
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, list) and not value:
            continue
        if key == "gender" and str(value).strip() in ("", "unknown"):
            continue
        merged[key] = value
    return merged


def apply_supplementary_to_structured(structured: dict[str, Any], text: str) -> dict[str, Any]:
    """从输入框补充文字抽取字段并合并到基础结构化数据（后续仍会被卡片覆盖）。"""
    if not (text or "").strip():
        return dict(structured)
    updates = extract_structured_updates(text)
    if not updates:
        return dict(structured)
    return merge_structured(structured, updates)


def merge_confirmed_structured(
    base: dict[str, Any],
    card: dict[str, Any] | None,
    *,
    supplementary_text: str = "",
) -> dict[str, Any]:
    """信息收集确认：对话解析 + 输入框补充 + 卡片填写，三者合并（卡片非空字段优先）。"""
    merged = dict(base)
    if supplementary_text.strip():
        merged = apply_supplementary_to_structured(merged, supplementary_text)
    if card:
        merged = merge_card_structured(merged, card)
    return merged
