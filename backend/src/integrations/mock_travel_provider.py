"""第三方航班/酒店查询接口（演示用，可替换为国能商旅真实 API）。"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

PROVIDER_NAME = "mock_travel_api_v1"

_CITY_AIRPORT: dict[str, str] = {
    "北京": "首都/大兴",
    "上海": "浦东/虹桥",
    "广州": "白云",
    "深圳": "宝安",
    "鄂尔多斯": "伊金霍洛",
    "南昌": "昌北",
    "呼和浩特": "白塔",
    "海拉尔": "东山",
}

_CITY_HOTEL_PREFIX: dict[str, str] = {
    "广州": "广州天河",
    "北京": "北京朝阳",
    "鄂尔多斯": "鄂尔多斯东胜",
    "南昌": "南昌红谷滩",
    "雁宝": "雁宝",
    "燕宝": "雁宝",
    "海拉尔": "海拉尔",
}


@dataclass
class FlightOption:
    flight_no: str
    airline: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    cabin: str
    price: int
    provider: str = PROVIDER_NAME

    def to_dict(self) -> dict:
        return asdict(self)

    def to_public_dict(self) -> dict:
        data = self.to_dict()
        data.pop("provider", None)
        return data


@dataclass
class HotelOption:
    name: str
    address: str
    distance_km: float
    price_per_night: int
    room_type: str
    check_in: str
    check_out: str
    provider: str = PROVIDER_NAME

    def to_dict(self) -> dict:
        return asdict(self)

    def to_public_dict(self) -> dict:
        data = self.to_dict()
        data.pop("provider", None)
        return data


@dataclass
class TravelBookingSnapshot:
    flights: list[FlightOption]
    hotels: list[HotelOption]
    provider: str = PROVIDER_NAME
    queried_at: str = ""

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "queried_at": self.queried_at,
            "flights": [f.to_dict() for f in self.flights],
            "hotels": [h.to_dict() for h in self.hotels],
        }

    def to_public_dict(self) -> dict:
        return {
            "queried_at": self.queried_at,
            "flights": [f.to_public_dict() for f in self.flights],
            "hotels": [h.to_public_dict() for h in self.hotels],
        }


def _seed_key(*parts: str) -> int:
    raw = "|".join(parts).encode("utf-8")
    return int(hashlib.md5(raw).hexdigest()[:8], 16)


def _resolve_departure_date(hint: str | None) -> date:
    today = date.today()
    if hint and "明天" in hint:
        return today + timedelta(days=1)
    if hint and "后天" in hint:
        return today + timedelta(days=2)
    if hint and "周四" in hint:
        weekday = today.weekday()
        thursday = 3
        delta = (thursday - weekday) % 7
        if delta == 0:
            delta = 7
        return today + timedelta(days=delta)
    return today + timedelta(days=1)


def _cabin_label(pref: str | None) -> tuple[str, int]:
    pref = pref or "经济舱"
    if "公务" in pref or "商务" in pref:
        return "公务舱", 1680
    if "头等" in pref:
        return "头等舱", 2680
    return "经济舱", 860


async def search_flights(
    origin: str,
    destination: str,
    *,
    origin_airport: str | None = None,
    departure_hint: str | None = None,
    cabin_pref: str | None = None,
    arrival_before: str | None = None,
) -> list[FlightOption]:
    """模拟调用第三方航班查询 API。"""
    dep_date = _resolve_departure_date(departure_hint)
    cabin, base_price = _cabin_label(cabin_pref)
    seed = _seed_key(origin, destination, str(dep_date), cabin)
    o_ap = origin_airport or _CITY_AIRPORT.get(origin, f"{origin}机场")
    d_ap = _CITY_AIRPORT.get(destination, f"{destination}机场")

    if arrival_before and ("2点" in arrival_before or "14" in arrival_before):
        schedules = [(9, 11), (10, 12), (11, 13)]
    else:
        schedules = [
            (10 + (seed % 2), 12 + (seed % 3)),
            (12 + (seed % 2), 14 + (seed % 2)),
            (14 + (seed % 2), 16 + (seed % 2)),
        ]

    flight_nos = [
        f"CA{1500 + seed % 800}",
        "CA1234",
        "CA6789",
    ]
    airlines = ["中国国际航空", "中国国际航空", "中国南方航空"]
    price_offsets = [0, 80, 150]

    flights: list[FlightOption] = []
    for idx, (flight_no, airline, (dep_h, arr_h), offset) in enumerate(
        zip(flight_nos, airlines, schedules, price_offsets, strict=False)
    ):
        flights.append(
            FlightOption(
                flight_no=flight_no,
                airline=airline,
                origin=f"{o_ap}（{origin}）",
                destination=f"{d_ap}（{destination}）",
                departure_time=f"{dep_date.isoformat()} {dep_h:02d}:30",
                arrival_time=f"{dep_date.isoformat()} {arr_h:02d}:45",
                cabin=cabin,
                price=base_price + offset + (seed % 100),
            )
        )
    return flights[:3]


async def search_hotels(
    city: str,
    nights: int,
    *,
    max_price: int | None = None,
    max_distance_km: float | None = None,
    room_type: str | None = None,
    departure_hint: str | None = None,
) -> list[HotelOption]:
    """模拟调用第三方酒店查询 API。"""
    check_in = _resolve_departure_date(departure_hint)
    check_out = check_in + timedelta(days=max(nights, 1))
    budget = max_price or 500
    dist_limit = max_distance_km or 3.0
    room = room_type or "标准间"
    prefix = _CITY_HOTEL_PREFIX.get(city, city)
    seed = _seed_key(city, str(budget), str(dist_limit), room)

    templates = [
        (f"{prefix}商务酒店", 1.2, min(budget, int(budget * 0.85)), room),
        (f"{prefix}如家快捷酒店", 2.0, min(max(budget, 260), 300), "快捷大床房"),
        (f"{prefix}汉庭优选", 2.6, 298, "标间"),
    ]
    hotels: list[HotelOption] = []
    for idx, (name, dist_factor, price, room_label) in enumerate(templates):
        dist = round(min(dist_limit + 0.5, dist_factor + (seed % 10) / 10), 1)
        hotels.append(
            HotelOption(
                name=name,
                address=f"{city}能源大厦附近 {dist}km",
                distance_km=dist,
                price_per_night=int(price),
                room_type=room_label if idx > 0 else (room or room_label),
                check_in=check_in.isoformat(),
                check_out=check_out.isoformat(),
            )
        )
    return hotels[:3]


async def query_travel_bookings(plan) -> TravelBookingSnapshot:
    """根据 TravelPlan 一次性查询航班与酒店。"""
    flights: list[FlightOption] = []
    hotels: list[HotelOption] = []

    if plan.needs_transport:
        origin = plan.origin_airport or plan.origin or "北京"
        if "机场" in origin:
            origin_city = "北京"
            origin_airport = origin
        else:
            origin_city = origin
            origin_airport = plan.origin_airport
        flights = await search_flights(
            origin_city,
            plan.destination or "目的地",
            origin_airport=origin_airport,
            departure_hint=plan.departure_hint,
            cabin_pref=plan.transport_pref,
            arrival_before=plan.arrival_deadline,
        )

    if plan.needs_hotel:
        nights = max((plan.trip_days or 1) - 1, 1)
        hotels = await search_hotels(
            plan.destination or "目的地",
            nights,
            max_price=plan.hotel_max_price,
            max_distance_km=plan.hotel_max_distance_km,
            room_type=plan.hotel_room_type,
            departure_hint=plan.departure_hint,
        )

    return TravelBookingSnapshot(
        flights=flights,
        hotels=hotels,
        queried_at=datetime.now().isoformat(timespec="seconds"),
    )
