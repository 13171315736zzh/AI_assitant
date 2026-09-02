"""差旅细则：行程解析、规则匹配、主动建议与提醒。"""

from __future__ import annotations

import re

from src.agent.policy_context import trim_excerpt
from src.agent.travel_policy_knowledge import (
    ARTICLE_BY_ID,
    POLICY_ARTICLES,
    POLICY_FILENAME,
    accommodation_standard_other,
    build_policy_knowledge_summary,
    estimate_train_hours,
    normalize_city,
)

_CN_NUM = {"一": 1, "二": 2, "两": 2, "俩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

_KNOWN_CITIES = sorted(
    {
        "北京", "上海", "天津", "重庆", "呼和浩特", "鄂尔多斯", "海拉尔", "包头", "赤峰",
        "南昌", "武汉", "广州", "深圳", "杭州", "南京", "成都", "西安", "郑州", "济南",
        "青岛", "长沙", "合肥", "福州", "厦门", "沈阳", "大连", "哈尔滨", "长春", "太原",
        "石家庄", "南宁", "昆明", "贵阳", "兰州", "西宁", "银川", "乌鲁木齐", "拉萨", "海口",
        "神东", "宁波", "珠海", "汕头", "苏州", "无锡", "雁宝", "燕宝",
    },
    key=len,
    reverse=True,
)


class TravelContext:
    __slots__ = (
        "raw_text",
        "trip_days",
        "origin",
        "destination",
        "train_hours",
        "mentions_split",
        "mentions_reimburse",
        "mentions_basic_ops",
        "mentions_train",
        "mentions_flight",
        "mentions_meeting",
        "mentions_training",
        "staff_level",
    )

    def __init__(self, raw_text: str) -> None:
        self.raw_text = raw_text
        self.trip_days: int | None = None
        self.origin: str | None = None
        self.destination: str | None = None
        self.train_hours: float | None = None
        self.mentions_split = False
        self.mentions_reimburse = False
        self.mentions_basic_ops = False
        self.mentions_train = False
        self.mentions_flight = False
        self.mentions_meeting = False
        self.mentions_training = False
        self.staff_level: str | None = None


class PolicyReminder:
    __slots__ = ("rule_id", "title", "message", "clause", "excerpt", "priority")

    def __init__(
        self,
        rule_id: str,
        title: str,
        message: str,
        clause: str,
        excerpt: str,
        priority: int = 50,
    ) -> None:
        self.rule_id = rule_id
        self.title = title
        self.message = message
        self.clause = clause
        self.excerpt = excerpt
        self.priority = priority


_DISCOVER_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), rule_id)
    for pattern, rule_id in (
        (r"连续乘车\s*6\s*小时", "train_soft_seat_6h"),
        (r"超过\s*7\s*天[\s\S]{0,40}?包干", "lump_sum_mandatory"),
        (r"7\s*天\s*[（(]\s*含\s*7\s*天\s*[）)][\s\S]{0,40}?包干", "lump_sum_optional"),
        (r"拆分[\s\S]{0,20}?规避[\s\S]{0,20}?包干", "no_split_trips"),
        (r"连续出差\s*30\s*天", "long_trip_30d"),
        (r"事前审批|事先报经[\s\S]{0,12}?批准", "pre_approval"),
        (r"3\s*个?\s*月内报销", "reimburse_deadline"),
        (r"国能商旅平台", "platform_booking"),
        (r"每人每天\s*100\s*元包干", "meal_traffic_allowance"),
    )
)


def _parse_cn_number(token: str) -> int | None:
    token = token.strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if token in _CN_NUM:
        return _CN_NUM[token]
    if token.startswith("十"):
        rest = token[1:]
        return 10 + (_CN_NUM.get(rest, 0) if rest else 0)
    if "十" in token:
        parts = token.split("十", 1)
        tens = _CN_NUM.get(parts[0], 0) if parts[0] else 1
        ones = _CN_NUM.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    return None


def extract_trip_days(text: str) -> int | None:
    if not text:
        return None
    normalized = text.replace("个", "")
    explicit_over = re.search(r"(?:超过|大于|多于|不低于)\s*(\d+)\s*天", normalized)
    if explicit_over:
        return int(explicit_over.group(1)) + 1
    for pattern in (
        r"(\d+)\s*天",
        r"([两二三四五六七八九十\d]+)\s*天",
        r"([两二三四五六七八九十\d]+)\s*周",
        r"([两二三四五六七八九十\d]+)\s*个?\s*月",
    ):
        for match in re.finditer(pattern, normalized):
            token = match.group(1)
            if "月" in match.group(0):
                num = _parse_cn_number(token) or (int(token) if token.isdigit() else None)
                if num:
                    return num * 30
            elif "周" in match.group(0):
                num = _parse_cn_number(token) or (int(token) if token.isdigit() else None)
                if num:
                    return num * 7
            elif token.isdigit():
                return int(token)
            else:
                num = _parse_cn_number(token)
                if num:
                    return num
    if re.search(r"半\s*个?\s*月", normalized):
        return 15
    if re.search(r"一\s*个?\s*月|1\s*个?\s*月", normalized):
        return 30
    return None


def _find_city(text: str) -> str | None:
    for city in _KNOWN_CITIES:
        if city in text:
            return city
    return None


def _is_valid_city(name: str | None) -> bool:
    if not name:
        return False
    if re.match(r"^(明天|今天|后天|下周|我要|请帮|帮|请|相关)", name):
        return False
    return name in _KNOWN_CITIES


def _extract_route(text: str) -> tuple[str | None, str | None]:
    patterns = (
        r"从\s*([\u4e00-\u9fff]{2,6}?)\s*(?:到|去|至|往)\s*([\u4e00-\u9fff]{2,6}?)(?:出差|办事|培训|会议|项目|$|[，,。！？\s])",
        r"去\s*([\u4e00-\u9fff]{2,6})(?:出差|办事|培训|会议|项目|[，,。！？\s]|$)",
        r"([\u4e00-\u9fff]{2,6}?)\s*(?:到|去|至|往)\s*([\u4e00-\u9fff]{2,6}?)(?:出差|办事|培训|会议|项目)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        if match.lastindex == 1:
            dest = normalize_city(match.group(1))
            origin = "北京" if re.search(r"返回\s*北京|回\s*北京", text) else None
            if dest and _is_valid_city(dest):
                return origin, dest
            continue
        origin = normalize_city(match.group(1))
        dest = normalize_city(match.group(2))
        if _is_valid_city(origin) and _is_valid_city(dest) and origin != dest:
            return origin, dest
    origin = None
    dest = None
    if re.search(r"返回\s*北京|回\s*北京", text):
        origin = "北京"
    go_match = re.search(r"去\s*([\u4e00-\u9fff]{2,6})", text)
    if go_match:
        candidate = normalize_city(go_match.group(1))
        if _is_valid_city(candidate):
            dest = candidate
    if origin and dest:
        return origin, dest
    cities_found: list[str] = []
    for city in _KNOWN_CITIES:
        if city in text:
            cities_found.append(city)
    if len(cities_found) >= 2:
        a, b = normalize_city(cities_found[0]), normalize_city(cities_found[1])
        if re.search(r"返回\s*北京|回\s*北京", text) and "北京" in cities_found:
            return "北京", b if b != "北京" else a
        return a, b
    if len(cities_found) == 1:
        city = normalize_city(cities_found[0])
        if re.search(r"返回\s*北京|回\s*北京", text) and city != "北京":
            return "北京", city
        return None, city
    return None, None


def parse_travel_context(text: str) -> TravelContext:
    ctx = TravelContext(text)
    ctx.trip_days = extract_trip_days(text)
    ctx.origin, ctx.destination = _extract_route(text)
    if ctx.origin and ctx.destination:
        ctx.train_hours = estimate_train_hours(ctx.origin, ctx.destination)
    ctx.mentions_split = bool(re.search(r"拆分|分段|分两?次|拆成", text))
    ctx.mentions_reimburse = "报销" in text
    ctx.mentions_basic_ops = bool(re.search(r"基础运维|运维类", text))
    ctx.mentions_train = bool(re.search(r"火车|高铁|动车|铁路|软席|硬席", text))
    ctx.mentions_flight = bool(re.search(r"飞机|航班|机票|航空", text))
    ctx.mentions_meeting = "会议" in text
    ctx.mentions_training = bool(re.search(r"培训|学习", text))
    if re.search(r"主要负责人|公司领导", text):
        ctx.staff_level = "主要负责人"
    elif re.search(r"其他负责人|部门负责人|副总", text):
        ctx.staff_level = "其他负责人"
    elif re.search(r"其他人员|普通员工|职员", text):
        ctx.staff_level = "其他人员"
    return ctx


def discover_rule_ids_from_text(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for pattern, rule_id in _DISCOVER_PATTERNS:
        if pattern.search(text) and rule_id not in found:
            found.append(rule_id)
    return found


def _add(reminders: list[PolicyReminder], rule_id: str, message: str) -> None:
    article = ARTICLE_BY_ID[rule_id]
    reminders.append(
        PolicyReminder(
            rule_id=rule_id,
            title=article["title"],
            message=message,
            clause=article["clause"],
            excerpt=article["excerpt"],
            priority=article["priority"],
        )
    )


def evaluate_travel_reminders(ctx: TravelContext) -> list[PolicyReminder]:
    reminders: list[PolicyReminder] = []
    text = ctx.raw_text
    days = ctx.trip_days

    # —— 城市间交通：第十六条 火车软席 ——
    if ctx.origin and ctx.destination and ctx.train_hours is not None:
        hours = ctx.train_hours
        route = f"{ctx.origin}→{ctx.destination}"
        if hours >= 6:
            if ctx.mentions_train or not ctx.mentions_flight:
                _add(
                    reminders,
                    "train_soft_seat_6h",
                    f"{route} 铁路行程约 {hours:g} 小时，连续乘车 6 小时及以上，可乘坐火车软席（软座、软卧、动卧）。建议优先评估火车软席方案。",
                )
            _add(
                reminders,
                "transport_standard",
                f"其他人员默认可乘坐火车硬席/高铁二等座；因 {route} 车程约 {hours:g} 小时，符合第十六条时可升级软席。",
            )
        elif ctx.mentions_train:
            _add(
                reminders,
                "transport_standard",
                f"{route} 铁路行程约 {hours:g} 小时，未达 6 小时，其他人员一般按硬席/二等座标准乘坐（第十六条）。",
            )

    # —— 目的地住宿标准 ——
    if ctx.destination:
        limit, label = accommodation_standard_other(ctx.destination)
        staff = ctx.staff_level or "其他人员"
        _add(
            reminders,
            "accommodation_limit",
            f"目的地 {ctx.destination}（{label}），{staff}住宿费限额标准为 {limit} 元/人·天（附件2）。",
        )

    # —— 包干制 ——
    if days is not None and days > 7 and not ctx.mentions_basic_ops:
        _add(
            reminders,
            "lump_sum_mandatory",
            f"本次出差约 {days} 天，超过 7 天（不含），同一地点非基础运维类项目须实行出差包干制。",
        )
        _add(
            reminders,
            "lump_sum_exception",
            "如确因特殊情况无法实行包干制，须单独说明并经部门负责人、分管领导批准。",
        )
    elif days is not None and 1 <= days <= 7:
        _add(
            reminders,
            "lump_sum_optional",
            f"本次出差约 {days} 天，在 7 天（含）以内，正式员工可选择包干制或常规报销。",
        )

    if days is not None and days >= 30:
        _add(
            reminders,
            "long_trip_30d",
            f"连续出差 {days} 天，已达 30 天及以上，可关注长期出差探亲补贴或往返交通费政策（第十八条）。",
        )

    if ctx.mentions_split and (days is None or days > 5):
        _add(reminders, "no_split_trips", "请勿拆分同一项目/地点的长差行程以规避包干制。")

    if re.search(r"出差|差旅", text) and (
        days is not None or re.search(r"安排|申请|办理|订票", text)
    ):
        _add(reminders, "pre_approval", "请先完成出差审批，申请须写明具体事由、地点及预计往返时间。")

    if re.search(r"出差|差旅", text):
        _add(
            reminders,
            "meeting_training",
            "市内交通与伙食补助按出差自然天每人每天 100 元包干；默认按未统一安排食宿处理。"
            "若实际为会议/培训且主办方统一安排食宿，按细则第二十七条执行。",
        )

    if re.search(r"订票|机票|酒店|住宿|商旅|平台|火车|高铁", text):
        _add(reminders, "platform_booking", "城市间交通与住宿原则上通过国能商旅平台预订。")

    if ctx.mentions_reimburse:
        _add(reminders, "reimburse_deadline", "出差结束后 3 个月内须报销；商旅平台订票建议两周内报销。")

    if re.search(r"绕道|顺路|省亲|回家", text):
        _add(reminders, "no_detour", "绕道、省亲等导致行程与申请不符的费用可能不予报销，请在申请中如实说明。")

    reminders.sort(key=lambda item: item.priority)
    seen: set[str] = set()
    deduped: list[PolicyReminder] = []
    for item in reminders:
        if item.rule_id in seen:
            continue
        seen.add(item.rule_id)
        deduped.append(item)
    return deduped


def build_travel_rule_snippets(ctx: TravelContext) -> str:
    if not re.search(r"出差|差旅|住宿|报销|火车|机票|酒店", ctx.raw_text):
        return ""
    lines = [build_policy_knowledge_summary()]
    insights = evaluate_travel_reminders(ctx)
    if insights:
        lines.append("\n【针对当前用户行程的分析结论（须在回复中体现）】")
        for item in insights[:8]:
            lines.append(f"- {item.message}（{item.clause}）")
    if ctx.origin and ctx.destination:
        lines.append(f"- 解析路线：{ctx.origin} → {ctx.destination}")
        if ctx.train_hours is not None:
            lines.append(f"- 估算铁路时长：约 {ctx.train_hours:g} 小时")
    if ctx.trip_days:
        lines.append(f"- 解析出差天数：约 {ctx.trip_days} 天")
    return "\n".join(lines)


def format_reminder_block(reminders: list[PolicyReminder], max_items: int = 5) -> str:
    if not reminders:
        return ""
    lines = ["【差旅建议与规定提醒】"]
    for item in reminders[:max_items]:
        lines.append(f"· {item.message}（{item.clause}）")
    return "\n".join(lines)


def reminders_to_sources(reminders: list[PolicyReminder], filename: str = POLICY_FILENAME) -> list[dict]:
    return [
        {
            "filename": filename,
            "clause": item.clause,
            "excerpt": trim_excerpt(f"{item.title}：{item.excerpt}"),
            "rule_id": item.rule_id,
        }
        for item in reminders
    ]


def apply_travel_reminders(
    user_content: str,
    assistant_content: str,
    ctx: TravelContext | None = None,
) -> tuple[str, list[PolicyReminder]]:
    ctx = ctx or parse_travel_context(user_content)
    reminders = evaluate_travel_reminders(ctx)
    if not reminders:
        return assistant_content, []

    block = format_reminder_block(reminders)
    if block.split("\n", 1)[0] in assistant_content:
        return assistant_content, reminders

    key_phrases = (
        "包干制", "软席", "6 小时", "6小时", "事前审批", "商旅平台",
        "住宿费", "元/人·天", "第十六条",
    )
    covered = sum(1 for key in key_phrases if key in assistant_content)
    critical = any(r.rule_id in ("lump_sum_mandatory", "train_soft_seat_6h", "accommodation_limit") for r in reminders)
    if covered < 2 or critical:
        assistant_content = f"{block}\n\n{assistant_content}".strip()

    return assistant_content, reminders
