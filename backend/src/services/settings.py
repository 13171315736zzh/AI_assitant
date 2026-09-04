from src.agent.user_memory import is_position_confirmed
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
    WelcomePublic,
)
from src.repositories.system_config import SystemConfigRepository
from src.repositories.user import UserRepository
from src.repositories.user_settings import UserSettingsRepository
from src.services.admin import SystemConfigService

DEMO_STRUCTURED = {
    "display_name": "张明",
    "employee_id": "0176338",
    "job_role": "产品经理",
    "department": "神东煤炭集团",
    "position": "非管理岗",
    "email": "zhangming@ceic.com",
    "travel_mode_preference": "高铁",
    "related_projects": ["神东能源数据治理平台"],
    "gender": "男",
    "id_number": "",
    "base_location": "北京市",
}

DEMO_MEMORY_ITEMS = [
    {"key": "常用出差目的地", "value": "鄂尔多斯、北京"},
    {"key": "常用联系人", "value": "李经理（工包审批）"},
    {"key": "沟通偏好", "value": "简洁回复，优先表格展示"},
    {"key": "差旅偏好", "value": "优先下午航班，经济舱"},
]

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
        "display_name": user.display_name or "",
        "employee_id": user.employee_id or "",
        "job_role": "",
        "department": "",
        "position": "",
        "email": "",
        "travel_mode_preference": "",
        "related_projects": [],
        "gender": "unknown",
        "id_number": "",
        "base_location": "",
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
        system_config_repo: SystemConfigRepository | None = None,
    ):
        self.settings_repo = settings_repo
        self.user_repo = user_repo
        self.system_config_repo = system_config_repo

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

    async def _normalize_structured_fields(
        self,
        structured: dict,
        *,
        source_text: str = "",
    ) -> dict:
        from src.services.project_mapping import ProjectMappingService

        return await ProjectMappingService(self.settings_repo.db).normalize_memory_structured(
            structured,
            source_text=source_text,
        )

    def _to_memory_public(self, record: UserSettingsRecord) -> MemoryPublic:
        from src.agent.memory_extractor import count_memory_fields, filter_extension_memory_items

        structured = MemoryStructured.model_validate(record.structured_json or {})
        filtered_items = filter_extension_memory_items(list(record.memory_items_json or []))
        items = [MemoryItem.model_validate(item) for item in filtered_items]
        return MemoryPublic(
            memory_enabled=record.memory_enabled,
            structured=structured,
            memory_items=items,
            field_count=count_memory_fields(
                record.structured_json or {}, filtered_items
            ),
        )

    async def _persist_filtered_memory_items(self, record: UserSettingsRecord) -> None:
        from src.agent.memory_extractor import filter_extension_memory_items

        raw_items = list(record.memory_items_json or [])
        filtered = filter_extension_memory_items(raw_items)
        if filtered != raw_items:
            record.memory_items_json = filtered
            await self.settings_repo.save(record)

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
        await self._persist_filtered_memory_items(record)
        public = self._to_memory_public(record)
        normalized = await self._normalize_structured_fields(public.structured.model_dump())
        public.structured = MemoryStructured.model_validate(normalized)
        return public

    async def update_memory(self, user_id: int, body: MemoryUpdateRequest) -> MemoryPublic:
        user = await self._get_user(user_id)
        record = await self._get_or_create_settings(user)
        if body.memory_enabled is not None:
            record.memory_enabled = body.memory_enabled
        if body.structured is not None:
            normalized = await self._normalize_structured_fields(body.structured.model_dump())
            record.structured_json = MemoryStructured.model_validate(normalized).model_dump()
        if body.memory_items is not None:
            from src.agent.memory_extractor import filter_extension_memory_items

            payload = [item.model_dump() for item in body.memory_items]
            record.memory_items_json = filter_extension_memory_items(payload)
        await self.settings_repo.save(record)
        return self._to_memory_public(record)

    async def clear_memory(self, user_id: int) -> ClearMemoryPublic:
        user = await self._get_user(user_id)
        record = await self._get_or_create_settings(user)
        record.memory_items_json = []
        record.structured_json = _base_structured(user)
        await self.settings_repo.save(record)
        return ClearMemoryPublic(cleared=True)

    async def build_agent_memory_snippets(self, user_id: int) -> str:
        from src.agent.user_memory import build_user_memory_snippets

        user = await self._get_user(user_id)
        record = await self._get_or_create_settings(user)
        return build_user_memory_snippets(
            display_name=user.display_name,
            structured=dict(record.structured_json or {}),
            memory_items=list(record.memory_items_json or []),
            memory_enabled=record.memory_enabled,
        )

    async def try_extract_memory_from_message(
        self,
        user_id: int,
        user_content: str,
        assistant_context: str | None = None,
    ) -> bool:
        from src.agent.memory_extractor import (
            extract_memory_item_updates,
            extract_structured_updates,
            merge_memory_items,
            merge_structured,
            sanitize_structured_seed,
        )
        from src.agent.user_memory import extract_position, is_position_confirmed

        user = await self._get_user(user_id)
        record = await self._get_or_create_settings(user)
        if not record.memory_enabled:
            return False

        structured = sanitize_structured_seed(
            dict(record.structured_json or _base_structured(user))
        )
        if not structured.get("display_name"):
            structured["display_name"] = user.display_name
        if not structured.get("employee_id"):
            structured["employee_id"] = user.employee_id

        updates = extract_structured_updates(user_content)
        if updates.get("position") or not is_position_confirmed(structured.get("position")):
            if "position" not in updates:
                position = extract_position(user_content, assistant_context)
                if position:
                    updates["position"] = position

        item_updates = extract_memory_item_updates(user_content)
        if not updates and not item_updates:
            return False

        merged_structured = merge_structured(structured, updates)
        merged_structured = await self._normalize_structured_fields(
            merged_structured,
            source_text=user_content,
        )
        merged_items = merge_memory_items(
            list(record.memory_items_json or []), item_updates
        )

        record.structured_json = merged_structured
        record.memory_items_json = merged_items
        await self.settings_repo.save(record)
        return True

    async def try_extract_position_from_message(
        self,
        user_id: int,
        user_content: str,
        assistant_context: str | None = None,
    ) -> bool:
        return await self.try_extract_memory_from_message(
            user_id, user_content, assistant_context
        )

    async def get_user_structured_memory(self, user_id: int) -> dict:
        user = await self._get_user(user_id)
        record = await self._get_or_create_settings(user)
        structured = dict(record.structured_json or _base_structured(user))
        if not structured.get("display_name"):
            structured["display_name"] = user.display_name
        if not structured.get("employee_id"):
            structured["employee_id"] = user.employee_id
        return structured

    async def get_confirmed_position(self, user_id: int) -> str | None:
        user = await self._get_user(user_id)
        record = await self._get_or_create_settings(user)
        structured = dict(record.structured_json or {})
        position = (structured.get("position") or "").strip()
        if is_position_confirmed(position):
            return position
        return None

    async def get_travel_staff_level(self, user_id: int) -> str:
        from src.agent.user_memory import resolve_travel_staff_level

        structured = await self.get_user_structured_memory(user_id)
        position = await self.get_confirmed_position(user_id)
        return resolve_travel_staff_level(
            memory_structured=structured,
            override=position,
        )

    async def get_welcome(self) -> WelcomePublic:
        if self.system_config_repo is None:
            return WelcomePublic(welcome_message="您好，我是国能办公助手，有什么可以帮您？")
        config = await SystemConfigService(self.system_config_repo).get_config()
        return WelcomePublic(welcome_message=config.welcome_message)
