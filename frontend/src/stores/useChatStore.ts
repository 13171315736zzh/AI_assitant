import { defineStore } from 'pinia'
import { ref, computed, nextTick } from 'vue'
import type { Message, Session } from '@/types'
import {
  fetchSessions,
  fetchMessages,
  createSession,
  endSession,
  deleteSession,
  sendMessageStream,
  clearMemory,
  confirmBookingSelection,
  confirmRoomSelection,
  confirmWorkpackagePlan,
  confirmWorkpackageFill,
  confirmTravelPlan,
  confirmMeetingPlan,
} from '@/services/sessionService'
import { fetchWelcomeMessage } from '@/services/settingsService'
import { DEFAULT_WELCOME_TEXT } from '@/constants/welcomeQuickActions'
import { useAuthStore } from './useAuthStore'

const DEFAULT_WELCOME = DEFAULT_WELCOME_TEXT
const WELCOME_MESSAGE_ID = '__welcome__'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<Session[]>([])
  const activeSessionId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const welcomeMessage = ref(DEFAULT_WELCOME)
  const loading = ref(false)
  const sending = ref(false)
  const deletingSessionId = ref<string | null>(null)
  const workflowSubmitting = ref(false)

  const activeSession = computed(() =>
    sessions.value.find((s) => s.id === activeSessionId.value) ?? null,
  )

  const isActiveSessionEnded = computed(() => activeSession.value?.status === 'ended')

  const displayMessages = computed(() => {
    if (messages.value.length > 0) return messages.value
    const text = welcomeMessage.value.trim()
    if (!text) return []
    return [
      {
        id: WELCOME_MESSAGE_ID,
        session_id: activeSessionId.value ?? '',
        role: 'assistant' as const,
        content: text,
        message_type: 'text' as const,
        metadata: { is_welcome: true },
        created_at: new Date().toISOString(),
      },
    ]
  })

  async function loadWelcomeMessage() {
    try {
      const res = await fetchWelcomeMessage()
      if (res.code === 200 && res.data.welcome_message.trim()) {
        welcomeMessage.value = res.data.welcome_message.trim()
      }
    } catch {
      welcomeMessage.value = DEFAULT_WELCOME
    }
  }

  async function loadSessions() {
    const auth = useAuthStore()
    if (!auth.user) return
    loading.value = true
    try {
      await loadWelcomeMessage()
      const res = await fetchSessions(auth.user.id)
      if (res.code === 200) {
        sessions.value = res.data.items
        const ids = new Set(sessions.value.map((s) => s.id))
        if (!activeSessionId.value || !ids.has(activeSessionId.value)) {
          activeSessionId.value = sessions.value[0]?.id ?? null
          messages.value = []
          if (activeSessionId.value) {
            await loadMessages(activeSessionId.value)
          }
        }
      } else {
        sessions.value = []
        activeSessionId.value = null
        messages.value = []
        alert(res.message || '加载会话失败，请重新登录后再试')
      }
    } finally {
      loading.value = false
    }
  }

  function reset() {
    sessions.value = []
    activeSessionId.value = null
    messages.value = []
    loading.value = false
    sending.value = false
  }

  async function loadMessages(sessionId: string) {
    activeSessionId.value = sessionId
    loading.value = true
    try {
      const res = await fetchMessages(sessionId)
      if (res.code === 200) {
        messages.value = res.data.items.filter((m) => m.message_type !== 'pending')
      }
    } finally {
      loading.value = false
    }
  }

  async function newSession() {
    const auth = useAuthStore()
    if (!auth.user) return false
    const res = await createSession(auth.user.id)
    if (res.code !== 200) {
      alert(res.message || '创建会话失败，请重新登录后再试')
      return false
    }
    sessions.value.unshift(res.data)
    activeSessionId.value = res.data.id
    messages.value = []
    await loadWelcomeMessage()
    return true
  }

  async function endCurrentSession() {
    if (!activeSessionId.value) return
    const res = await endSession(activeSessionId.value)
    if (res.code === 200) {
      const idx = sessions.value.findIndex((s) => s.id === res.data.id)
      if (idx >= 0) sessions.value[idx] = res.data
    }
  }

  async function removeSession(sessionId: string) {
    if (deletingSessionId.value === sessionId) return
    deletingSessionId.value = sessionId
    try {
      const res = await deleteSession(sessionId)
      if (res.code !== 200 || !res.data.deleted) {
        throw new Error(res.message || '删除失败')
      }
      sessions.value = sessions.value.filter((s) => s.id !== sessionId)
      if (activeSessionId.value === sessionId) {
        activeSessionId.value = sessions.value[0]?.id ?? null
        messages.value = []
        if (activeSessionId.value) {
          await loadMessages(activeSessionId.value)
        }
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : '删除失败，请稍后重试'
      throw new Error(message.includes('timeout') ? '删除超时，请稍后重试' : message)
    } finally {
      deletingSessionId.value = null
    }
  }

  async function send(content: string) {
    const trimmed = content.trim()
    if (!trimmed) return

    if (!activeSessionId.value) {
      const created = await newSession()
      if (!created || !activeSessionId.value) return
    }

    const sessionId = activeSessionId.value
    const tempUserId = `temp_u_${Date.now()}`
    const pendingId = `temp_pending_${Date.now()}`
    const now = new Date().toISOString()

    messages.value.push({
      id: tempUserId,
      session_id: sessionId,
      role: 'user',
      content: trimmed,
      message_type: 'text',
      metadata: null,
      created_at: now,
    })
    messages.value.push({
      id: pendingId,
      session_id: sessionId,
      role: 'assistant',
      content: '',
      message_type: 'pending',
      metadata: null,
      created_at: now,
    })
    await nextTick()

    sending.value = true
    try {
      await sendMessageStream(sessionId, trimmed, {
        onUser: (userMessage) => {
          const idx = messages.value.findIndex((m) => m.id === tempUserId)
          if (idx >= 0) {
            messages.value[idx] = userMessage
            return
          }
          if (!messages.value.some((m) => m.id === userMessage.id)) {
            messages.value.push(userMessage)
          }
        },
        onAck: (ackContent) => {
          const existing = messages.value.find((m) => m.id === pendingId)
          if (existing) {
            existing.content = existing.content
              ? `${existing.content}\n${ackContent}`
              : ackContent
            return
          }
          messages.value.push({
            id: pendingId,
            session_id: sessionId,
            role: 'assistant',
            content: ackContent,
            message_type: 'pending',
            metadata: null,
            created_at: new Date().toISOString(),
          })
        },
        onDone: (data) => {
          messages.value = messages.value.filter((m) => m.id !== pendingId)
          const userIdx = messages.value.findIndex(
            (m) => m.id === tempUserId || m.id === data.user_message.id,
          )
          if (userIdx >= 0) {
            messages.value[userIdx] = data.user_message
          } else {
            messages.value.push(data.user_message)
          }
          messages.value.push(data.assistant_message)
          const session = sessions.value.find((s) => s.id === sessionId)
          if (session) {
            session.message_count += 2
            session.updated_at = data.assistant_message.created_at
            if (data.session_title) {
              session.title = data.session_title
            }
          }
        },
        onError: (message) => {
          messages.value = messages.value.filter((m) => m.id !== pendingId)
          alert(message)
        },
      })
    } finally {
      sending.value = false
    }
  }

  async function confirmBooking(payload: {
    messageId: string
    flight_no?: string
    hotel_name?: string
  }) {
    await _confirmWorkflow(payload.messageId, 'booking_selection', () =>
      confirmBookingSelection(activeSessionId.value!, {
        flight_no: payload.flight_no,
        hotel_name: payload.hotel_name,
      }),
    )
  }

  async function confirmRoom(payload: { messageId: string; room: string }) {
    await _confirmWorkflow(payload.messageId, 'room_selection', () =>
      confirmRoomSelection(activeSessionId.value!, payload.room),
    )
  }

  async function confirmWorkpackage(payload: {
    messageId: string
    entries: import('@/types').TimesheetEntry[]
  }) {
    await _confirmWorkflow(payload.messageId, 'workpackage_confirm', () =>
      confirmWorkpackageFill(activeSessionId.value!, { entries: payload.entries }),
    )
  }

  async function confirmWorkpackagePlanAction(payload: { messageId: string; project?: string }) {
    await _confirmWorkflow(payload.messageId, 'workpackage_plan_confirm', () =>
      confirmWorkpackagePlan(activeSessionId.value!, { project: payload.project }),
    )
  }

  async function confirmTravelPlanAction(payload: { messageId: string }) {
    await _confirmWorkflow(payload.messageId, 'travel_plan_confirm', () =>
      confirmTravelPlan(activeSessionId.value!),
    )
  }

  async function confirmMeetingPlanAction(payload: { messageId: string }) {
    await _confirmWorkflow(payload.messageId, 'meeting_plan_confirm', () =>
      confirmMeetingPlan(activeSessionId.value!),
    )
  }

  async function _confirmWorkflow(
    messageId: string,
    metaKey: string,
    apiCall: () => Promise<{
      code: number
      message: string
      data: {
        user_message: Message
        assistant_message: Message
        session_title?: string
      }
    }>,
  ) {
    if (!activeSessionId.value || workflowSubmitting.value) return
    const sessionId = activeSessionId.value
    workflowSubmitting.value = true
    try {
      const res = await apiCall()
      if (res.code !== 200) {
        alert(res.message || '操作失败')
        return
      }
      const idx = messages.value.findIndex((m) => m.id === messageId)
      if (idx >= 0 && messages.value[idx].metadata?.[metaKey]) {
        messages.value[idx] = {
          ...messages.value[idx],
          metadata: {
            ...messages.value[idx].metadata,
            [metaKey]: {
              ...(messages.value[idx].metadata?.[metaKey] as Record<string, unknown>),
              status: 'confirmed',
            },
          },
        }
      }
      messages.value.push(res.data.user_message)
      messages.value.push(res.data.assistant_message)
      const session = sessions.value.find((s) => s.id === sessionId)
      if (session) {
        session.message_count += 2
        session.updated_at = res.data.assistant_message.created_at
        if (res.data.session_title) {
          session.title = res.data.session_title
        }
      }
    } catch {
      alert('操作失败，请稍后重试')
    } finally {
      workflowSubmitting.value = false
    }
  }

  async function clearUserMemory() {
    const res = await clearMemory()
    if (res.code === 200) {
      alert('长期记忆已清除')
    }
  }

  return {
    sessions,
    activeSessionId,
    messages,
    displayMessages,
    welcomeMessage,
    loading,
    sending,
    deletingSessionId,
    workflowSubmitting,
    activeSession,
    isActiveSessionEnded,
    loadSessions,
    reset,
    loadMessages,
    newSession,
    endCurrentSession,
    removeSession,
    send,
    confirmBooking,
    confirmRoom,
    confirmWorkpackage,
    confirmWorkpackagePlan: confirmWorkpackagePlanAction,
    confirmTravelPlan: confirmTravelPlanAction,
    confirmMeetingPlan: confirmMeetingPlanAction,
    clearUserMemory,
  }
})
