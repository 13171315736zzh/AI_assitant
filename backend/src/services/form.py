from datetime import UTC, datetime

from src.models.form import (
    FORM_TYPES,
    FormPublic,
    FormReceiptPublic,
    FormStatusPublic,
    FormSubmitPublic,
)
from src.repositories.form import FormRepository

_TRAVEL_FIELDS = {
    "destination": "鄂尔多斯",
    "departure_date": "2026-03-26",
    "return_date": "2026-03-28",
    "project": "神东能源数据治理平台",
    "transport": "飞机 · 经济舱",
    "description": "现场培训",
}

_FORM_TEMPLATES: dict[str, tuple[str, dict[str, str]]] = {
    "travel": ("差旅申请表单", dict(_TRAVEL_FIELDS)),
    "workpackage": (
        "工包填报",
        {
            "project": "神东能源数据治理平台",
            "hours": "40",
            "content": "数据治理方案编写",
            "period": "2026-W12",
        },
    ),
    "meeting": (
        "会议预约",
        {
            "subject": "项目进度评审会",
            "start_time": "2026-03-26 14:00",
            "end_time": "2026-03-26 16:00",
            "room": "总部 A301",
            "attendees": "张明、李经理、王芳",
        },
    ),
    "email": (
        "邮件撰写",
        {
            "to": "limanager@ceic.com",
            "cc": "",
            "subject": "神东项目出差安排确认",
            "body": "赵士廷经理，您好！\n\n烦请知悉，我计划于下周三前往神东项目现场…\n\n此致\n敬礼",
        },
    ),
}

_SUBMIT_MESSAGES = {
    "travel": "差旅申请已进入审批流程",
    "workpackage": "工包填报已提交",
    "meeting": "会议预约已提交",
    "email": "邮件已发送",
}


def _to_form_public(record) -> FormPublic:
    return FormPublic(
        form_id=record.id,
        form_type=record.form_type,
        status=record.status,
        title=record.title,
        fields=dict(record.fields_json or {}),
    )


class FormService:
    def __init__(self, form_repo: FormRepository):
        self.form_repo = form_repo

    async def preview(
        self,
        user_id: int,
        form_type: str,
        session_id: str,
        task_id: str | None,
        fields: dict[str, str] | None,
    ) -> FormPublic | None:
        if form_type not in FORM_TYPES:
            return None
        title, template = _FORM_TEMPLATES[form_type]
        merged = {**template, **(fields or {})}
        record = await self.form_repo.create(
            user_id=user_id,
            form_type=form_type,
            title=title,
            fields=merged,
            session_id=session_id,
            task_id=task_id,
        )
        return _to_form_public(record)

    async def get_form(self, user_id: int, form_id: str) -> FormPublic | None:
        record = await self.form_repo.get_by_id(form_id, user_id)
        if record is None:
            return None
        return _to_form_public(record)

    async def confirm(self, user_id: int, form_id: str) -> FormStatusPublic | None:
        record = await self.form_repo.get_by_id(form_id, user_id)
        if record is None:
            return None
        if record.status == "submitted":
            return FormStatusPublic(form_id=record.id, status=record.status)
        updated = await self.form_repo.update(record, status="confirmed")
        return FormStatusPublic(form_id=updated.id, status=updated.status)

    async def submit(
        self, user_id: int, form_id: str, fields: dict[str, str]
    ) -> FormSubmitPublic | None:
        record = await self.form_repo.get_by_id(form_id, user_id)
        if record is None:
            return None
        merged = {**(record.fields_json or {}), **fields}
        receipt_id = f"RC{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        summary = _SUBMIT_MESSAGES.get(record.form_type, "提交成功")
        updated = await self.form_repo.update(
            record,
            status="submitted",
            fields_json=merged,
            receipt_id=receipt_id,
            receipt_summary=summary,
            submitted_at=datetime.now(UTC),
        )
        return FormSubmitPublic(
            form_id=updated.id,
            status=updated.status,
            receipt_id=receipt_id,
            message=summary,
        )

    async def get_receipt(self, user_id: int, form_id: str) -> FormReceiptPublic | None:
        record = await self.form_repo.get_by_id(form_id, user_id)
        if record is None or not record.receipt_id:
            return None
        return FormReceiptPublic(
            receipt_id=record.receipt_id,
            status=record.status,
            summary=record.receipt_summary or "提交成功",
            submitted_at=(
                record.submitted_at.isoformat()
                if record.submitted_at
                else datetime.now(UTC).isoformat()
            ),
        )
