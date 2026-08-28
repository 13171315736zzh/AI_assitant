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
                            "document_id": "doc_001",
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


DEMO_TASK = {
    "id": "task_001",
    "session_id": "sess_001",
    "goal": "下周三去神东项目出差，安排差旅申请和机票",
    "status": "running",
    "current_step": 2,
    "total_steps": 4,
    "replan_count": 0,
    "steps": [
        {
            "step_id": 1,
            "action": "差旅申请创建",
            "tool": "travel_apply",
            "status": "completed",
            "depends_on": [],
            "params": {"destination": "鄂尔多斯"},
            "result": {"receipt_id": "TA20260325001", "form_id": "form_001"},
        },
        {
            "step_id": 2,
            "action": "机票预订",
            "tool": "flight_book",
            "status": "running",
            "depends_on": [1],
            "params": {"cabin": "economy"},
            "result": None,
        },
        {
            "step_id": 3,
            "action": "酒店预订",
            "tool": "hotel_book",
            "status": "pending",
            "depends_on": [1],
            "params": {},
            "result": None,
        },
        {
            "step_id": 4,
            "action": "用户确认",
            "tool": "user_confirm",
            "status": "pending",
            "depends_on": [2, 3],
            "params": {},
            "result": None,
        },
    ],
}


async def seed_demo_tasks() -> None:
    async with get_session() as db:
        from src.db.task_models import TaskRecord
        from src.repositories.task import TaskRepository

        user_repo = UserRepository(db)
        user = await user_repo.get_by_username("user_a")
        if user is None:
            return

        repo = TaskRepository(db)
        if await repo.exists(DEMO_TASK["id"]):
            return

        now = datetime.now(UTC)
        db.add(
            TaskRecord(
                id=DEMO_TASK["id"],
                session_id=DEMO_TASK["session_id"],
                user_id=user.id,
                goal=DEMO_TASK["goal"],
                status=DEMO_TASK["status"],
                current_step=DEMO_TASK["current_step"],
                total_steps=DEMO_TASK["total_steps"],
                replan_count=DEMO_TASK["replan_count"],
                steps_json=DEMO_TASK["steps"],
                created_at=now,
            )
        )


async def seed_user_settings() -> None:
    async with get_session() as db:
        from src.db.user_settings_models import UserSettingsRecord
        from src.repositories.user import UserRepository
        from src.repositories.user_settings import UserSettingsRepository

        user_repo = UserRepository(db)
        settings_repo = UserSettingsRepository(db)

        demo_memory_items = [
            {"key": "常用出差目的地", "value": "鄂尔多斯、北京"},
            {"key": "常用联系人", "value": "李经理（工包审批）"},
            {"key": "默认部门", "value": "神东煤炭集团"},
            {"key": "沟通偏好", "value": "简洁回复，优先表格展示"},
            {"key": "差旅偏好", "value": "优先下午航班，经济舱"},
        ]
        demo_structured = {
            "employee_id": "0176338",
            "department": "神东煤炭集团",
            "position": "员工",
            "email": "zhangming@ceic.com",
            "travel_mode_preference": "经济舱",
            "related_projects": ["神东能源数据治理平台"],
            "gender": "unknown",
        }

        for username, _, _, role, employee_id in SEED_ACCOUNTS:
            user = await user_repo.get_by_username(username)
            if user is None:
                continue
            if await settings_repo.get_by_user_id(user.id) is not None:
                continue
            if username == "user_a":
                memory_items = demo_memory_items
                structured = demo_structured
            else:
                memory_items = []
                structured = {
                    "employee_id": employee_id,
                    "department": "",
                    "position": "管理员" if role == "admin" else "员工",
                    "email": "",
                    "travel_mode_preference": "",
                    "related_projects": [],
                    "gender": "unknown",
                }
            db.add(
                UserSettingsRecord(
                    user_id=user.id,
                    theme="light",
                    memory_enabled=True,
                    memory_items_json=memory_items,
                    structured_json=structured,
                )
            )


async def seed_demo_forms() -> None:
    async with get_session() as db:
        from src.db.form_models import FormRecord
        from src.repositories.form import FormRepository

        user_repo = UserRepository(db)
        user = await user_repo.get_by_username("user_a")
        if user is None:
            return

        repo = FormRepository(db)
        if await repo.exists("form_001"):
            return

        now = datetime.now(UTC)
        db.add(
            FormRecord(
                id="form_001",
                user_id=user.id,
                session_id="sess_001",
                task_id="task_001",
                form_type="travel",
                status="preview",
                title="差旅申请表单",
                fields_json={
                    "destination": "鄂尔多斯",
                    "departure_date": "2026-03-26",
                    "return_date": "2026-03-28",
                    "project": "神东能源数据治理平台",
                    "transport": "飞机 · 经济舱",
                    "description": "现场培训",
                },
                created_at=now,
            )
        )


async def seed_knowledge() -> None:
    async with get_session() as db:
        from pathlib import Path

        from src.db.knowledge_models import DocumentChunkRecord, DocumentRecord, QARecord
        from src.repositories.knowledge import KnowledgeRepository

        repo = KnowledgeRepository(db)
        if await repo.document_exists("doc_001"):
            return

        now = datetime.now(UTC)
        docs_dir = Path(__file__).resolve().parents[1] / "data" / "documents"
        pdf_path = docs_dir / "doc_001.pdf"

        db.add(
            DocumentRecord(
                id="doc_001",
                filename="国家能源集团差旅管理办法2024修订版.pdf",
                file_type="pdf",
                file_path=str(pdf_path),
                status="ready",
                stage="ready",
                progress_percent=100,
                uploaded_by="admin",
                created_at=now,
                updated_at=now,
            )
        )
        db.add(
            DocumentRecord(
                id="doc_002",
                filename="差旅报销实施细则.docx",
                file_type="docx",
                file_path=str(docs_dir / "doc_002.docx"),
                status="ready",
                stage="ready",
                progress_percent=100,
                uploaded_by="admin",
                created_at=now,
                updated_at=now,
            )
        )

        qa_items = [
            (
                "qa_001",
                "doc_001",
                "鄂尔多斯住宿费标准是多少？",
                "其他人员不超过300元/天",
                "差旅管理办法·第十二条",
            ),
            (
                "qa_002",
                "doc_001",
                "出差伙食补助标准是多少？",
                "国内出差伙食补助费标准为100元/天",
                "差旅管理办法·第十五条",
            ),
            (
                "qa_003",
                "doc_002",
                "差旅报销需要哪些材料？",
                "需提供差旅申请单、交通票据、住宿发票及费用明细表",
                "报销实施细则·第三章",
            ),
        ]
        for qa_id, doc_id, question, answer, clause in qa_items:
            db.add(
                QARecord(
                    id=qa_id,
                    document_id=doc_id,
                    question=question,
                    answer=answer,
                    source_clause=clause,
                )
            )

        chunks = [
            (
                "chunk_001",
                "doc_001",
                0,
                "第三章 差旅费用标准 第十二条 其他人员鄂尔多斯地区住宿费不超过300元/天，北京、上海等一线城市不超过500元/天。",
                "第三章第十二条",
            ),
            (
                "chunk_002",
                "doc_001",
                1,
                "第十五条 国内出差伙食补助费标准为100元/天，凭票据实报销的除外。",
                "第十五条",
            ),
            (
                "chunk_003",
                "doc_002",
                0,
                "第三章 报销材料 需提供差旅申请单、交通票据、住宿发票及费用明细表，缺一不可。",
                "第三章",
            ),
        ]
        for chunk_id, doc_id, index, content, clause in chunks:
            db.add(
                DocumentChunkRecord(
                    id=chunk_id,
                    document_id=doc_id,
                    chunk_index=index,
                    content=content,
                    source_clause=clause,
                    keywords_json=[],
                )
            )
