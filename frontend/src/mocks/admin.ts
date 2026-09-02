import type { PaginatedData } from '@/types'

export interface AdminDocument {
  id: string
  filename: string
  file_type: string
  status: 'ready' | 'uploading' | 'parsing' | 'indexing' | 'qa_generating' | 'failed'
  uploaded_by: string
  created_at: string
  progress_percent?: number
}

export interface AdminQA {
  id: string
  document_id: string
  question: string
  answer: string
  source_clause: string
}

export interface ConversationStats {
  total_sessions: number
  active_sessions: number
  today_new_sessions: number
}

export interface AdminConversation {
  id: string
  user: { display_name: string; employee_id: string }
  title: string
  status: 'active' | 'ended'
  message_count: number
  created_at: string
  updated_at: string
}

export interface ConversationMessagePreview {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface AdminConversationDetail extends AdminConversation {
  ended_reason: 'completed' | 'manual' | null
  messages: ConversationMessagePreview[]
  task_summary: string | null
}

export interface SystemConfig {
  system_name: string
  welcome_message: string
  default_model: string
  temperature: number
  session_retention_days: number
  max_concurrent_sessions: number
  log_level: string
  api_timeout_seconds: number
}

export const mockAdminDocuments: AdminDocument[] = [
  {
    id: 'doc_001',
    filename: '国家能源集团差旅管理办法2024修订版.pdf',
    file_type: 'pdf',
    status: 'ready',
    uploaded_by: 'admin',
    created_at: '2026-03-01T00:00:00+08:00',
  },
  {
    id: 'doc_002',
    filename: '差旅报销实施细则.docx',
    file_type: 'docx',
    status: 'indexing',
    uploaded_by: 'admin',
    created_at: '2026-03-20T00:00:00+08:00',
    progress_percent: 67,
  },
]

export const mockAdminQA: AdminQA[] = [
  {
    id: 'qa_001',
    document_id: 'doc_001',
    question: '鄂尔多斯住宿费标准是多少？',
    answer: '其他人员不超过300元/天',
    source_clause: '差旅管理办法·第十二条',
  },
  {
    id: 'qa_002',
    document_id: 'doc_001',
    question: '出差伙食补助标准是多少？',
    answer: '国内出差伙食补助费标准为100元/天',
    source_clause: '差旅管理办法·第十五条',
  },
]

export const mockConversationStats: ConversationStats = {
  total_sessions: 1248,
  active_sessions: 36,
  today_new_sessions: 89,
}

export const mockAdminConversations: AdminConversation[] = [
  {
    id: 'sess_001',
    user: { display_name: '张明', employee_id: '0176338' },
    title: '神东出差差旅安排',
    status: 'active',
    message_count: 24,
    created_at: '2026-03-20T09:15:00+08:00',
    updated_at: '2026-03-20T10:32:00+08:00',
  },
  {
    id: 'sess_002',
    user: { display_name: '李华', employee_id: '0176401' },
    title: '工包填报咨询',
    status: 'ended',
    message_count: 12,
    created_at: '2026-03-19T14:20:00+08:00',
    updated_at: '2026-03-19T15:08:00+08:00',
  },
  {
    id: 'sess_003',
    user: { display_name: '王芳', employee_id: '0176522' },
    title: '会议预约帮助',
    status: 'active',
    message_count: 8,
    created_at: '2026-03-20T08:40:00+08:00',
    updated_at: '2026-03-20T09:55:00+08:00',
  },
  {
    id: 'sess_004',
    user: { display_name: '赵强', employee_id: '0176588' },
    title: '差旅政策查询',
    status: 'ended',
    message_count: 6,
    created_at: '2026-03-18T16:30:00+08:00',
    updated_at: '2026-03-18T16:45:00+08:00',
  },
  {
    id: 'sess_005',
    user: { display_name: '陈静', employee_id: '0176610' },
    title: '邮件撰写协助',
    status: 'active',
    message_count: 15,
    created_at: '2026-03-20T11:00:00+08:00',
    updated_at: '2026-03-20T11:28:00+08:00',
  },
]

export let mockSystemConfig: SystemConfig = {
  system_name: '智能办公助手 · 国能集团',
  welcome_message: '您好，我是国能办公助手，有什么可以帮您？',
  default_model: 'qwen-max',
  temperature: 0.7,
  session_retention_days: 90,
  max_concurrent_sessions: 3,
  log_level: 'INFO',
  api_timeout_seconds: 60,
}

export function mockAdminDocumentsList(): PaginatedData<AdminDocument> {
  return { items: mockAdminDocuments, total: mockAdminDocuments.length, page: 1, page_size: 20 }
}

export function mockAdminQAList(keyword?: string): PaginatedData<AdminQA> {
  let items = mockAdminQA
  if (keyword) {
    items = items.filter((i) => i.question.includes(keyword) || i.answer.includes(keyword))
  }
  return { items, total: items.length, page: 1, page_size: 20 }
}

export function mockSearchTest(query: string) {
  return {
    results: mockAdminQA
      .filter((i) => i.question.includes(query) || query.includes('鄂尔多斯'))
      .map((i) => ({
        type: 'qa' as const,
        question: i.question,
        answer: i.answer,
        similarity: 0.92,
        source_clause: i.source_clause,
      })),
  }
}

export function mockConversationsList(keyword?: string, status?: string): PaginatedData<AdminConversation> {
  let items = mockAdminConversations
  if (keyword) {
    items = items.filter(
      (i) => i.title.includes(keyword) || i.user.display_name.includes(keyword),
    )
  }
  if (status) {
    items = items.filter((i) => i.status === status)
  }
  return { items, total: items.length, page: 1, page_size: 20 }
}

export function mockUpdateSystemConfig(config: Partial<SystemConfig>): SystemConfig {
  mockSystemConfig = { ...mockSystemConfig, ...config }
  return mockSystemConfig
}

const mockConversationDetails: Record<string, Omit<AdminConversationDetail, keyof AdminConversation> & Partial<AdminConversation>> = {
  sess_001: {
    ended_reason: null,
    task_summary: '神东出差差旅安排 · 2/4 步骤进行中',
    messages: [
      { role: 'user', content: '下周三去神东项目出差，帮我安排差旅申请和机票', created_at: '2026-03-20T09:15:00+08:00' },
      { role: 'assistant', content: '好的，我已开始为您安排。请先确认以下信息…', created_at: '2026-03-20T09:15:05+08:00' },
      { role: 'user', content: '经济舱即可，需要订酒店', created_at: '2026-03-20T09:20:00+08:00' },
      { role: 'assistant', content: '已记录您的偏好。差旅申请已提交（单号 TA20260325001），正在查询机票…', created_at: '2026-03-20T09:20:05+08:00' },
    ],
  },
  sess_002: {
    ended_reason: 'completed',
    task_summary: null,
    messages: [
      { role: 'user', content: '本周工包怎么填报？', created_at: '2026-03-19T14:20:00+08:00' },
      { role: 'assistant', content: '工包填报需填写项目名称、工时及工作内容。是否需要我帮您打开填报表单？', created_at: '2026-03-19T14:20:10+08:00' },
      { role: 'user', content: '好的，帮我填一下', created_at: '2026-03-19T14:35:00+08:00' },
      { role: 'assistant', content: '工包填报已完成，会话已结束。', created_at: '2026-03-19T15:08:00+08:00' },
    ],
  },
  sess_003: {
    ended_reason: null,
    task_summary: null,
    messages: [
      { role: 'user', content: '帮我预约明天下午的项目评审会', created_at: '2026-03-20T08:40:00+08:00' },
      { role: 'assistant', content: '请确认：会议主题、参会人员及会议室偏好。', created_at: '2026-03-20T08:40:08+08:00' },
    ],
  },
  sess_004: {
    ended_reason: 'completed',
    task_summary: null,
    messages: [
      { role: 'user', content: '鄂尔多斯出差住宿费标准是多少？', created_at: '2026-03-18T16:30:00+08:00' },
      { role: 'assistant', content: '根据《差旅管理办法》第十二条，其他人员不超过 300 元/天。', created_at: '2026-03-18T16:45:00+08:00' },
    ],
  },
  sess_005: {
    ended_reason: null,
    task_summary: null,
    messages: [
      { role: 'user', content: '帮我写一封给李经理的出差确认邮件', created_at: '2026-03-20T11:00:00+08:00' },
      { role: 'assistant', content: '已为您生成邮件草稿，请确认收件人和正文后发送。', created_at: '2026-03-20T11:05:00+08:00' },
    ],
  },
}

export function mockGetConversationDetail(sessionId: string): AdminConversationDetail | null {
  const base = mockAdminConversations.find((c) => c.id === sessionId)
  const extra = mockConversationDetails[sessionId]
  if (!base || !extra) return null
  return {
    ...base,
    ended_reason: extra.ended_reason ?? null,
    messages: extra.messages ?? [],
    task_summary: extra.task_summary ?? null,
  }
}
