import { defineStore } from 'pinia'
import { ref, computed, nextTick } from 'vue'
import type { EmailComposeMeta, Message, Session, Task } from '@/types'
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
  confirmLeavePlan,
  confirmInfoCollectPlan,
} from '@/services/sessionService'
import { fetchWelcomeMessage } from '@/services/settingsService'
import { DEFAULT_WELCOME_TEXT } from '@/constants/welcomeQuickActions'
import {
  findPendingWorkflowCard,
  type WorkflowCardDraft,
} from '@/utils/workflowCardDraft'
import { openMailCompose, saveMailPrefill } from '@/utils/emailMail'
import type { OaDemoPayload } from '@/utils/oaDemo'
import { useAuthStore } from './useAuthStore'

const DEFAULT_WELCOME = DEFAULT_WELCOME_TEXT
const WELCOME_MESSAGE_ID = '__welcome__'
const NEW_SESSION_DRAFT_KEY = '__new__'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<Session[]>([])
  const activeSessionId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const welcomeMessage = ref(DEFAULT_WELCOME)
  const loading = ref(false)
  const sending = ref(false)
  const deletingSessionId = ref<string | null>(null)
  const workflowSubmitting = ref(false)
  const inputDrafts = ref<Record<string, string>>({})
  const workflowCardDrafts = ref<Record<string, WorkflowCardDraft>>({})

  const activeSession = computed(() =>
    sessions.value.find((s) => s.id === activeSessionId.value) ?? null,
  )

  const isActiveSessionEnded = computed(() => activeSession.value?.status === 'ended')

  const activeInputDraft = computed({
    get() {
      const key = activeSessionId.value ?? NEW_SESSION_DRAFT_KEY
      return inputDrafts.value[key] ?? ''
    },
    set(value: string) {
      const key = activeSessionId.value ?? NEW_SESSION_DRAFT_KEY
      const next = { ...inputDrafts.value }
      if (!value) {
        delete next[key]
      } else {
        next[key] = value
      }
      inputDrafts.value = next
    },
  })

  function clearInputDraft(sessionId: string) {
    if (!(sessionId in inputDrafts.value)) return
    const next = { ...inputDrafts.value }
    delete next[sessionId]
    inputDrafts.value = next
  }

  function setWorkflowCardDraft(draft: WorkflowCardDraft) {
    workflowCardDrafts.value = {
      ...workflowCardDrafts.value,
      [`${draft.messageId}:${draft.metaKey}`]: draft,
    }
  }

  function getActiveWorkflowCardDraft(): WorkflowCardDraft | null {
    const pending = findPendingWorkflowCard(messages.value)
    if (!pending) return null
    return workflowCardDrafts.value[`${pending.messageId}:${pending.metaKey}`] ?? null
  }

  function takeSupplementaryInput(): string {
    const sessionId = activeSessionId.value
    if (!sessionId) return ''
    const text = activeInputDraft.value.trim()
    if (text) clearInputDraft(sessionId)
    return text
  }

  function migrateNewSessionDraft(sessionId: string) {
    const pendingDraft = inputDrafts.value[NEW_SESSION_DRAFT_KEY]
    if (!pendingDraft) return
    const next = { ...inputDrafts.value }
    delete next[NEW_SESSION_DRAFT_KEY]
    next[sessionId] = pendingDraft
    inputDrafts.value = next
  }

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
    inputDrafts.value = {}
    workflowCardDrafts.value = {}
    loading.value = false
    sending.value = false
  }

  async function loadMessages(sessionId: string, options?: { silent?: boolean }) {
    activeSessionId.value = sessionId
    if (!options?.silent) {
      loading.value = true
    }
    try {
      const res = await fetchMessages(sessionId)
      if (res.code === 200) {
        messages.value = res.data.items.filter((m) => m.message_type !== 'pending')
      }
    } finally {
      if (!options?.silent) {
        loading.value = false
      }
    }
  }

  function patchTaskMessageMetadata(taskId: string, task: Task) {
    const completedCount = task.steps.filter((step) => step.status === 'completed').length
    const total = task.total_steps || task.steps.length
    const isCompleted = task.status === 'completed'

    messages.value = messages.value.map((msg) => {
      const meta = msg.metadata
      if (!meta || meta.task_id !== taskId) return msg
      return {
        ...msg,
        metadata: {
          ...meta,
          progress: isCompleted ? `${total}/${total}` : `${completedCount}/${total}`,
          progress_percent: isCompleted ? 100 : meta.progress_percent,
          status: isCompleted ? 'completed' : meta.status,
          steps_desc: isCompleted && meta.steps_desc && !String(meta.steps_desc).includes('已完成')
            ? `${String(meta.steps_desc).replace(/ · 进行中$/, '')} · 已完成`
            : meta.steps_desc,
        },
      }
    })
  }

  function appendAssistantMessageIfNew(message: Message) {
    if (messages.value.some((item) => item.id === message.id)) return
    messages.value = [...messages.value, message]
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
    migrateNewSessionDraft(res.data.id)
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
      clearInputDraft(sessionId)
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

    const sessionId = activeSessionId.value!
    clearInputDraft(sessionId)
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
      const cardDraft = getActiveWorkflowCardDraft()
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
      }, { cardDraft })
    } finally {
      sending.value = false
    }
  }

  async function confirmBooking(payload: {
    messageId: string
    flight_no?: string
    train_no?: string
    hotel_name?: string
  }) {
    await _confirmWorkflow(payload.messageId, 'booking_selection', () =>
      confirmBookingSelection(activeSessionId.value!, {
        flight_no: payload.flight_no,
        train_no: payload.train_no,
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

  async function confirmWorkpackagePlanAction(payload: {
    messageId: string
    project?: string
    all_days_eight_hours?: boolean
    hours_per_day?: number
  }) {
    const supplementary = takeSupplementaryInput()
    const draft = workflowCardDrafts.value[`${payload.messageId}:workpackage_plan_confirm`]
    const draftPayload = draft?.payload ?? {}
    await _confirmWorkflow(payload.messageId, 'workpackage_plan_confirm', () =>
      confirmWorkpackagePlan(activeSessionId.value!, {
        project: payload.project ?? (draftPayload.project as string | undefined),
        all_days_eight_hours:
          payload.all_days_eight_hours
          ?? (draftPayload.all_days_eight_hours as boolean | undefined),
        hours_per_day:
          payload.hours_per_day ?? (draftPayload.hours_per_day as number | undefined),
        supplementary_content: supplementary || undefined,
      }),
    )
  }

  async function confirmTravelPlanAction(payload: {
    messageId: string
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
  }) {
    const supplementary = takeSupplementaryInput()
    const draft = workflowCardDrafts.value[`${payload.messageId}:travel_plan_confirm`]
    const draftPayload = draft?.payload ?? {}
    const travelFields = {
      origin: payload.origin ?? (draftPayload.origin as string | undefined),
      destination: payload.destination ?? (draftPayload.destination as string | undefined),
      start_date: payload.start_date ?? (draftPayload.start_date as string | undefined),
      end_date: payload.end_date ?? (draftPayload.end_date as string | undefined),
      purpose: payload.purpose ?? (draftPayload.purpose as string | undefined),
      transport_mode: payload.transport_mode ?? (draftPayload.transport_mode as string | undefined),
      transport_other: payload.transport_other ?? (draftPayload.transport_other as string | undefined),
    }
    const emailFields = {
      recipient: payload.recipient ?? (draftPayload.recipient as string | undefined) ?? '',
      cc: payload.cc ?? (draftPayload.cc as string | undefined) ?? '',
      subject: payload.subject ?? (draftPayload.subject as string | undefined) ?? '',
      body: payload.body ?? (draftPayload.body as string | undefined) ?? '',
      signature: payload.signature ?? (draftPayload.signature as string | undefined) ?? '',
    }
    const assistantMessage = await _confirmWorkflow(payload.messageId, 'travel_plan_confirm', async () =>
      confirmTravelPlan(activeSessionId.value!, {
        supplementary_content: supplementary || undefined,
        ...travelFields,
        ...emailFields,
      }),
    )
    if (!assistantMessage) return

    const confirmedCard = messages.value.find((m) => m.id === payload.messageId)
    const isEmailOnly = Boolean(
      (confirmedCard?.metadata?.travel_plan_confirm as { email_only?: boolean } | undefined)
        ?.email_only,
    )
    const meta = assistantMessage.metadata ?? {}
    const emailCompose = meta.email_compose as EmailComposeMeta | undefined
    const taskId = (emailCompose?.task_id ?? meta.task_id) as string | undefined
    if (taskId && isEmailOnly) {
      saveMailPrefill(taskId, emailCompose ?? {
        task_id: taskId,
        session_id: activeSessionId.value ?? undefined,
        recipient: emailFields.recipient,
        cc: emailFields.cc,
        subject: emailFields.subject,
        body: emailFields.body,
        signature: emailFields.signature,
      })
      openMailCompose(taskId)
    }
  }

  async function confirmMeetingPlanAction(payload: {
    messageId: string
    supplementary_content?: string
    subject?: string
    room?: string | null
    room_flexible?: boolean
    attendees?: string
    date_hint?: string
    start_hint?: string
    end_hint?: string
  }) {
    const inputExtra = takeSupplementaryInput()
    const draft = workflowCardDrafts.value[`${payload.messageId}:meeting_plan_confirm`]
    const draftPayload = draft?.payload ?? {}
    const supplementaryParts = [
      payload.supplementary_content,
      draftPayload.supplementary_content as string | undefined,
      inputExtra,
    ].filter(Boolean)
    await _confirmWorkflow(payload.messageId, 'meeting_plan_confirm', () =>
      confirmMeetingPlan(activeSessionId.value!, {
        supplementary_content: supplementaryParts.length
          ? supplementaryParts.join('，')
          : undefined,
        subject: payload.subject ?? (draftPayload.subject as string | undefined),
        room: payload.room ?? (draftPayload.room as string | null | undefined),
        room_flexible: payload.room_flexible ?? (draftPayload.room_flexible as boolean | undefined),
        attendees: payload.attendees ?? (draftPayload.attendees as string | undefined),
        date_hint: payload.date_hint ?? (draftPayload.date_hint as string | undefined),
        start_hint: payload.start_hint ?? (draftPayload.start_hint as string | undefined),
        end_hint: payload.end_hint ?? (draftPayload.end_hint as string | undefined),
      }),
    )
  }

  async function confirmLeavePlanAction(payload: {
    messageId: string
    reason: string
    attachment_name?: string
    leave_type?: string
    date_start?: string
    date_end?: string
    start_period?: string
    end_period?: string
  }) {
    const supplementary = takeSupplementaryInput()
    const draft = workflowCardDrafts.value[`${payload.messageId}:leave_plan_confirm`]
    const draftPayload = draft?.payload ?? {}
    await _confirmWorkflow(payload.messageId, 'leave_plan_confirm', () =>
      confirmLeavePlan(activeSessionId.value!, {
        reason: payload.reason || (draftPayload.reason as string) || '',
        attachment_name: payload.attachment_name ?? (draftPayload.attachment_name as string | undefined),
        leave_type: payload.leave_type ?? (draftPayload.leave_type as string | undefined),
        date_start: payload.date_start ?? (draftPayload.date_start as string | undefined),
        date_end: payload.date_end ?? (draftPayload.date_end as string | undefined),
        start_period: payload.start_period ?? (draftPayload.start_period as string | undefined),
        end_period: payload.end_period ?? (draftPayload.end_period as string | undefined),
        supplementary_content: supplementary || undefined,
      }),
    )
  }

  async function confirmInfoCollectPlanAction(payload: {
    messageId: string
    structured: import('@/mocks/settings').MemoryStructured
  }) {
    const inputExtra = takeSupplementaryInput()
    const draft = workflowCardDrafts.value[`${payload.messageId}:info_collect_plan_confirm`]
    const draftStructured = draft?.payload?.structured as
      import('@/mocks/settings').MemoryStructured | undefined
    const structured = draftStructured
      ? { ...payload.structured, ...draftStructured, related_projects: draftStructured.related_projects?.length
          ? [...draftStructured.related_projects]
          : payload.structured.related_projects }
      : payload.structured
    await _confirmWorkflow(payload.messageId, 'info_collect_plan_confirm', () =>
      confirmInfoCollectPlan(activeSessionId.value!, {
        structured,
        supplementary_content: inputExtra || undefined,
      }),
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
  ): Promise<Message | null> {
    if (!activeSessionId.value || workflowSubmitting.value) return null
    const sessionId = activeSessionId.value
    workflowSubmitting.value = true
    try {
      const res = await apiCall()
      if (res.code !== 200) {
        alert(res.message || '操作失败')
        return null
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
      return res.data.assistant_message
    } catch {
      alert('操作失败，请稍后重试')
      return null
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

  async function handleOaTaskUpdate(payload: OaDemoPayload) {
    if (activeSessionId.value !== payload.sessionId) return

    if (payload.assistantMessage) {
      appendAssistantMessageIfNew(payload.assistantMessage)
    }
    if (payload.task) {
      patchTaskMessageMetadata(payload.taskId, payload.task)
    }

    await loadMessages(payload.sessionId, { silent: true })
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
    activeInputDraft,
    setWorkflowCardDraft,
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
    confirmLeavePlan: confirmLeavePlanAction,
    confirmInfoCollectPlan: confirmInfoCollectPlanAction,
    clearUserMemory,
    handleOaTaskUpdate,
  }
})
