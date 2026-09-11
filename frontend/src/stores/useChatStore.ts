import { defineStore } from 'pinia'
import { ref, computed, nextTick } from 'vue'
import type { EmailComposeMeta, Message, Session, Task, WorkflowPlan } from '@/types'
import {
  fetchSessions,
  fetchMessages,
  createSession,
  endSession,
  deleteSession,
  sendMessage,
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
  requestWorkflowCancelConfirm,
  confirmWorkflowCancel,
  confirmMeetingCancelSelection,
  activateWorkflowNode as activateWorkflowNodeApi,
} from '@/services/sessionService'
import { fetchWelcomeMessage } from '@/services/settingsService'
import { DEFAULT_WELCOME_TEXT } from '@/constants/welcomeQuickActions'
import {
  findPendingWorkflowCard,
  type WorkflowCardDraft,
  type WorkflowPlanConfirmKey,
} from '@/utils/workflowCardDraft'
import {
  applyCancelledNodesToWorkflowPlan,
  applyWorkflowPlanToMessages,
} from '@/utils/workflowPlan'
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

  function getWorkflowCardDraft(
    messageId: string,
    metaKey: WorkflowPlanConfirmKey,
  ): Record<string, unknown> | null {
    const draft = workflowCardDrafts.value[`${messageId}:${metaKey}`]
    return draft?.payload ?? null
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
    workflowSubmitting.value = false
  }

  function applySendResult(
    sessionId: string,
    tempUserId: string,
    pendingId: string,
    data: { user_message: Message; assistant_message: Message; session_title?: string },
  ) {
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
    syncWorkflowPlanFromAssistantMessage(data.assistant_message)
    const session = sessions.value.find((s) => s.id === sessionId)
    if (session) {
      session.message_count += 2
      session.updated_at = data.assistant_message.created_at
      if (data.session_title) {
        session.title = data.session_title
      }
    }
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

  async function send(content: string, options?: { useCardDraft?: boolean }) {
    const trimmed = content.trim()
    if (!trimmed) return
    if (sending.value) {
      window.alert('正在处理上一条消息，请稍候…')
      return
    }

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

    const useCardDraft = options?.useCardDraft !== false
    const cardDraft = useCardDraft ? getActiveWorkflowCardDraft() : null

    sending.value = true
    try {
      if (!cardDraft) {
        const res = await sendMessage(sessionId, trimmed)
        if (res.code !== 200) {
          messages.value = messages.value.filter(
            (m) => m.id !== tempUserId && m.id !== pendingId,
          )
          alert(res.message || '发送失败，请稍后重试')
          return
        }
        applySendResult(sessionId, tempUserId, pendingId, res.data)
        return
      }

      const completed = await sendMessageStream(sessionId, trimmed, {
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
          const idx = messages.value.findIndex((m) => m.id === pendingId)
          if (idx >= 0) {
            const existing = messages.value[idx]
            messages.value[idx] = {
              ...existing,
              content: existing.content ? `${existing.content}\n${ackContent}` : ackContent,
            }
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
          applySendResult(sessionId, tempUserId, pendingId, data)
        },
        onError: (message) => {
          messages.value = messages.value.filter((m) => m.id !== pendingId)
          alert(message)
        },
      }, { cardDraft })

      if (!completed) {
        messages.value = messages.value.filter(
          (m) => m.id !== pendingId && m.id !== tempUserId,
        )
        await loadMessages(sessionId, { silent: true })
      }
    } catch {
      messages.value = messages.value.filter(
        (m) => m.id !== pendingId && m.id !== tempUserId,
      )
      await loadMessages(sessionId, { silent: true })
      alert('发送失败，请稍后重试')
    } finally {
      sending.value = false
    }
  }

  async function confirmBooking(payload: {
    messageId: string
    flight_no?: string
    train_no?: string
    hotel_name?: string
    drive?: boolean
  }) {
    await _confirmWorkflow(payload.messageId, 'booking_selection', () =>
      confirmBookingSelection(activeSessionId.value!, {
        flight_no: payload.flight_no,
        train_no: payload.train_no,
        hotel_name: payload.hotel_name,
        drive: payload.drive,
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
      saveMailPrefill(taskId, {
        ...(emailCompose ?? {
          task_id: taskId,
          session_id: activeSessionId.value ?? undefined,
          recipient: emailFields.recipient,
          cc: emailFields.cc,
          subject: emailFields.subject,
          body: emailFields.body,
          signature: emailFields.signature,
        }),
        from_name: emailCompose?.from_name,
        from_email: emailCompose?.from_email,
      })
      openMailCompose(taskId)
    }
  }

  async function confirmMeetingPlanAction(payload: {
    messageId: string
    supplementary_content?: string
    subject?: string
    meeting_name?: string
    meeting_topic?: string
    room?: string | null
    room_flexible?: boolean
    room_preference?: string
    attendees?: string
    date_hint?: string
    start_hint?: string
    end_hint?: string
    confirm_node_id?: string
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
        meeting_name: payload.meeting_name ?? (draftPayload.meeting_name as string | undefined),
        meeting_topic: payload.meeting_topic ?? (draftPayload.meeting_topic as string | undefined),
        room: payload.room ?? (draftPayload.room as string | null | undefined),
        room_flexible: payload.room_flexible ?? (draftPayload.room_flexible as boolean | undefined),
        room_preference: payload.room_preference ?? (draftPayload.room_preference as string | undefined),
        attendees: payload.attendees ?? (draftPayload.attendees as string | undefined),
        date_hint: payload.date_hint ?? (draftPayload.date_hint as string | undefined),
        start_hint: payload.start_hint ?? (draftPayload.start_hint as string | undefined),
        end_hint: payload.end_hint ?? (draftPayload.end_hint as string | undefined),
        confirm_node_id: payload.confirm_node_id
          ?? (draftPayload.confirm_node_id as string | undefined),
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

  function cancelledNodeIdFromConfirmMessage(msg: Message | undefined): string | null {
    if (!msg?.metadata) return null
    const generic = msg.metadata.workflow_cancel_confirm as { node_id?: string } | undefined
    if (generic?.node_id) return generic.node_id
    if (msg.metadata.room_cancel_confirm) return 'room'
    return null
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
    const cancelNodeId = cancelledNodeIdFromConfirmMessage(
      messages.value.find((m) => m.id === messageId),
    )
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
      syncWorkflowPlanFromAssistantMessage(res.data.assistant_message)
      if (
        cancelNodeId
        && (metaKey === 'workflow_cancel_confirm' || metaKey === 'room_cancel_confirm')
      ) {
        messages.value = applyCancelledNodesToWorkflowPlan(messages.value, [cancelNodeId])
      }
      const session = sessions.value.find((s) => s.id === sessionId)
      if (session) {
        session.message_count += 2
        session.updated_at = res.data.assistant_message.created_at
        if (res.data.session_title) {
          session.title = res.data.session_title
        }
      }
      if (
        (metaKey === 'workflow_cancel_confirm' || metaKey === 'room_cancel_confirm')
        && activeSessionId.value
      ) {
        await loadMessages(activeSessionId.value, { silent: true })
      } else if (!res.data.assistant_message.metadata?.workflow_plan && activeSessionId.value) {
        await loadMessages(activeSessionId.value, { silent: true })
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

  async function requestWorkflowCancelConfirmAction(payload: {
    taskId?: string
    nodeId?: string
  }) {
    if (!activeSessionId.value || workflowSubmitting.value) return null
    const sessionId = activeSessionId.value
    workflowSubmitting.value = true
    try {
      const res = await requestWorkflowCancelConfirm(sessionId, {
        task_id: payload.taskId ?? null,
        node_id: payload.nodeId ?? null,
      })
      if (res.code !== 200 || !res.data) {
        alert(res.message || '无法发起取消确认')
        return null
      }
      messages.value.push(res.data.user_message)
      messages.value.push(res.data.assistant_message)
      syncWorkflowPlanFromAssistantMessage(res.data.assistant_message)
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

  async function activateWorkflowNode(nodeId: string): Promise<Message | null> {
    if (!activeSessionId.value || sending.value || workflowSubmitting.value) {
      return null
    }
    const sessionId = activeSessionId.value
    try {
      const res = await activateWorkflowNodeApi(sessionId, nodeId)
      if (res.code !== 200 || !res.data?.assistant_message) {
        alert(res.message || '无法激活该办理节点')
        return null
      }
      appendAssistantMessageIfNew(res.data.assistant_message)
      syncWorkflowPlanFromAssistantMessage(res.data.assistant_message)
      const session = sessions.value.find((s) => s.id === sessionId)
      if (session) {
        session.message_count += 1
        session.updated_at = res.data.assistant_message.created_at
      }
      return res.data.assistant_message
    } catch {
      alert('激活办理节点失败，请稍后重试')
      return null
    }
  }

  function syncWorkflowPlanFromAssistantMessage(assistantMessage: Message) {
    const plan = assistantMessage.metadata?.workflow_plan as WorkflowPlan | undefined
    if (!plan?.nodes?.length) return
    messages.value = applyWorkflowPlanToMessages(messages.value, plan)
  }

  async function confirmMeetingCancelSelectionAction(payload: {
    messageId: string
    node_ids: string[]
  }) {
    await _confirmWorkflow(payload.messageId, 'meeting_cancel_selection', () =>
      confirmMeetingCancelSelection(activeSessionId.value!, {
        node_ids: payload.node_ids,
      }),
    )
  }

  async function confirmWorkflowCancelAction(payload: { messageId: string; task_id: string }) {
    const msg = messages.value.find((item) => item.id === payload.messageId)
    const metaKey = msg?.metadata?.workflow_cancel_confirm
      ? 'workflow_cancel_confirm'
      : 'room_cancel_confirm'
    await _confirmWorkflow(payload.messageId, metaKey, () =>
      confirmWorkflowCancel(activeSessionId.value!, { task_id: payload.task_id }),
    )
  }

  async function cancelWorkflowNode(taskId: string) {
    if (!taskId || workflowSubmitting.value) return false
    workflowSubmitting.value = true
    try {
      const { cancelTask } = await import('@/services/taskService')
      const res = await cancelTask(taskId)
      if (res.code !== 200 || !res.data) {
        alert(res.message || '取消失败，请稍后重试')
        return false
      }
      if (res.data.assistant_message) {
        appendAssistantMessageIfNew(res.data.assistant_message)
        syncWorkflowPlanFromAssistantMessage(res.data.assistant_message)
      }
      if (
        !res.data.assistant_message?.metadata?.workflow_plan
        && activeSessionId.value
      ) {
        await loadMessages(activeSessionId.value, { silent: true })
      }
      return true
    } catch {
      alert('取消失败，请稍后重试')
      return false
    } finally {
      workflowSubmitting.value = false
    }
  }

  async function withdrawAndOpenOa(
    taskId: string,
    openPage: () => boolean,
  ) {
    if (!taskId || workflowSubmitting.value) return false
    workflowSubmitting.value = true
    try {
      const { withdrawOaApplication } = await import('@/services/taskService')
      const res = await withdrawOaApplication(taskId)
      if (res.code !== 200 || !res.data) {
        alert(res.message || '撤回失败，请稍后重试')
        return false
      }
      if (res.data.assistant_message) {
        appendAssistantMessageIfNew(res.data.assistant_message)
      }
      if (activeSessionId.value) {
        await loadMessages(activeSessionId.value, { silent: true })
      }
      openPage()
      return true
    } catch {
      alert('撤回失败，请稍后重试')
      return false
    } finally {
      workflowSubmitting.value = false
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
    activeInputDraft,
    workflowCardDrafts,
    setWorkflowCardDraft,
    getWorkflowCardDraft,
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
    cancelWorkflowNode,
    withdrawAndOpenOa,
    requestWorkflowCancelConfirm: requestWorkflowCancelConfirmAction,
    confirmWorkflowCancel: confirmWorkflowCancelAction,
    confirmMeetingCancelSelection: confirmMeetingCancelSelectionAction,
    activateWorkflowNode,
  }
})
