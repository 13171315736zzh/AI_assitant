import { defineStore } from 'pinia'
import { ref, computed, nextTick } from 'vue'
import type { Message, Session } from '@/types'
import {
  fetchSessions,
  fetchMessages,
  createSession,
  endSession,
  sendMessageStream,
  clearMemory,
} from '@/services/sessionService'
import { useAuthStore } from './useAuthStore'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<Session[]>([])
  const activeSessionId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const loading = ref(false)
  const sending = ref(false)

  const activeSession = computed(() =>
    sessions.value.find((s) => s.id === activeSessionId.value) ?? null,
  )

  const isActiveSessionEnded = computed(() => activeSession.value?.status === 'ended')

  async function loadSessions() {
    const auth = useAuthStore()
    if (!auth.user) return
    loading.value = true
    try {
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
      }
    } finally {
      loading.value = false
    }
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
    if (!auth.user) return
    const res = await createSession(auth.user.id)
    if (res.code === 200) {
      sessions.value.unshift(res.data)
      activeSessionId.value = res.data.id
      messages.value = []
    }
  }

  async function endCurrentSession() {
    if (!activeSessionId.value) return
    const res = await endSession(activeSessionId.value)
    if (res.code === 200) {
      const idx = sessions.value.findIndex((s) => s.id === res.data.id)
      if (idx >= 0) sessions.value[idx] = res.data
    }
  }

  async function send(content: string) {
    if (!activeSessionId.value || !content.trim()) return
    const sessionId = activeSessionId.value
    const trimmed = content.trim()
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
          }
        },
        onError: (message) => {
          messages.value = messages.value.filter(
            (m) => m.id !== tempUserId && m.id !== pendingId,
          )
          alert(message)
        },
      })
    } finally {
      sending.value = false
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
    loading,
    sending,
    activeSession,
    isActiveSessionEnded,
    loadSessions,
    loadMessages,
    newSession,
    endCurrentSession,
    send,
    clearUserMemory,
  }
})
