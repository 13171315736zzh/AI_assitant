export type ThemeValue = 'light' | 'dark' | 'system'

export interface MemoryItem {
  key: string
  value: string
}

export interface MemoryStructured {
  display_name: string
  gender: string
  id_number: string
  employee_id: string
  job_role: string
  position: string
  base_location: string
  department: string
  email: string
  travel_mode_preference: string
  related_projects: string[]
}

export interface MemorySettings {
  memory_enabled: boolean
  structured: MemoryStructured
  memory_items: MemoryItem[]
  field_count?: number
}

export interface ProfileSettings {
  username: string
  display_name: string
  role: string
  employee_id: string
}

export interface ChangelogEntry {
  version: string
  date: string
  items: string[]
}

export interface VersionInfo {
  version: string
  release_date: string
  has_update: boolean
  changelog: ChangelogEntry[]
}

export interface VersionCheckResult {
  has_update: boolean
  message: string
}

const mockMemory: MemorySettings = {
  memory_enabled: true,
  structured: {
    display_name: '张明',
    employee_id: '0176338',
    job_role: '产品经理',
    department: '神东煤炭集团',
    position: '其他人员',
    email: 'zhangming@ceic.com',
    travel_mode_preference: '高铁',
    related_projects: ['神东能源数据治理平台'],
    gender: '男',
    id_number: '',
    base_location: '北京',
  },
  memory_items: [
    { key: '常用出差目的地', value: '鄂尔多斯、北京' },
    { key: '常用联系人', value: '李经理（工包审批）' },
    { key: '沟通偏好', value: '简洁回复，优先表格展示' },
    { key: '差旅偏好', value: '优先下午航班，经济舱' },
  ],
}

let themeStore: ThemeValue = 'light'

export function mockGetMemory(): MemorySettings {
  return {
    memory_enabled: mockMemory.memory_enabled,
    structured: { ...mockMemory.structured, related_projects: [...mockMemory.structured.related_projects] },
    memory_items: mockMemory.memory_items.map((item) => ({ ...item })),
  }
}

export function mockUpdateMemory(payload: {
  memory_enabled?: boolean
  structured?: MemoryStructured
  memory_items?: MemoryItem[]
}): MemorySettings {
  if (payload.memory_enabled !== undefined) {
    mockMemory.memory_enabled = payload.memory_enabled
  }
  if (payload.structured !== undefined) {
    mockMemory.structured = {
      ...payload.structured,
      related_projects: [...payload.structured.related_projects],
    }
  }
  if (payload.memory_items !== undefined) {
    mockMemory.memory_items = payload.memory_items.map((item) => ({ ...item }))
  }
  return mockGetMemory()
}

export function mockClearMemory(): { cleared: boolean } {
  mockMemory.memory_items = []
  mockMemory.structured = {
    display_name: '张明',
    employee_id: '0176338',
    job_role: '',
    department: '',
    position: '',
    email: '',
    travel_mode_preference: '',
    related_projects: [],
    gender: 'unknown',
    id_number: '',
    base_location: '',
  }
  return { cleared: true }
}

export function mockGetTheme(): { theme: ThemeValue } {
  return { theme: themeStore }
}

export function mockUpdateTheme(theme: ThemeValue): { theme: ThemeValue } {
  themeStore = theme
  return { theme: themeStore }
}

export function mockGetProfile(): ProfileSettings {
  return {
    username: 'user_a',
    display_name: '张明',
    role: 'employee',
    employee_id: '0176338',
  }
}

export function mockGetVersion(): VersionInfo {
  return {
    version: '1.0.0',
    release_date: '2026-03-20',
    has_update: false,
    changelog: [
      {
        version: '1.0.0',
        date: '2026-03-20',
        items: [
          '首次发布：对话、知识库、差旅/工包/会议/邮件工具',
          '支持个人设置与长期记忆',
          '人工协助 Mock 工单',
        ],
      },
    ],
  }
}

export function mockCheckVersion(): VersionCheckResult {
  return { has_update: false, message: '已是最新版本' }
}
