"""长期记忆字段格式校验。"""

from __future__ import annotations

import re
from datetime import datetime

_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK_CODES = "10X98765432"
_EMPLOYEE_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{1,9}$")
_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

STRUCTURED_FIELD_LABELS: dict[str, str] = {
    "display_name": "姓名",
    "gender": "性别",
    "id_number": "身份证号",
    "employee_id": "工号",
    "job_role": "岗位",
    "position": "岗位类型",
    "base_location": "常驻地（Base）",
    "department": "部门",
    "email": "邮箱",
    "travel_mode_preference": "交通偏好",
    "related_projects": "关联项目",
}


def format_field_error(field_key: str, detail: str) -> str:
    label = STRUCTURED_FIELD_LABELS.get(field_key, field_key)
    return f"您填入的{label}不符合格式要求：{detail}，请修改"


def normalize_id_number(value: str | None) -> str:
    return (value or "").strip().upper()


def normalize_employee_id(value: str | None) -> str:
    return (value or "").strip().upper()


def validate_id_number(value: str | None) -> str | None:
    """校验中国大陆 18 位身份证号；空值视为未填写。"""
    text = normalize_id_number(value)
    if not text:
        return None
    if not re.fullmatch(r"\d{17}[\dX]", text):
        return "身份证号须为 18 位，末位可为数字或 X"
    try:
        datetime.strptime(text[6:14], "%Y%m%d")
    except ValueError:
        return "身份证号中的出生日期无效"
    total = sum(int(text[i]) * _ID_WEIGHTS[i] for i in range(17))
    if _ID_CHECK_CODES[total % 11] != text[17]:
        return "身份证号校验位不正确，请核对"
    return None


def validate_employee_id(value: str | None) -> str | None:
    """工号：字母 + 数字，最多 9 位；空值视为未填写。"""
    text = normalize_employee_id(value)
    if not text:
        return None
    if not _EMPLOYEE_ID_PATTERN.fullmatch(text):
        return "工号仅支持字母和数字，最多 9 位"
    return None


def validate_email(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if not _EMAIL_PATTERN.fullmatch(text):
        return "邮箱格式不正确，请填写如 name@company.com"
    return None


def validate_structured_fields(structured: dict) -> dict[str, str]:
    """返回字段级错误信息（含用户可读前缀）。"""
    errors: dict[str, str] = {}
    id_err = validate_id_number(str(structured.get("id_number") or ""))
    if id_err:
        errors["id_number"] = format_field_error("id_number", id_err)
    emp_err = validate_employee_id(str(structured.get("employee_id") or ""))
    if emp_err:
        errors["employee_id"] = format_field_error("employee_id", emp_err)
    email_err = validate_email(str(structured.get("email") or ""))
    if email_err:
        errors["email"] = format_field_error("email", email_err)
    return errors
