import type { Message, PaginatedData, Session } from '@/types'

export const mockSessions: Session[] = [
  {
    id: 'sess_001',
    user_id: 2,
    title: '神东出差安排',
    status: 'active',
    ended_reason: null,
    message_count: 4,
    created_at: '2026-03-20T09:15:00+08:00',
    updated_at: '2026-03-20T14:32:00+08:00',
  },
  {
    id: 'sess_002',
    user_id: 2,
    title: '鄂尔多斯住宿费标准',
    status: 'ended',
    ended_reason: 'completed',
    message_count: 2,
    created_at: '2026-03-19T10:15:00+08:00',
    updated_at: '2026-03-19T10:45:00+08:00',
  },
  {
    id: 'sess_003',
    user_id: 2,
    title: '本周工包填报',
    status: 'ended',
    ended_reason: 'manual',
    message_count: 6,
    created_at: '2026-03-18T16:00:00+08:00',
    updated_at: '2026-03-18T17:30:00+08:00',
  },
]

export const mockMessagesBySession: Record<string, Message[]> = {
  sess_001: [
    {
      id: 'msg_001',
      session_id: 'sess_001',
      role: 'user',
      content: '下周三去神东项目出差，帮我安排差旅申请和机票',
      message_type: 'text',
      metadata: null,
      created_at: '2026-03-20T09:15:00+08:00',
    },
    {
      id: 'msg_002',
      session_id: 'sess_001',
      role: 'assistant',
      content: '好的，我已开始为您安排。请先确认以下信息…',
      message_type: 'task',
      metadata: {
        task_id: 'task_001',
        task_title: '神东出差差旅安排',
        progress: '2/4',
        progress_percent: 50,
        steps_desc: '差旅申请创建 · 机票预订 · 酒店预订 · 用户确认',
      },
      created_at: '2026-03-20T09:15:05+08:00',
    },
    {
      id: 'msg_003',
      session_id: 'sess_001',
      role: 'user',
      content: '经济舱即可，需要订酒店',
      message_type: 'text',
      metadata: null,
      created_at: '2026-03-20T09:20:00+08:00',
    },
    {
      id: 'msg_004',
      session_id: 'sess_001',
      role: 'assistant',
      content: '已记录您的偏好。差旅申请已提交（单号 TA20260325001），正在查询机票…',
      message_type: 'text',
      metadata: null,
      created_at: '2026-03-20T09:20:05+08:00',
    },
  ],
  sess_002: [
    {
      id: 'msg_101',
      session_id: 'sess_002',
      role: 'user',
      content: '鄂尔多斯出差住宿费标准是多少？',
      message_type: 'text',
      metadata: null,
      created_at: '2026-03-19T10:15:00+08:00',
    },
    {
      id: 'msg_102',
      session_id: 'sess_002',
      role: 'assistant',
      content:
        '根据《国家能源集团差旅管理办法》第三章第十二条，其他人员鄂尔多斯地区住宿费不超过 300 元/天。',
      message_type: 'text',
      metadata: {
        sources: [{ filename: '国家能源集团差旅管理办法2024修订版.pdf', clause: '第三章第十二条' }],
      },
      created_at: '2026-03-19T10:15:10+08:00',
    },
  ],
  sess_003: [
    {
      id: 'msg_201',
      session_id: 'sess_003',
      role: 'user',
      content: '帮我填报本周工包',
      message_type: 'text',
      metadata: null,
      created_at: '2026-03-18T16:00:00+08:00',
    },
    {
      id: 'msg_202',
      session_id: 'sess_003',
      role: 'assistant',
      content: '工包填报已完成，会话已结束。',
      message_type: 'text',
      metadata: null,
      created_at: '2026-03-18T17:30:00+08:00',
    },
  ],
}

export function mockSessionList(userId: number): PaginatedData<Session> {
  const items = mockSessions.filter((s) => s.user_id === userId)
  return { items, total: items.length, page: 1, page_size: 20 }
}

export function mockMessages(sessionId: string): PaginatedData<Message> {
  const items = mockMessagesBySession[sessionId] ?? []
  return { items, total: items.length, page: 1, page_size: 50 }
}

let sessionCounter = 100

export function mockCreateSession(userId: number, title = '新对话'): Session {
  sessionCounter += 1
  const session: Session = {
    id: `sess_new_${sessionCounter}`,
    user_id: userId,
    title,
    status: 'active',
    ended_reason: null,
    message_count: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
  mockSessions.unshift(session)
  mockMessagesBySession[session.id] = []
  return session
}

export function mockEndSession(sessionId: string): Session | null {
  const session = mockSessions.find((s) => s.id === sessionId)
  if (!session) return null
  session.status = 'ended'
  session.ended_reason = 'manual'
  session.updated_at = new Date().toISOString()
  return session
}

export function mockSendMessage(sessionId: string, content: string): Message[] | null {
  const session = mockSessions.find((s) => s.id === sessionId)
  if (!session || session.status === 'ended') return null

  const list = mockMessagesBySession[sessionId] ?? []
  const now = new Date().toISOString()
  const userMsg: Message = {
    id: `msg_u_${Date.now()}`,
    session_id: sessionId,
    role: 'user',
    content,
    message_type: 'text',
    metadata: null,
    created_at: now,
  }
  const assistantMsg: Message = {
    id: `msg_a_${Date.now()}`,
    session_id: sessionId,
    role: 'assistant',
    content: buildMockAssistantReply(content),
    message_type: 'text',
    metadata: null,
    created_at: now,
  }
  list.push(userMsg, assistantMsg)
  mockMessagesBySession[sessionId] = list
  session.message_count = list.length
  session.updated_at = now
  return [userMsg, assistantMsg]
}

export function mockClearMemory(): { cleared: boolean } {
  return { cleared: true }
}

function buildMockAssistantReply(content: string): string {
  const parts = content
    .split(/[？?。；;]/)
    .map((p) => p.trim())
    .filter(Boolean)
  if (parts.length <= 1) {
    return `关于「${content.slice(0, 48)}${content.length > 48 ? '…' : ''}」，我已整理相关信息，请查看上方说明或继续补充需求。`
  }
  const labels = ['一、', '二、', '三、']
  return parts
    .slice(0, 3)
    .map((part, idx) => `${labels[idx] ?? `${idx + 1}、`}${part}的相关说明已整理，如需进一步操作请告诉我。`)
    .join('\n\n')
}
