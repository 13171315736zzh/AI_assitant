"""邮件撰写：称谓与礼貌用语规范。"""

from __future__ import annotations

import re

_EMAIL_KEYWORDS = ("邮件", "写信", "发信", "发邮件", "写封", "email", "收件人", "抄送", "通知")

# 职务 → 尊称后缀（用于生成「姓名+尊称」）
_TITLE_SUFFIX: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"项目经理|项目负责"), "经理"),
    (re.compile(r"部门负责人|部门经理|总监"), "经理"),
    (re.compile(r"总经理|副总|分管领导|公司领导|主要负责人"), "总"),
    (re.compile(r"主任|处长|科长"), "主任"),
    (re.compile(r"工程师|专员|职员|员工"), "同事"),
)


def is_email_context(text: str) -> bool:
    if not text:
        return False
    if any(kw in text for kw in _EMAIL_KEYWORDS):
        return True
    return bool(re.search(r"给.{1,8}(发|写|通知|告知)", text))


def infer_salutation(name: str, title_hint: str = "") -> str:
    """根据姓名与职务提示生成标准称谓，如「赵士廷经理，您好」。"""
    name = name.strip()
    if not name:
        return "您好"
    combined = title_hint or ""
    for pattern, suffix in _TITLE_SUFFIX:
        if pattern.search(combined):
            if suffix == "总" and not name.endswith("总"):
                return f"{name}{suffix}，您好"
            if suffix in ("经理", "主任", "同事") and not name.endswith(suffix):
                return f"{name}{suffix}，您好"
            break
    if re.search(r"经理|负责", combined):
        return f"{name}经理，您好" if not name.endswith("经理") else f"{name}，您好"
    if re.search(r"总|领导|负责人", combined):
        return f"{name}总，您好" if not name.endswith("总") else f"{name}，您好"
    return f"{name}您好"


def build_email_writing_snippets(text: str) -> str:
    if not is_email_context(text):
        return ""

    hints: list[str] = []
    name = ""
    title_hint = ""
    pm_match = re.search(r"项目经理\s*([\u4e00-\u9fff]{2,4})", text)
    if pm_match:
        name, title_hint = pm_match.group(1), "项目经理"
    else:
        name_match = re.search(
            r"(?:给|通知|告知|发给|写给)\s*([\u4e00-\u9fff]{2,4})(?:（|\(|，|,|\s|$)",
            text,
        )
        title_match = re.search(r"项目经理|部门经理|负责人|总监|主任|领导|经理", text)
        if name_match:
            name = name_match.group(1)
            title_hint = title_match.group(0) if title_match else ""
    if name:
        salutation = infer_salutation(name, title_hint)
        hints.append(f"- 本邮件开头称谓建议：「{salutation}」")

    lines = [
        "\n【邮件撰写规范（生成或展示邮件正文时必须遵守）】",
        "- 称谓务必客气、尊敬：已知对方姓名和职务时，开头用「姓名+职务/尊称+，您好」",
        "  · 项目经理 →「赵士廷经理，您好」（勿写「赵士廷，你好」或直呼姓名）",
        "  · 部门/公司领导 →「李总，您好」「王经理，您好」",
        "  · 不确定职务时可「XX老师，您好」或「XX您好」，但仍须礼貌",
        "- 正文全程保持谦逊得体：多用「请」「烦请」「感谢」「如有不便敬请谅解」",
        "- 说明事由条理清晰；涉及请求时用「恳请」「麻烦您」而非命令式语气",
        "- 结尾使用敬语，如「此致\\n敬礼」「谢谢！顺祝工作顺利」",
        "- 输出完整邮件时须包含：称谓、正文、结尾敬语；语气正式但不生硬",
    ]
    lines.extend(hints)
    return "\n".join(lines)
