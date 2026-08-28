import type { ApiResponse, Message, PaginatedData, Session } from '@/types'
import {
  mockCreateSession,
  mockEndSession,
  mockMessages,
  mockSendMessage,
  mockSessionList,
} from '@/mocks/sessions'
import api, { isMockMode } from './api'
import { clearUserMemory } from './settingsService'

export async function fetchSessions(userId: number): Promise<ApiResponse<PaginatedData<Session>>> {
  if (isMockMode('sessions')) {
    await delay(200)
    return { code: 200, message: 'success', data: mockSessionList(userId) }
  }
  const { data } = await api.get<ApiResponse<PaginatedData<Session>>>('/sessions')
  return data
}

export async function fetchMessages(sessionId: string): Promise<ApiResponse<PaginatedData<Message>>> {
  if (isMockMode('sessions')) {
    await delay(150)
    return { code: 200, message: 'success', data: mockMessages(sessionId) }
  }
  const { data } = await api.get<ApiResponse<PaginatedData<Message>>>(`/sessions/${sessionId}/messages`)
  return data
}

export async function createSession(userId: number, title?: string): Promise<ApiResponse<Session>> {
  if (isMockMode('sessions')) {
    await delay(200)
    return { code: 200, message: 'success', data: mockCreateSession(userId, title) }
  }
  const { data } = await api.post<ApiResponse<Session>>('/sessions', { title })
  return data
}

export async function endSession(sessionId: string): Promise<ApiResponse<Session>> {
  if (isMockMode('sessions')) {
    const updated = mockEndSession(sessionId)
    if (!updated) {
      return { code: 404, message: '会话不存在', data: null as unknown as Session }
    }
    return { code: 200, message: 'success', data: updated }
  }
  const { data } = await api.patch<ApiResponse<Session>>(`/sessions/${sessionId}`, {
    status: 'ended',
    ended_reason: 'manual',
  })
  return data
}

export async function sendMessage(
  sessionId: string,
  content: string,
): Promise<ApiResponse<{ user_message: Message; assistant_message: Message }>> {
  if (isMockMode('sessions')) {
    await delay(400)
    const result = mockSendMessage(sessionId, content)
    if (!result) {
      return {
        code: 400,
        message: '会话已结束，无法发送新消息',
        data: null as unknown as { user_message: Message; assistant_message: Message },
      }
    }
    return {
      code: 200,
      message: 'success',
      data: { user_message: result[0], assistant_message: result[1] },
    }
  }
  const { data } = await api.post(`/sessions/${sessionId}/messages`, { content })
  return data
}

export interface StreamMessageHandlers {
  onUser?: (message: Message) => void
  onAck?: (content: string) => void
  onDone?: (data: { user_message: Message; assistant_message: Message }) => void
  onError?: (message: string) => void
}

function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = 'message'
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) data += line.slice(5).trim()
  }
  if (!data) return null
  return { event, data }
}

export async function sendMessageStream(
  sessionId: string,
  content: string,
  handlers: StreamMessageHandlers,
): Promise<void> {
  if (isMockMode('sessions')) {
    const result = mockSendMessage(sessionId, content)
    if (!result) {
      handlers.onError?.('会话已结束，无法发送新消息')
      return
    }
    handlers.onUser?.(result[0])
    await delay(50)
    const acks = buildMockAcks(content)
    for (const ack of acks) {
      handlers.onAck?.(ack)
      await delay(ack === acks[acks.length - 1] ? 400 : 280)
    }
    handlers.onDone?.({ user_message: result[0], assistant_message: result[1] })
    return
  }

  const token = localStorage.getItem('token')
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  const url = `${base}/sessions/${encodeURIComponent(sessionId)}/stream?content=${encodeURIComponent(content)}`
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok || !res.body) {
    handlers.onError?.('发送失败，请稍后重试')
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      const parsed = parseSseBlock(part.trim())
      if (!parsed) continue
      try {
        const payload = JSON.parse(parsed.data) as Record<string, unknown>
        if (parsed.event === 'user') {
          handlers.onUser?.(payload.user_message as Message)
        } else if (parsed.event === 'ack' && typeof payload.content === 'string') {
          handlers.onAck?.(payload.content)
        } else if (parsed.event === 'done') {
          handlers.onDone?.(payload as { user_message: Message; assistant_message: Message })
        } else if (parsed.event === 'error') {
          handlers.onError?.((payload.message as string) ?? '发送失败')
        }
      } catch {
        handlers.onError?.('响应解析失败')
      }
    }
  }
}

export async function clearMemory(): Promise<ApiResponse<{ cleared: boolean }>> {
  return clearUserMemory()
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function buildMockAcks(content: string): string[] {
  const parts = content
    .split(/[？?。；;]/)
    .map((p) => p.trim())
    .filter(Boolean)
  if (parts.length <= 1) {
    const brief = content.slice(0, 40)
    return [`好的，我会帮您处理：${brief}${content.length > 40 ? '…' : ''}`]
  }
  const prefixes = ['好的，', '接着，', '另外，']
  return parts.slice(0, 3).map((part, idx) => {
    const prefix = prefixes[idx] ?? '另外，'
    const brief = part.slice(0, 36)
    return `${prefix}我会帮您处理：${brief}${part.length > 36 ? '…' : ''}`
  })
}
