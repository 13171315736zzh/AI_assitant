"""会议室查询接口（演示用，可替换为国能会议真实 API）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta


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

    def to_public_dict(self) -> dict:
        return {
            "requested_room": self.requested_room,
            "time_label": self.time_label,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "available": self.available,
            "conflict_reason": self.conflict_reason,
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
    "403": ("4F", 20, "大型会议/投影"),
}


def _resolve_meeting_date(hint: str | None) -> date:
    today = date.today()
    if hint and "明天" in hint:
        return today + timedelta(days=1)
    if hint and "后天" in hint:
        return today + timedelta(days=2)
    if hint and "周四" in hint:
        weekday = today.weekday()
        delta = (3 - weekday) % 7 or 7
        return today + timedelta(days=delta)
    return today + timedelta(days=1)


def _parse_time_range(start_hint: str | None, end_hint: str | None) -> tuple[str, str, str]:
    start = start_hint or "14:00"
    end = end_hint or "16:00"
    if "下午" in (start_hint or "") and ":" not in start:
        start = "14:00"
    if "上午" in (start_hint or "") and ":" not in start:
        start = "09:00"
    label = f"{start}-{end}"
    return start, end, label


async def query_room_availability(
    room: str,
    *,
    date_hint: str | None = None,
    start_hint: str | None = None,
    end_hint: str | None = None,
) -> RoomAvailabilityResult:
    meeting_date = _resolve_meeting_date(date_hint)
    start, end, time_label = _parse_time_range(start_hint, end_hint)
    start_dt = f"{meeting_date.isoformat()} {start}"
    end_dt = f"{meeting_date.isoformat()} {end}"
    full_time_label = f"{meeting_date.isoformat()} {time_label}"

    busy_hours = _BUSY_ROOMS.get(room, ())
    hour_keys = [h for h in busy_hours if h >= start[:5] or start[:2] >= "13"]
    conflict = bool(hour_keys) and room in _BUSY_ROOMS

    conflict_reason = None
    if conflict:
        conflict_reason = (
            f"{room} 会议室在 {full_time_label} 已被「项目进度评审会」预定，"
            f"该时段暂不可用"
        )

    alternatives: list[RoomOption] = []
    for alt_room, (floor, cap, equip) in _ROOM_CATALOG.items():
        if alt_room == room:
            continue
        alt_busy = alt_room in _BUSY_ROOMS and any(
            h >= start[:5] for h in _BUSY_ROOMS.get(alt_room, ())
        )
        if alt_busy and alt_room != "235":
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

    # 优先推荐相邻 235
    alternatives.sort(key=lambda r: (0 if r.room == "235" else 1, r.room))

    return RoomAvailabilityResult(
        requested_room=room,
        time_label=full_time_label,
        start_time=start_dt,
        end_time=end_dt,
        available=not conflict,
        conflict_reason=conflict_reason,
        alternatives=alternatives[:3],
    )
