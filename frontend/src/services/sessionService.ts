import type { ApiResponse, Message, PaginatedData, Session } from '@/types'
import type { WorkflowCardDraft } from '@/utils/workflowCardDraft'
import { buildCardDraftQueryParam } from '@/utils/workflowCardDraft'
import {
  mockCreateSession,
  mockDeleteSession,
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

export async function deleteSession(
  sessionId: string,
): Promise<ApiResponse<{ deleted: boolean }>> {
  if (isMockMode('sessions')) {
    await delay(150)
    const deleted = mockDeleteSession(sessionId)
    if (!deleted) {
      return { code: 404, message: '会话不存在', data: { deleted: false } }
    }
    return { code: 200, message: 'success', data: { deleted: true } }
  }
  const { data } = await api.delete<ApiResponse<{ deleted: boolean }>>(`/sessions/${sessionId}`, {
    timeout: 30000,
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
  onDone?: (data: {
    user_message: Message
    assistant_message: Message
    session_title?: string
  }) => void
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
  options?: { cardDraft?: WorkflowCardDraft | null },
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
    handlers.onDone?.({
      user_message: result[0],
      assistant_message: result[1],
      session_title: result[2],
    })
    return
  }

  const token = localStorage.getItem('token')
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  const cardDraftParam = buildCardDraftQueryParam(options?.cardDraft ?? null)
  const query = new URLSearchParams({ content })
  if (cardDraftParam) {
    query.set('card_draft', cardDraftParam)
  }
  const url = `${base}/sessions/${encodeURIComponent(sessionId)}/stream?${query.toString()}`
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
          handlers.onDone?.(
            payload as {
              user_message: Message
              assistant_message: Message
              session_title?: string
            },
          )
        } else if (parsed.event === 'error') {
          handlers.onError?.((payload.message as string) ?? '发送失败')
        }
      } catch {
        handlers.onError?.('响应解析失败')
      }
    }
  }
}

export async function confirmBookingSelection(
  sessionId: string,
  payload: { flight_no?: string; train_no?: string; hotel_name?: string; drive?: boolean },
): Promise<
  ApiResponse<{
    user_message: Message
    assistant_message: Message
    session_title?: string
  }>
> {
  const { data } = await api.post(`/sessions/${encodeURIComponent(sessionId)}/booking-selection`, payload)
  return data
}

export async function confirmRoomSelection(
  sessionId: string,
  room: string,
): Promise<
  ApiResponse<{
    user_message: Message
    assistant_message: Message
    session_title?: string
  }>
> {
  const { data } = await api.post(`/sessions/${encodeURIComponent(sessionId)}/room-selection`, { room })
  return data
}

export async function confirmWorkpackagePlan(
  sessionId: string,
  payload?: {
    project?: string
    all_days_eight_hours?: boolean
    hours_per_day?: number
    supplementary_content?: string
  },
): Promise<
  ApiResponse<{
    user_message: Message
    assistant_message: Message
    session_title?: string
  }>
> {
  const { data } = await api.post(
    `/sessions/${encodeURIComponent(sessionId)}/workpackage-plan-confirm`,
    {
      confirmed: true,
      project: payload?.project ?? null,
      all_days_eight_hours: payload?.all_days_eight_hours ?? null,
      hours_per_day: payload?.hours_per_day ?? null,
      supplementary_content: payload?.supplementary_content ?? null,
    },
  )
  return data
}

export async function confirmWorkpackageFill(
  sessionId: string,
  payload?: { entries?: import('@/types').TimesheetEntry[] },
): Promise<
  ApiResponse<{
    user_message: Message
    assistant_message: Message
    session_title?: string
  }>
> {
  const { data } = await api.post(`/sessions/${encodeURIComponent(sessionId)}/workpackage-confirm`, {
    confirmed: true,
    entries: payload?.entries ?? null,
  })
  return data
}

export async function confirmTravelPlan(
  sessionId: string,
  payload?: {
    supplementary_content?: string
    origin?: string
    destination?: string
    start_date?: string
    end_date?: string
    purpose?: string
    transport_mode?: string
    transport_other?: string
    recipient?: string
    cc?: string
    subject?: string
    body?: string
    signature?: string
  },
): Promise<
  ApiResponse<{
    user_message: Message
    assistant_message: Message
    session_title?: string
  }>
> {
  const { data } = await api.post(`/sessions/${encodeURIComponent(sessionId)}/travel-plan-confirm`, {
    confirmed: true,
    supplementary_content: payload?.supplementary_content ?? null,
    origin: payload?.origin ?? null,
    destination: payload?.destination ?? null,
    start_date: payload?.start_date ?? null,
    end_date: payload?.end_date ?? null,
    purpose: payload?.purpose ?? null,
    transport_mode: payload?.transport_mode ?? null,
    transport_other: payload?.transport_other ?? null,
    recipient: payload?.recipient ?? null,
    cc: payload?.cc ?? null,
    subject: payload?.subject ?? null,
    body: payload?.body ?? null,
    signature: payload?.signature ?? null,
  })
  return data
}

export async function confirmMeetingPlan(
  sessionId: string,
  payload?: {
    supplementary_content?: string
    subject?: string
    room?: string | null
    room_flexible?: boolean
    room_preference?: string
    attendees?: string
    date_hint?: string
    start_hint?: string
    end_hint?: string
  },
): Promise<
  ApiResponse<{
    user_message: Message
    assistant_message: Message
    session_title?: string
  }>
> {
  const { data } = await api.post(`/sessions/${encodeURIComponent(sessionId)}/meeting-plan-confirm`, {
    confirmed: true,
    supplementary_content: payload?.supplementary_content ?? null,
    subject: payload?.subject ?? null,
    room: payload?.room ?? null,
    selected_room: payload?.room ?? null,
    room_flexible: payload?.room_flexible ?? null,
    room_preference: payload?.room_preference ?? null,
    attendees: payload?.attendees ?? null,
    date_hint: payload?.date_hint ?? null,
    start_hint: payload?.start_hint ?? null,
    end_hint: payload?.end_hint ?? null,
  })
  return data
}

export async function confirmLeavePlan(
  sessionId: string,
  payload: {
    reason: string
    attachment_name?: string
    leave_type?: string
    date_start?: string
    date_end?: string
    start_period?: string
    end_period?: string
    supplementary_content?: string
  },
): Promise<
  ApiResponse<{
    user_message: Message
    assistant_message: Message
    session_title?: string
  }>
> {
  const { data } = await api.post(`/sessions/${encodeURIComponent(sessionId)}/leave-plan-confirm`, {
    confirmed: true,
    reason: payload.reason,
    attachment_name: payload.attachment_name ?? null,
    leave_type: payload.leave_type ?? null,
    date_start: payload.date_start ?? null,
    date_end: payload.date_end ?? null,
    start_period: payload.start_period ?? null,
    end_period: payload.end_period ?? null,
    supplementary_content: payload.supplementary_content ?? null,
  })
  return data
}

export async function confirmInfoCollectPlan(
  sessionId: string,
  payload: { structured: Record<string, unknown>; supplementary_content?: string },
): Promise<
  ApiResponse<{
    user_message: Message
    assistant_message: Message
    session_title?: string
  }>
> {
  const { data } = await api.post(
    `/sessions/${encodeURIComponent(sessionId)}/info-collect-plan-confirm`,
    {
      confirmed: true,
      structured: payload.structured,
      supplementary_content: payload.supplementary_content ?? null,
    },
  )
  return data
}

export async function confirmMeetingCancelSelection(
  sessionId: string,
  payload: { node_ids: string[] },
): Promise<
  ApiResponse<{
    user_message: Message
    assistant_message: Message
    session_title?: string
  }>
> {
  const { data } = await api.post(
    `/sessions/${encodeURIComponent(sessionId)}/meeting-cancel-selection-confirm`,
    {
      confirmed: true,
      node_ids: payload.node_ids,
    },
  )
  return data
}

export async function requestWorkflowCancelConfirm(
  sessionId: string,
  payload?: { task_id?: string | null; node_id?: string | null },
): Promise<
  ApiResponse<{
    user_message: Message
    assistant_message: Message
    session_title?: string
  }>
> {
  const { data } = await api.post(`/sessions/${encodeURIComponent(sessionId)}/workflow-cancel-request`, {
    task_id: payload?.task_id ?? null,
    node_id: payload?.node_id ?? null,
  })
  return data
}

export async function confirmWorkflowCancel(
  sessionId: string,
  payload: { task_id: string },
): Promise<
  ApiResponse<{
    user_message: Message
    assistant_message: Message
    session_title?: string
  }>
> {
  const { data } = await api.post(`/sessions/${encodeURIComponent(sessionId)}/workflow-cancel-confirm`, {
    confirmed: true,
    task_id: payload.task_id,
  })
  return data
}

/** @deprecated 请使用 requestWorkflowCancelConfirm */
export async function requestRoomCancelConfirm(
  sessionId: string,
  payload?: { task_id?: string | null },
) {
  return requestWorkflowCancelConfirm(sessionId, {
    task_id: payload?.task_id ?? null,
    node_id: 'room',
  })
}

/** @deprecated 请使用 confirmWorkflowCancel */
export async function confirmRoomCancel(
  sessionId: string,
  payload: { task_id: string },
) {
  return confirmWorkflowCancel(sessionId, payload)
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
