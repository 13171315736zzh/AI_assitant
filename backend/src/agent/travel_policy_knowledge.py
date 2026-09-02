"""《差旅费管理实施细则》结构化知识：城市标准、路线时长、条款原文。"""

from __future__ import annotations

# 附件2：其他城市人员（其他人员）住宿费限额 元/人·天（省会/直辖市）
_CITY_ACCOMMODATION_OTHER: dict[str, int] = {
    "北京": 700,
    "上海": 700,
    "天津": 700,
    "重庆": 700,
    "石家庄": 700,
    "太原": 700,
    "呼和浩特": 700,
    "沈阳": 700,
    "大连": 700,
    "长春": 700,
    "哈尔滨": 700,
    "南京": 700,
    "杭州": 700,
    "宁波": 700,
    "合肥": 700,
    "福州": 700,
    "厦门": 700,
    "南昌": 700,
    "济南": 700,
    "青岛": 700,
    "郑州": 700,
    "武汉": 700,
    "长沙": 700,
    "广州": 700,
    "深圳": 700,
    "珠海": 700,
    "汕头": 700,
    "南宁": 700,
    "海口": 700,
    "成都": 700,
    "贵阳": 700,
    "昆明": 700,
    "拉萨": 700,
    "西安": 700,
    "兰州": 700,
    "西宁": 700,
    "银川": 700,
    "乌鲁木齐": 700,
}

# 省内「其他城市」其他人员一般为 500（细则附件2）
_PROVINCE_OTHER_CITY_ACCOMMODATION = 500

# 城市 → 所属省份（用于判断「其他城市」）
_CITY_PROVINCE: dict[str, str] = {
    "鄂尔多斯": "内蒙古",
    "海拉尔": "内蒙古",
    "包头": "内蒙古",
    "赤峰": "内蒙古",
    "神东": "内蒙古",
    "苏州": "江苏",
    "无锡": "江苏",
    "珠海": "广东",
}

# 常见城市间铁路运行时长（小时，含高铁/普速典型值，用于第十六条判断）
_ROUTE_TRAIN_HOURS: dict[frozenset[str], float] = {
    frozenset({"北京", "南昌"}): 6.5,
    frozenset({"北京", "上海"}): 4.5,
    frozenset({"北京", "广州"}): 8.0,
    frozenset({"北京", "深圳"}): 8.5,
    frozenset({"北京", "武汉"}): 4.5,
    frozenset({"北京", "西安"}): 4.5,
    frozenset({"北京", "成都"}): 8.0,
    frozenset({"北京", "哈尔滨"}): 5.5,
    frozenset({"北京", "呼和浩特"}): 2.5,
    frozenset({"北京", "天津"}): 0.5,
    frozenset({"北京", "石家庄"}): 1.5,
    frozenset({"北京", "郑州"}): 3.5,
    frozenset({"北京", "济南"}): 2.0,
    frozenset({"北京", "沈阳"}): 4.5,
    frozenset({"北京", "乌鲁木齐"}): 30.0,
    frozenset({"上海", "南昌"}): 4.0,
    frozenset({"上海", "广州"}): 7.0,
    frozenset({"上海", "深圳"}): 7.5,
    frozenset({"上海", "武汉"}): 4.0,
    frozenset({"上海", "成都"}): 11.0,
    frozenset({"广州", "南昌"}): 4.5,
    frozenset({"广州", "武汉"}): 4.0,
}

# 跨省省会默认按 >=6 小时估算（保守，便于提醒用户确认）
_CROSS_PROVINCE_CAPITAL_DEFAULT_HOURS = 6.5

# 细则条款库（供提醒与 LLM 注入）
POLICY_ARTICLES: tuple[dict, ...] = (
    {
        "id": "pre_approval",
        "clause": "第四条、第九条",
        "title": "事前审批",
        "excerpt": "因公出差须事先审批；申请须写明事由、地点、预计往返时间，不得仅写「出差」。",
        "priority": 40,
    },
    {
        "id": "itinerary_change",
        "clause": "第十一条",
        "title": "行程变更",
        "excerpt": "工作任务变动导致行程变更的，应及时修改出差申请，注明原因并经部门负责人审批。",
        "priority": 45,
    },
    {
        "id": "transport_standard",
        "clause": "第十三条、附件1",
        "title": "交通工具等级",
        "excerpt": "其他人员默认：飞机经济舱、火车硬席/高铁动车二等座；超过规定等级须总经理审批（第三十七条）。",
        "priority": 35,
    },
    {
        "id": "train_soft_seat_6h",
        "clause": "第十六条",
        "title": "火车软席（6小时及以上）",
        "excerpt": "出差人员连续乘车 6 小时及以上的，可乘坐火车软席（软座、软卧、动卧）。",
        "priority": 25,
    },
    {
        "id": "platform_booking",
        "clause": "第十四条、第三十六条",
        "title": "商旅平台预订",
        "excerpt": "乘坐飞机、火车、轮船等原则上通过国能商旅平台预订；报销须提供合规票据及审批单。",
        "priority": 55,
    },
    {
        "id": "long_trip_30d",
        "clause": "第十八条",
        "title": "长期出差30天及以上",
        "excerpt": "正式员工在常驻地外连续出差30天（含）以上，可发放长期出差探亲补贴或报销一次往返城市间交通费。",
        "priority": 28,
    },
    {
        "id": "accommodation_limit",
        "clause": "第二十条、附件2",
        "title": "住宿费限额",
        "excerpt": "须在职务对应住宿费限额内住宿；国内标准见附件2，旺季部分城市上浮20%。",
        "priority": 32,
    },
    {
        "id": "meal_traffic_allowance",
        "clause": "第二十三条、第二十四条",
        "title": "市内交通与伙食补助",
        "excerpt": "市内交通费、伙食补助均按出差自然（日历）天数计算，每人每天 100 元包干使用。",
        "priority": 70,
    },
    {
        "id": "lump_sum_mandatory",
        "clause": "第二十九条、第三十条",
        "title": "出差包干制（超过7天）",
        "excerpt": "同一地点超过7天（不含）的非基础运维类项目出差，须对住宿费、市内交通费、伙食补助实行包干结算。",
        "priority": 10,
    },
    {
        "id": "lump_sum_optional",
        "clause": "第三十二条",
        "title": "7天以内可选包干",
        "excerpt": "7天（含）以内出差，正式员工可选择包干制或按常规标准报销。",
        "priority": 30,
    },
    {
        "id": "lump_sum_exception",
        "clause": "第三十三条",
        "title": "无法包干须审批",
        "excerpt": "7天以上无法实行包干制的，须单独说明并经部门负责人、分管领导批准。",
        "priority": 20,
    },
    {
        "id": "no_split_trips",
        "clause": "第三十四条",
        "title": "禁止拆分规避包干",
        "excerpt": "同一人员同一项目或地点不得拆分行程规避包干制。",
        "priority": 15,
    },
    {
        "id": "meeting_training",
        "clause": "第二十七条",
        "title": "会议培训食宿",
        "excerpt": "未统一安排食宿时按常规补助；统一安排食宿的会议/培训，会议期间市内交通和伙食补助按每天100元；培训期间不报销市内交通和伙食补助。",
        "priority": 50,
    },
    {
        "id": "reimburse_deadline",
        "clause": "第四十一条",
        "title": "报销时限",
        "excerpt": "出差结束后3个月内报销；商旅平台订票建议两周内报销。",
        "priority": 60,
    },
    {
        "id": "no_detour",
        "clause": "第四十条",
        "title": "绕道与行程不符",
        "excerpt": "绕道、省亲等导致行程与申请不符的，多产生的费用不予报销或自理。",
        "priority": 65,
    },
)

ARTICLE_BY_ID = {item["id"]: item for item in POLICY_ARTICLES}

POLICY_FILENAME = "国能数智科技开发（北京）有限公司差旅费管理实施细则（试行）.pdf"


def normalize_city(name: str) -> str:
    return name.replace("市", "").strip()


def estimate_train_hours(origin: str, destination: str) -> float | None:
    a, b = normalize_city(origin), normalize_city(destination)
    if a == b:
        return 0.0
    key = frozenset({a, b})
    if key in _ROUTE_TRAIN_HOURS:
        return _ROUTE_TRAIN_HOURS[key]
    if a in _CITY_ACCOMMODATION_OTHER and b in _CITY_ACCOMMODATION_OTHER and a != b:
        return _CROSS_PROVINCE_CAPITAL_DEFAULT_HOURS
    return None


def accommodation_standard_other(city: str) -> tuple[int, str]:
    """返回 (限额, 说明)。"""
    city = normalize_city(city)
    if city in _CITY_ACCOMMODATION_OTHER:
        return _CITY_ACCOMMODATION_OTHER[city], f"{city}（省会/直辖市）"
    province = _CITY_PROVINCE.get(city)
    if province:
        return _PROVINCE_OTHER_CITY_ACCOMMODATION, f"{province}其他城市"
    if city in ("海拉尔", "鄂尔多斯", "包头", "赤峰", "神东"):
        return _PROVINCE_OTHER_CITY_ACCOMMODATION, "内蒙古其他城市"
    return _PROVINCE_OTHER_CITY_ACCOMMODATION, "一般城市"


def build_policy_knowledge_summary() -> str:
    lines = ["【差旅细则核心条款（须结合用户行程主动分析并给出建议）】"]
    for item in POLICY_ARTICLES:
        lines.append(f"- {item['title']}（{item['clause']}）：{item['excerpt']}")
    lines.append(
        "- 分析用户行程时须推断：是否适用第十六条火车软席、目的地住宿费限额、是否触发包干制、是否须事前审批等"
    )
    return "\n".join(lines)
