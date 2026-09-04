/** 与「核心个人信息」重复的扩展记忆键名，不在下方扩展条目中展示 */
export const EXTENSION_MEMORY_RESERVED_KEYS = new Set([
  'display_name',
  'gender',
  'id_number',
  'employee_id',
  'job_role',
  'position',
  'base_location',
  'department',
  'email',
  'travel_mode_preference',
  'related_projects',
  '姓名',
  '性别',
  '身份证号',
  '身份证',
  '工号',
  '员工编号',
  '岗位',
  '岗位类型',
  '职位',
  '职级',
  '常驻地（Base）',
  '常驻地',
  'Base',
  'BASE',
  'Base地',
  'base地',
  '部门',
  '默认部门',
  '所属部门',
  '邮箱',
  '电子邮箱',
  '交通偏好',
  '出行偏好',
  '关联项目',
  '负责项目',
])

const reservedKeyFolded = new Set(
  [...EXTENSION_MEMORY_RESERVED_KEYS].map((key) => key.toLowerCase()),
)

export function isReservedExtensionMemoryKey(key: string): boolean {
  const normalized = key.trim()
  if (!normalized) return true
  if (EXTENSION_MEMORY_RESERVED_KEYS.has(normalized)) return true
  return reservedKeyFolded.has(normalized.toLowerCase())
}

export function filterExtensionMemoryItems<T extends { key: string; value: string }>(
  items: T[],
): T[] {
  return items.filter(
    (item) => item.key.trim() && item.value.trim() && !isReservedExtensionMemoryKey(item.key),
  )
}
