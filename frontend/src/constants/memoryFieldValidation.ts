export function normalizeIdNumber(value: string): string {
  return value.trim().toUpperCase()
}

export function normalizeEmployeeId(value: string): string {
  return value.trim().toUpperCase()
}

const FIELD_LABELS: Record<string, string> = {
  id_number: '身份证号',
  employee_id: '工号',
  email: '邮箱',
  travel_mode_preference: '交通偏好',
}

export function formatFieldError(key: string, detail: string): string {
  const label = FIELD_LABELS[key] ?? key
  return `您填入的${label}不符合格式要求：${detail}，请修改`
}

const ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2] as const
const ID_CHECK_CODES = '10X98765432'

function isValidBirthDate(yyyymmdd: string): boolean {
  if (!/^\d{8}$/.test(yyyymmdd)) return false
  const year = Number(yyyymmdd.slice(0, 4))
  const month = Number(yyyymmdd.slice(4, 6))
  const day = Number(yyyymmdd.slice(6, 8))
  const date = new Date(year, month - 1, day)
  return (
    date.getFullYear() === year
    && date.getMonth() === month - 1
    && date.getDate() === day
  )
}

export function validateIdNumber(value: string): string | null {
  const text = normalizeIdNumber(value)
  if (!text) return null
  if (!/^\d{17}[\dX]$/.test(text)) {
    return '身份证号须为 18 位，末位可为数字或 X'
  }
  if (!isValidBirthDate(text.slice(6, 14))) {
    return '身份证号中的出生日期无效'
  }
  let total = 0
  for (let i = 0; i < 17; i += 1) {
    total += Number(text[i]) * ID_WEIGHTS[i]
  }
  if (ID_CHECK_CODES[total % 11] !== text[17]) {
    return '身份证号校验位不正确，请核对'
  }
  return null
}

export function validateEmployeeId(value: string): string | null {
  const text = normalizeEmployeeId(value)
  if (!text) return null
  if (!/^[A-Za-z0-9]{1,9}$/.test(text)) {
    return '工号仅支持字母和数字，最多 9 位'
  }
  return null
}

export function validateEmail(value: string): string | null {
  const text = value.trim()
  if (!text) return null
  if (!/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(text)) {
    return '邮箱格式不正确，请填写如 name@company.com'
  }
  return null
}

export function validateMemoryStructuredFields(structured: {
  id_number?: string
  employee_id?: string
  email?: string
}): Record<string, string> {
  const errors: Record<string, string> = {}
  const idError = validateIdNumber(structured.id_number ?? '')
  if (idError) errors.id_number = formatFieldError('id_number', idError)
  const empError = validateEmployeeId(structured.employee_id ?? '')
  if (empError) errors.employee_id = formatFieldError('employee_id', empError)
  const emailError = validateEmail(structured.email ?? '')
  if (emailError) errors.email = formatFieldError('email', emailError)
  return errors
}
