from datetime import UTC, datetime

from src.core.security import hash_password
from src.db.session import get_session
from src.repositories.session import MessageRepository, SessionRepository
from src.repositories.user import UserRepository

SEED_ACCOUNTS = [
    ("admin", "admin123", "管理员", "admin", "0000001"),
    ("user_a", "usera123", "张明", "employee", "0176338"),
    ("user_b", "userb123", "李华", "employee", "0176401"),
]

DEMO_SESSIONS = [
    {
        "id": "sess_001",
        "title": "神东出差安排",
        "status": "active",
        "ended_reason": None,
        "messages": [
            ("msg_001", "user", "下周三去神东项目出差，帮我安排差旅申请和机票", "text", None),
            (
                "msg_002",
                "assistant",
                "好的，我已开始为您安排。请先确认以下信息…",
                "task",
                {
                    "task_id": "task_001",
                    "task_title": "神东出差差旅安排",
                    "progress": "2/4",
                    "progress_percent": 50,
                    "steps_desc": "差旅申请创建 · 机票预订 · 酒店预订 · 用户确认",
                },
            ),
        ],
    },
    {
        "id": "sess_002",
        "title": "鄂尔多斯住宿费标准",
        "status": "ended",
        "ended_reason": "completed",
        "messages": [
            ("msg_101", "user", "鄂尔多斯出差住宿费标准是多少？", "text", None),
            (
                "msg_102",
                "assistant",
                "根据《国家能源集团差旅管理办法》第三章第十二条，其他人员鄂尔多斯地区住宿费不超过 300 元/天。",
                "text",
                {
                    "sources": [
                        {
                            "filename": "国家能源集团差旅管理办法2024修订版.pdf",
                            "clause": "第三章第十二条",
                        }
                    ]
                },
            ),
        ],
    },
]


async def seed_users() -> None:
    async with get_session() as db:
        repo = UserRepository(db)
        if await repo.count() > 0:
            return
        for username, password, display_name, role, employee_id in SEED_ACCOUNTS:
            await repo.create(
                username=username,
                hashed_password=hash_password(password),
                display_name=display_name,
                role=role,
                employee_id=employee_id,
            )


async def seed_demo_sessions() -> None:
    async with get_session() as db:
        session_repo = SessionRepository(db)
        user_repo = UserRepository(db)
        message_repo = MessageRepository(db)
        user = await user_repo.get_by_username("user_a")
        if user is None:
            return
        existing, _ = await session_repo.list_by_user(user.id, None, 1, 1)
        if existing:
            return

        now = datetime.now(UTC)
        for item in DEMO_SESSIONS:
            from src.db.chat_models import MessageRecord, SessionRecord

            session = SessionRecord(
                id=item["id"],
                user_id=user.id,
                title=item["title"],
                status=item["status"],
                ended_reason=item["ended_reason"],
                message_count=len(item["messages"]),
                created_at=now,
                updated_at=now,
            )
            db.add(session)
            for msg_id, role, content, msg_type, meta in item["messages"]:
                db.add(
                    MessageRecord(
                        id=msg_id,
                        session_id=item["id"],
                        role=role,
                        content=content,
                        message_type=msg_type,
                        metadata_json=meta,
                        created_at=now,
                    )
                )
