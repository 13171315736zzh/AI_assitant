from src.config.settings import get_settings
from src.db.user_model import User
from src.db.user_settings_models import UserSettingsRecord
from src.models.settings import (
    ChangelogEntry,
    ClearMemoryPublic,
    MemoryItem,
    MemoryPublic,
    MemoryStructured,
    MemoryUpdateRequest,
    ProfilePublic,
    ThemePublic,
    ThemeUpdateRequest,
    VersionCheckPublic,
    VersionPublic,
)
from src.repositories.user import UserRepository
from src.repositories.user_settings import UserSettingsRepository

DEMO_MEMORY_ITEMS = [
    {"key": "常用出差目的地", "value": "鄂尔多斯、北京"},
    {"key": "常用联系人", "value": "李经理（工包审批）"},
    {"key": "默认部门", "value": "神东煤炭集团"},
    {"key": "沟通偏好", "value": "简洁回复，优先表格展示"},
    {"key": "差旅偏好", "value": "优先下午航班，经济舱"},
]

DEMO_STRUCTURED = {
    "employee_id": "0176338",
    "department": "神东煤炭集团",
    "position": "员工",
    "email": "zhangming@ceic.com",
    "travel_mode_preference": "经济舱",
    "related_projects": ["神东能源数据治理平台"],
    "gender": "unknown",
}

CHANGELOG = [
    ChangelogEntry(
        version="1.0.0",
        date="2026-03-20",
        items=[
            "首次发布：对话、知识库、差旅/工包/会议/邮件工具",
            "支持个人设置与长期记忆",
            "人工协助 Mock 工单",
        ],
    )
]


def _base_structured(user: User) -> dict:
    return {
        "employee_id": user.employee_id,
        "department": "",
        "position": "管理员" if user.role == "admin" else "员工",
        "email": "",
        "travel_mode_preference": "",
        "related_projects": [],
        "gender": "unknown",
    }


def _demo_structured(user: User) -> dict:
    if user.username == "user_a":
        return dict(DEMO_STRUCTURED)
    return _base_structured(user)


def _demo_memory_items(user: User) -> list[dict]:
    if user.username == "user_a":
        return [dict(item) for item in DEMO_MEMORY_ITEMS]
    return []


class SettingsService:
    def __init__(
        self,
        settings_repo: UserSettingsRepository,
        user_repo: UserRepository,
    ):
        self.settings_repo = settings_repo
        self.user_repo = user_repo

    async def _get_user(self, user_id: int) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise ValueError("用户不存在")
        return user

    async def _get_or_create_settings(self, user: User) -> UserSettingsRecord:
        record = await self.settings_repo.get_by_user_id(user.id)
        if record is not None:
            return record
        return await self.settings_repo.create(
            user_id=user.id,
            memory_items_json=_demo_memory_items(user),
            structured_json=_demo_structured(user),
        )

    def _to_memory_public(self, record: UserSettingsRecord) -> MemoryPublic:
        structured = MemoryStructured.model_validate(record.structured_json or {})
        items = [MemoryItem.model_validate(item) for item in record.memory_items_json or []]
        return MemoryPublic(
            memory_enabled=record.memory_enabled,
            structured=structured,
            memory_items=items,
        )

    async def get_profile(self, user_id: int) -> ProfilePublic:
        user = await self._get_user(user_id)
        return ProfilePublic(
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            employee_id=user.employee_id,
        )

    async def get_theme(self, user_id: int) -> ThemePublic:
        user = await self._get_user(user_id)
        record = await self._get_or_create_settings(user)
        return ThemePublic(theme=record.theme)  # type: ignore[arg-type]

    async def update_theme(self, user_id: int, body: ThemeUpdateRequest) -> ThemePublic:
        user = await self._get_user(user_id)
        record = await self._get_or_create_settings(user)
        record.theme = body.theme
        await self.settings_repo.save(record)
        return ThemePublic(theme=record.theme)  # type: ignore[arg-type]

    async def get_version(self) -> VersionPublic:
        settings = get_settings()
        return VersionPublic(
            version=settings.app_version,
            release_date="2026-03-20",
            has_update=False,
            changelog=CHANGELOG,
        )

    async def check_version(self) -> VersionCheckPublic:
        return VersionCheckPublic(has_update=False, message="已是最新版本")

    async def get_memory(self, user_id: int) -> MemoryPublic:
        user = await self._get_user(user_id)
        record = await self._get_or_create_settings(user)
        return self._to_memory_public(record)

    async def update_memory(self, user_id: int, body: MemoryUpdateRequest) -> MemoryPublic:
        user = await self._get_user(user_id)
        record = await self._get_or_create_settings(user)
        if body.memory_enabled is not None:
            record.memory_enabled = body.memory_enabled
        if body.memory_items is not None:
            record.memory_items_json = [item.model_dump() for item in body.memory_items]
        await self.settings_repo.save(record)
        return self._to_memory_public(record)

    async def clear_memory(self, user_id: int) -> ClearMemoryPublic:
        user = await self._get_user(user_id)
        record = await self._get_or_create_settings(user)
        record.memory_items_json = []
        record.structured_json = _base_structured(user)
        await self.settings_repo.save(record)
        return ClearMemoryPublic(cleared=True)
