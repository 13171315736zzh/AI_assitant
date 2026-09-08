"""会议室查询接口（演示用，可替换为国能会议真实 API）。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta


@dataclass
class RoomOption:
    room: str
    floor: str
    capacity: int
    equipment: str
    available: bool
    conflict_reason: str | None = None

    def to_public_dict(self) -> dict:
        return asdict(self)


@dataclass
class RoomAvailabilityResult:
    requested_room: str
    time_label: str
    start_time: str
    end_time: str
    available: bool
    conflict_reason: str | None
    alternatives: list[RoomOption]
    browse_mode: bool = False

    def to_public_dict(self) -> dict:
        return {
            "requested_room": self.requested_room,
            "time_label": self.time_label,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "available": self.available,
            "conflict_reason": self.conflict_reason,
            "browse_mode": self.browse_mode,
            "alternatives": [r.to_public_dict() for r in self.alternatives],
        }


# 演示：236 下午时段常被占用
_BUSY_ROOMS: dict[str, tuple[str, ...]] = {
    "236": ("14:00", "15:00", "16:00", "17:00"),
    "403": ("09:00", "10:00", "11:00"),
}

_ROOM_CATALOG: dict[str, tuple[str, int, str]] = {
    "235": ("2F", 14, "投影/视频会议"),
    "236": ("2F", 12, "投影/白板"),
    "238": ("2F", 10, "视频会议"),
    "240": ("2F", 16, "投影/大屏"),
    "403": ("4F", 20, "大型会议/投影"),
}


def list_room_presets() -> list[dict[str, str | int]]:
    """常用会议室备选项，供确认卡片点选。"""
    return [
        {
            "room": room,
            "label": f"{room} 会议室",
            "floor": floor,
            "capacity": capacity,
            "equipment": equipment,
        }
        for room, (floor, capacity, equipment) in _ROOM_CATALOG.items()
    ]


def _resolve_meeting_date(hint: str | None, raw_text: str = "") -> date:
    today = date.today()
    combined = raw_text or ""
    if hint and ("今天" in hint or "今晚" in hint):
        return today
    if hint and "明天" in hint:
        return today + timedelta(days=1)
    if hint and "后天" in hint:
        return today + timedelta(days=2)
    if hint and "周四" in hint:
        weekday = today.weekday()
        delta = (3 - weekday) % 7 or 7
        return today + timedelta(days=delta)
    if re.search(r"今晚|今天|今日|今天晚上", combined):
        return today
    if hint and "明天" in hint:
        return today + timedelta(days=1)
    return today


def _parse_time_range(
    start_hint: str | None,
    end_hint: str | None,
    *,
    default_start: str = "14:00",
    default_end: str | None = None,
) -> tuple[str, str, str]:
    start = start_hint or default_start
    end = end_hint or default_end or _add_one_hour(start)
    if "下午" in (start_hint or "") and ":" not in start:
        start = "14:00"
    if "上午" in (start_hint or "") and ":" not in start:
        start = "09:00"
    if len(start) == 5:
        start_full = f"{start}:00"
    else:
        start_full = start
    if len(end) == 5:
        end_full = f"{end}:00"
    else:
        end_full = end
    label = f"{start[:5]}-{end[:5]}"
    return start_full, end_full, label


def _add_one_hour(start: str) -> str:
    base = start[:5]
    hour, minute = [int(part) for part in base.split(":", 1)]
    end_hour = min(hour + 1, 23)
    end_minute = 59 if end_hour == 23 and hour + 1 >= 24 else minute
    return f"{end_hour:02d}:{end_minute:02d}:00"


def _is_room_available(room: str, start: str, end: str) -> bool:
    if room not in _BUSY_ROOMS:
        return True
    start_key = start[:5]
    end_key = end[:5]
    for hour in _BUSY_ROOMS[room]:
        if start_key <= hour < end_key:
            return False
    return True


def _build_schedule(
    *,
    date_hint: str | None = None,
    start_hint: str | None = None,
    end_hint: str | None = None,
    raw_text: str = "",
) -> tuple[str, str, str, str]:
    meeting_date = _resolve_meeting_date(date_hint, raw_text)
    start, end, time_part = _parse_time_range(start_hint, end_hint)
    full_time_label = f"{meeting_date.isoformat()} {time_part}"
    start_dt = f"{meeting_date.isoformat()} {start[:8] if len(start) > 5 else start}"
    end_dt = f"{meeting_date.isoformat()} {end[:8] if len(end) > 5 else end}"
    if len(start_dt.split()[-1]) == 5:
        start_dt = f"{start_dt}:00"
    if len(end_dt.split()[-1]) == 5:
        end_dt = f"{end_dt}:00"
    return full_time_label, start_dt, end_dt, start


def _match_equipment(equipment: str, pref: str | None) -> bool:
    if not pref:
        return True
    return pref in equipment


def _collect_alternatives(
    *,
    exclude_room: str | None,
    start: str,
    end: str,
    equipment_pref: str | None = None,
    min_capacity: int | None = None,
    limit: int = 3,
) -> list[RoomOption]:
    alternatives: list[RoomOption] = []
    for alt_room, (floor, cap, equip) in _ROOM_CATALOG.items():
        if alt_room == exclude_room:
            continue
        if min_capacity and cap < min_capacity:
            continue
        if not _match_equipment(equip, equipment_pref):
            continue
        if not _is_room_available(alt_room, start, end):
            continue
        alternatives.append(
            RoomOption(
                room=alt_room,
                floor=floor,
                capacity=cap,
                equipment=equip,
                available=True,
            )
        )
    if min_capacity:
        alternatives.sort(key=lambda r: (r.capacity, r.room))
    else:
        alternatives.sort(key=lambda r: (0 if r.room == "235" else 1, r.room))
    return alternatives[:limit]


async def query_available_projection_rooms(
    *,
    date_hint: str | None = None,
    start_hint: str | None = None,
    end_hint: str | None = None,
    equipment_pref: str | None = "投影",
    raw_text: str = "",
) -> RoomAvailabilityResult:
    full_time_label, start_dt, end_dt, start = _build_schedule(
        date_hint=date_hint,
        start_hint=start_hint,
        end_hint=end_hint,
        raw_text=raw_text,
    )
    alternatives = _collect_alternatives(
        exclude_room=None,
        start=start,
        end=end_dt,
        equipment_pref=equipment_pref,
        limit=5,
    )
    preferred = ("235", "236", "240")
    prioritized = [room for room in alternatives if room.room in preferred]
    if prioritized:
        alternatives = prioritized[:3]
    else:
        alternatives = alternatives[:3]
    return RoomAvailabilityResult(
        requested_room="",
        time_label=full_time_label,
        start_time=start_dt,
        end_time=end_dt,
        available=False,
        conflict_reason=None,
        alternatives=alternatives,
        browse_mode=True,
    )


async def query_room_availability(
    room: str,
    *,
    date_hint: str | None = None,
    start_hint: str | None = None,
    end_hint: str | None = None,
    raw_text: str = "",
) -> RoomAvailabilityResult:
    full_time_label, start_dt, end_dt, start = _build_schedule(
        date_hint=date_hint,
        start_hint=start_hint,
        end_hint=end_hint,
        raw_text=raw_text,
    )

    available = _is_room_available(room, start, end_dt)
    conflict_reason = None
    if not available:
        conflict_reason = (
            f"{room} 会议室在 {full_time_label} 已被「项目进度评审会」预定，"
            f"该时段暂不可用"
        )

    alternatives = _collect_alternatives(
        exclude_room=room,
        start=start,
        end=end_dt,
        equipment_pref=None,
        limit=3,
    )

    return RoomAvailabilityResult(
        requested_room=room,
        time_label=full_time_label,
        start_time=start_dt,
        end_time=end_dt,
        available=available,
        conflict_reason=conflict_reason,
        alternatives=alternatives,
    )


def generate_gn_meeting_credentials(task_id: str, subject: str | None = None) -> dict[str, str]:
    """演示：生成国能会议链接与入会密码。"""
    digest = hashlib.sha256(f"{task_id}:{subject or ''}".encode()).hexdigest()
    meeting_no = str(int(digest[:8], 16) % 900000000 + 100000000)
    password = digest[8:14]
    return {
        "meeting_no": meeting_no,
        "meeting_link": f"https://gnmeeting.ceic.com/j/{meeting_no}",
        "meeting_password": password,
        "subject": subject or "国能会议",
    }
