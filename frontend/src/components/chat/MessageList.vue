<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import type {
  BookingSelectionMeta,
  Message,
  MessageSource,
  RoomSelectionMeta,
  WorkpackageConfirmMeta,
  WorkpackagePlanConfirmMeta,
  EmailPlanConfirmMeta,
  TravelPlanConfirmMeta,
  MeetingPlanConfirmMeta,
  LeavePlanConfirmMeta,
  InfoCollectPlanConfirmMeta,
  WorkflowNextNode,
  WorkflowCompletedNode,
  WorkflowDrawerRequest,
  WorkflowCancelConfirmMeta,
  MeetingCancelSelectionMeta,
  RoomCancelConfirmMeta,
  RelatedTaskMeta,
} from '@/types'
import { formatMessageHtml } from '@/utils/messageFormat'
import TravelBookingPicker from '@/components/chat/TravelBookingPicker.vue'
import MeetingRoomPicker from '@/components/chat/MeetingRoomPicker.vue'
import WorkpackageConfirmPanel from '@/components/chat/WorkpackageConfirmPanel.vue'
import WorkpackagePlanConfirmPanel from '@/components/chat/WorkpackagePlanConfirmPanel.vue'
import MeetingPlanConfirmPanel from '@/components/chat/MeetingPlanConfirmPanel.vue'
import EmailPlanConfirmPanel from '@/components/chat/EmailPlanConfirmPanel.vue'
import TravelPlanConfirmPanel from '@/components/chat/TravelPlanConfirmPanel.vue'
import LeavePlanConfirmPanel from '@/components/chat/LeavePlanConfirmPanel.vue'
import MemoryCollectConfirmPanel from '@/components/chat/MemoryCollectConfirmPanel.vue'
import WorkflowCancelConfirmPanel from '@/components/chat/WorkflowCancelConfirmPanel.vue'
import MeetingCancelSelectionPanel from '@/components/chat/MeetingCancelSelectionPanel.vue'
import WorkflowCompletedSummary from '@/components/chat/WorkflowCompletedSummary.vue'
import WelcomeQuickActions from '@/components/chat/WelcomeQuickActions.vue'
import { nodeActivationPrompt } from '@/utils/workflowPlan'
import { filterDrawerItems } from '@/utils/taskOaStatus'

const props = defineProps<{
  messages: Message[]
  workflowSubmitting?: boolean
  quickActionsDisabled?: boolean
  activeTaskId?: string | null
}>()

const emit = defineEmits<{
  openTask: [taskId: string]
  openDrawer: [request: WorkflowDrawerRequest]
  openSource: [source: MessageSource]
  confirmBooking: [payload: { messageId: string; flight_no?: string; train_no?: string; hotel_name?: string; drive?: boolean }]
  confirmRoom: [payload: { messageId: string; room: string }]
  confirmWorkpackage: [payload: { messageId: string; entries: import('@/types').TimesheetEntry[] }]
  confirmWorkpackagePlan: [payload: {
    messageId: string
    project?: string
    all_days_eight_hours?: boolean
    hours_per_day?: number
  }]
  confirmTravelPlan: [payload: {
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
  }]
  confirmMeetingPlan: [payload: {
    messageId: string
    supplementary_content?: string
    subject?: string
    room?: string | null
    room_flexible?: boolean
    room_preference?: string
    attendees?: string
    date_hint?: string
    start_hint?: string
    end_hint?: string
    confirm_node_id?: string
  }]
  confirmLeavePlan: [payload: {
    messageId: string
    reason: string
    attachment_name?: string
    leave_type?: string
    date_start?: string
    date_end?: string
    start_period?: string
    end_period?: string
  }]
  confirmInfoCollectPlan: [payload: { messageId: string; structured: import('@/mocks/settings').MemoryStructured }]
  confirmWorkflowCancel: [payload: { messageId: string; task_id: string }]
  confirmMeetingCancelSelection: [payload: { messageId: string; node_ids: string[] }]
  updateCardDraft: [draft: import('@/utils/workflowCardDraft').WorkflowCardDraft]
  quickStart: [prompt: string]
}>()

const containerRef = ref<HTMLElement | null>(null)
const bottomRef = ref<HTMLElement | null>(null)
const expandedPolicyIds = ref<Set<string>>(new Set())
const focusedMessageId = ref<string | null>(null)
const focusedInteractiveId = ref<string | null>(null)
let focusTimer: number | null = null
let interactiveFocusTimer: number | null = null

async function scrollToLatest(behavior: ScrollBehavior = 'smooth') {
  await nextTick()
  bottomRef.value?.scrollIntoView({ behavior, block: 'end' })
}

async function scrollToMessage(
  messageId: string,
  behavior: ScrollBehavior = 'smooth',
  options?: { highlightInteractive?: boolean; highlightOa?: boolean },
) {
  await nextTick()
  const el = containerRef.value?.querySelector(
    `[data-message-id="${messageId}"]`,
  ) as HTMLElement | null
  if (!el) return false

  if (options?.highlightInteractive || options?.highlightOa) {
    const zone = el.querySelector('.interactive-zone') as HTMLElement | null
    const planConfirm = el.querySelector('.plan-confirm') as HTMLElement | null
    const oaEntry = el.querySelector('.oa-entry') as HTMLElement | null
    const advance = el.querySelector('.workflow-advance') as HTMLElement | null
    const focusEl = options.highlightOa
      ? (oaEntry ?? advance ?? zone ?? planConfirm)
      : (zone ?? planConfirm ?? oaEntry ?? advance)
    if (focusEl) {
      focusEl.scrollIntoView({ behavior, block: 'center' })
      focusedInteractiveId.value = messageId
      if (interactiveFocusTimer !== null) {
        window.clearTimeout(interactiveFocusTimer)
      }
      interactiveFocusTimer = window.setTimeout(() => {
        focusedInteractiveId.value = null
        interactiveFocusTimer = null
      }, 3200)
    } else {
      el.scrollIntoView({ behavior, block: 'center' })
    }
  } else {
    el.scrollIntoView({ behavior, block: 'center' })
  }

  focusedMessageId.value = messageId
  if (focusTimer !== null) {
    window.clearTimeout(focusTimer)
  }
  focusTimer = window.setTimeout(() => {
    focusedMessageId.value = null
    focusTimer = null
  }, 2600)
  return true
}

defineExpose({ scrollToMessage })

watch(
  () =>
    [
      props.messages.length,
      props.messages[props.messages.length - 1]?.id,
      props.messages[props.messages.length - 1]?.content,
    ] as const,
  async ([len, lastId], prev) => {
    if (!len || !lastId) return
    const prevLen = prev?.[0] ?? 0
    const behavior: ScrollBehavior = prevLen === 0 ? 'instant' : 'smooth'
    await scrollToLatest(behavior)
  },
  { flush: 'post' },
)

onMounted(() => {
  if (props.messages.length) scrollToLatest('instant')
})

function completedNode(msg: Message): WorkflowCompletedNode | null {
  const raw = msg.metadata?.workflow_completed_node as WorkflowCompletedNode | undefined
  if (!raw?.node_id) return null
  return raw
}

function taskMeta(msg: Message) {
  const m = msg.metadata ?? {}
  const completed = completedNode(msg)
  const percent = completed?.progress_percent ?? (m.progress_percent as number) ?? 50
  const status = (m.status as string) ?? ''
  return {
    title: completed?.task_title || (m.task_title as string) || '任务进行中',
    progress: completed?.progress || (m.progress as string) || '',
    percent,
    stepsDesc: completed?.steps_desc || (m.steps_desc as string) || '',
    taskId: completed?.task_id || (m.task_id as string) || '',
    completed: status === 'completed' || percent >= 100,
  }
}

function relatedTasks(msg: Message): RelatedTaskMeta[] {
  const raw = msg.metadata?.related_tasks as RelatedTaskMeta[] | undefined
  return Array.isArray(raw) ? raw : []
}

function taskCardMetaFromRelated(task: RelatedTaskMeta) {
  return {
    title: task.task_title,
    progress: task.progress,
    percent: task.progress_percent ?? 50,
    stepsDesc: task.steps_desc,
    taskId: task.task_id,
    completed: (task.progress_percent ?? 0) >= 100,
  }
}

function relatedTaskHint(task: RelatedTaskMeta): string {
  if (task.meeting_kind === 'gn') return '点击打开划窗查看步骤，确认后前往 OA 提交国能会议'
  if (task.meeting_kind === 'room') return '点击打开划窗查看步骤，确认后前往 OA 提交会议室预约'
  if (task.booking_kind === 'transport' || task.booking_kind === 'hotel') {
    return '点击打开划窗查看步骤，确认后前往 OA'
  }
  return '点击打开划窗查看步骤，确认后前往 OA'
}

function oaEntryHint(msg: Message): string {
  const completed = completedNode(msg)
  if (completed?.oa_label) return `${completed.oa_label}：先打开划窗核对步骤，再确认跳转`
  if (msg.metadata?.meeting_kind === 'gn') return '点击打开划窗查看步骤，确认后前往 OA 提交国能会议'
  if (msg.metadata?.meeting_kind === 'room') return '点击打开划窗查看步骤，确认后前往 OA 提交会议室预约'
  return '点击打开划窗查看步骤，确认后前往 OA'
}

function oaEntryTaskId(msg: Message): string {
  return completedNode(msg)?.task_id || taskMeta(msg).taskId || ''
}

function hasOaEntry(msg: Message): boolean {
  return relatedTasks(msg).length > 0 || Boolean(oaEntryTaskId(msg))
}

function oaEntryNodeId(msg?: Message, task?: RelatedTaskMeta): string | undefined {
  if (task?.meeting_kind === 'gn') return 'gn_meeting'
  if (task?.meeting_kind === 'room') return 'room'
  if (task?.booking_kind === 'transport') return 'booking'
  if (task?.booking_kind === 'hotel') return 'hotel'
  if (!msg) return undefined
  const completed = completedNode(msg)
  if (completed?.node_id) return completed.node_id
  if (msg.metadata?.meeting_kind === 'gn') return 'gn_meeting'
  if (msg.metadata?.meeting_kind === 'room') return 'room'
  return undefined
}

function openOaDrawer(taskId?: string | null, nodeId?: string | null) {
  if (!taskId && !nodeId) return
  emit('openDrawer', { taskId, nodeId, force: true })
}

function handleRelatedTaskClick(task: RelatedTaskMeta) {
  openOaDrawer(task.task_id, oaEntryNodeId(undefined, task))
}

function handleSingleTaskClick(msg: Message) {
  openOaDrawer(oaEntryTaskId(msg), oaEntryNodeId(msg))
}

function confirmDrawerRequest(msg: Message): WorkflowDrawerRequest | null {
  const meeting = meetingPlanConfirm(msg)
  if (meeting) {
    const nodeId = meeting.confirm_node_id
      || (meeting.plan_mode === 'gn_only' || meeting.needs_gn_meeting ? 'gn_meeting' : 'room')
    return {
      nodeId,
      title: meeting.title,
      items: filterDrawerItems(meeting.items, nodeId),
    }
  }
  const leave = leavePlanConfirm(msg)
  if (leave) {
    return { nodeId: 'leave', title: leave.title, items: leave.items }
  }
  const travel = travelPlanConfirm(msg)
  if (travel) {
    return { nodeId: 'travel', title: travel.title, items: travel.items }
  }
  const email = emailPlanConfirm(msg)
  if (email) {
    return { nodeId: 'email', title: email.title, items: email.items }
  }
  const workpackage = workpackagePlanConfirm(msg)
  if (workpackage) {
    return { nodeId: 'workpackage', title: workpackage.title, items: workpackage.items }
  }
  return null
}

function handleConfirmPanelFocus(msg: Message) {
  const request = confirmDrawerRequest(msg)
  if (request) emit('openDrawer', request)
}

function handleCompletedSummaryClick(msg: Message) {
  const completed = completedNode(msg)
  if (!completed) return
  emit('openDrawer', {
    taskId: completed.task_id,
    nodeId: completed.node_id,
    title: `${completed.node_label}任务详情`,
    items: completed.items,
    force: true,
  })
}

function hasContinuationCard(msg: Message): boolean {
  return Boolean(completedNode(msg) || relatedTasks(msg).length || msg.message_type === 'task')
}

function sources(msg: Message): MessageSource[] {
  const list = msg.metadata?.sources as MessageSource[] | undefined
  return list ?? []
}

interface PolicyReminderMeta {
  rule_id: string
  title: string
  message: string
  clause: string
}

function workflowNextNode(msg: Message): WorkflowNextNode | null {
  const raw = msg.metadata?.workflow_next_node as WorkflowNextNode | undefined
  if (!raw) return null
  if (raw.node_id === null && !raw.label) return null
  return raw
}

function policyReminders(msg: Message): PolicyReminderMeta[] {
  if (hasNonTravelWorkflowSurface(msg)) {
    return []
  }
  const list = msg.metadata?.policy_reminders as PolicyReminderMeta[] | undefined
  return list ?? []
}

function isEmailPlanConfirm(meta: Record<string, unknown>): boolean {
  const confirm = meta.travel_plan_confirm as { email_only?: boolean; status?: string } | undefined
  return Boolean(confirm?.email_only)
}

function hasNonTravelWorkflowSurface(msg: Message): boolean {
  const meta = msg.metadata ?? {}
  if (isEmailPlanConfirm(meta)) {
    return true
  }
  return Boolean(
    meta.workpackage_confirm
    || meta.workpackage_plan_confirm
    || meta.meeting_plan_confirm
    || meta.leave_plan_confirm
    || meta.info_collect_plan_confirm
    || meta.room_selection
    || meta.workflow_cancel_confirm
    || meta.room_cancel_confirm
    || meta.meeting_cancel_selection
  )
}

function policySources(msg: Message): MessageSource[] {
  if (hasNonTravelWorkflowSurface(msg)) {
    return []
  }
  return sources(msg)
}

function shouldRenderHtml(msg: Message): boolean {
  if (msg.role !== 'assistant') return false
  if (msg.message_type === 'pending' && !msg.content) return false
  return true
}

function isPolicyExpanded(msgId: string): boolean {
  return expandedPolicyIds.value.has(msgId)
}

function togglePolicyBasis(msgId: string) {
  const next = new Set(expandedPolicyIds.value)
  if (next.has(msgId)) {
    next.delete(msgId)
  } else {
    next.add(msgId)
  }
  expandedPolicyIds.value = next
}

function bookingSelection(msg: Message): BookingSelectionMeta | null {
  const raw = msg.metadata?.booking_selection as BookingSelectionMeta | undefined
  if (!raw || raw.status !== 'pending') return null
  if (!raw.needs_flight && !raw.needs_hotel) return null
  const hasFlights = (raw.flights?.length ?? 0) > 0
  const hasTrains = (raw.trains?.length ?? 0) > 0
  const hasHotels = (raw.hotels?.length ?? 0) > 0
  const hasTransport = raw.transport_type === 'train' ? hasTrains : hasFlights
  if (raw.needs_flight && !hasTransport && !raw.needs_hotel) return null
  if (raw.needs_hotel && !hasHotels && !raw.needs_flight) return null
  if (raw.needs_flight && raw.needs_hotel && !hasTransport && !hasHotels) return null
  return raw
}

function hasInteractivePicker(msg: Message): boolean {
  return Boolean(
    msg.metadata?.interactive
    || bookingSelection(msg)
    || roomSelection(msg)
    || workpackageConfirm(msg)
    || workpackagePlanConfirm(msg)
    || emailPlanConfirm(msg)
    || travelPlanConfirm(msg)
    || meetingPlanConfirm(msg)
    || leavePlanConfirm(msg)
    || infoCollectPlanConfirm(msg)
    || (workflowCancelConfirm(msg)?.status === 'pending')
    || (meetingCancelSelection(msg)?.status === 'pending'),
  )
}

function handleBookingConfirm(
  messageId: string,
  payload: { flight_no?: string; train_no?: string; hotel_name?: string },
) {
  emit('confirmBooking', { messageId, ...payload })
}

function roomSelection(msg: Message): RoomSelectionMeta | null {
  const raw = msg.metadata?.room_selection as RoomSelectionMeta | undefined
  if (!raw?.options?.length) return null
  return raw
}

function workpackageConfirm(msg: Message): WorkpackageConfirmMeta | null {
  const raw = msg.metadata?.workpackage_confirm as WorkpackageConfirmMeta | undefined
  if (!raw || raw.status !== 'pending') return null
  return raw
}

function workpackagePlanConfirm(msg: Message): WorkpackagePlanConfirmMeta | null {
  const raw = msg.metadata?.workpackage_plan_confirm as WorkpackagePlanConfirmMeta | undefined
  if (!raw?.items?.length || raw.status !== 'pending') return null
  return raw
}

function emailPlanConfirm(msg: Message): EmailPlanConfirmMeta | null {
  const raw = msg.metadata?.travel_plan_confirm as EmailPlanConfirmMeta | undefined
  if (!raw?.email_only || raw.status !== 'pending') return null
  return raw
}

function travelPlanConfirm(msg: Message): TravelPlanConfirmMeta | null {
  const raw = msg.metadata?.travel_plan_confirm as TravelPlanConfirmMeta | undefined
  if (!raw || raw.status !== 'pending') return null
  if ((raw as EmailPlanConfirmMeta).email_only) return null
  return raw
}

function meetingPlanConfirm(msg: Message): MeetingPlanConfirmMeta | null {
  const raw = msg.metadata?.meeting_plan_confirm as MeetingPlanConfirmMeta | undefined
  if (!raw?.items?.length || raw.status !== 'pending') return null
  return raw
}

function leavePlanConfirm(msg: Message): LeavePlanConfirmMeta | null {
  const raw = msg.metadata?.leave_plan_confirm as LeavePlanConfirmMeta | undefined
  if (!raw?.items?.length || raw.status !== 'pending') return null
  return raw
}

function infoCollectPlanConfirm(msg: Message): InfoCollectPlanConfirmMeta | null {
  const raw = msg.metadata?.info_collect_plan_confirm as InfoCollectPlanConfirmMeta | undefined
  if (!raw || raw.status !== 'pending') return null
  return raw
}

function meetingCancelSelection(msg: Message): MeetingCancelSelectionMeta | null {
  const raw = msg.metadata?.meeting_cancel_selection as MeetingCancelSelectionMeta | undefined
  if (!raw?.options?.length || raw.status === 'superseded') return null
  return raw
}

function workflowCancelConfirm(msg: Message): WorkflowCancelConfirmMeta | null {
  const generic = msg.metadata?.workflow_cancel_confirm as WorkflowCancelConfirmMeta | undefined
  if (generic?.task_id && generic.status !== 'superseded') {
    return generic
  }

  const legacy = msg.metadata?.room_cancel_confirm as RoomCancelConfirmMeta | undefined
  if (!legacy?.task_id || legacy.status === 'superseded') return null

  const timeValue = legacy.time_label
    || (legacy.start_time && legacy.end_time
      ? `${legacy.start_time} — ${legacy.end_time}`
      : legacy.start_time || legacy.end_time || '—')

  return {
    status: legacy.status,
    title: legacy.title,
    confirm_label: legacy.confirm_label,
    task_id: legacy.task_id,
    node_id: 'room',
    node_label: '会议室',
    items: [
      { label: '会议室', value: legacy.room_name },
      { label: '会议主题', value: legacy.subject },
      { label: '会议时间', value: timeValue },
      { label: '参会人员', value: legacy.attendees },
    ].filter((item) => item.value && item.value !== '—'),
  }
}

function hasPendingPlanForNextNode(msg: Message): boolean {
  const next = workflowNextNode(msg)
  if (!next?.node_id) return false
  if (next.node_id === 'leave') {
    return leavePlanConfirm(msg)?.status === 'pending'
  }
  if (next.node_id === 'room' || next.node_id === 'gn_meeting') {
    return meetingPlanConfirm(msg)?.status === 'pending'
  }
  if (next.node_id === 'travel' || next.node_id === 'email') {
    return Boolean(travelPlanConfirm(msg) || emailPlanConfirm(msg))
  }
  if (next.node_id === 'workpackage') {
    return Boolean(workpackagePlanConfirm(msg) || workpackageConfirm(msg))
  }
  if (next.node_id === 'info_collect') {
    return infoCollectPlanConfirm(msg)?.status === 'pending'
  }
  return false
}

function handleNextNodeClick(msg: Message) {
  const nextNode = workflowNextNode(msg)
  if (!nextNode?.node_id) return
  if (props.quickActionsDisabled) {
    window.alert('正在处理上一条消息，请稍候…')
    return
  }
  emit('quickStart', nodeActivationPrompt(nextNode.node_id, nextNode.label))
}

function showBookingSwitchToFlight(next: WorkflowNextNode | null | undefined): boolean {
  if (!next || next.node_id !== 'booking') return false
  return next.transport_type !== 'flight'
}

function handleSwitchToFlightBooking() {
  if (props.quickActionsDisabled) return
  emit('quickStart', '订机票')
}
</script>

<template>
  <div ref="containerRef" class="messages">
    <div
      v-for="msg in messages"
      :key="msg.id"
      class="message-row"
      :class="[
        msg.role,
        {
          'welcome-row': msg.metadata?.is_welcome,
          'wide-form-row': travelPlanConfirm(msg) || emailPlanConfirm(msg)
            || meetingPlanConfirm(msg) || leavePlanConfirm(msg)
            || hasContinuationCard(msg),
          focused: focusedMessageId === msg.id,
        },
      ]"
      :data-message-id="msg.id"
    >
      <WelcomeQuickActions
        v-if="msg.metadata?.is_welcome"
        :message="msg.content"
        :disabled="quickActionsDisabled"
        @select="emit('quickStart', $event)"
      />
      <div
        v-else
        class="bubble"
        :class="[msg.role, { pending: msg.message_type === 'pending' }]"
      >
        <div v-if="msg.message_type === 'pending' && !msg.content" class="typing-indicator">
          <span class="typing-label">正在思考</span>
          <span class="typing-dots" aria-hidden="true">
            <span /><span /><span />
          </span>
        </div>
        <div
          v-else-if="shouldRenderHtml(msg)"
          class="message-text"
          v-html="formatMessageHtml(msg.content)"
        />
        <template v-else>{{ msg.content }}</template>

        <MeetingCancelSelectionPanel
          v-if="meetingCancelSelection(msg)"
          :class="{ 'interactive-focus': focusedInteractiveId === msg.id }"
          :selection="meetingCancelSelection(msg)!"
          :submitting="workflowSubmitting"
          @confirm="emit('confirmMeetingCancelSelection', {
            messageId: msg.id,
            node_ids: $event.node_ids,
          })"
        />

        <WorkflowCancelConfirmPanel
          v-if="workflowCancelConfirm(msg)"
          :class="{ 'interactive-focus': focusedInteractiveId === msg.id }"
          :confirm="workflowCancelConfirm(msg)!"
          :submitting="workflowSubmitting"
          @confirm="emit('confirmWorkflowCancel', {
            messageId: msg.id,
            task_id: $event.task_id,
          })"
        />

        <div
          v-if="hasContinuationCard(msg) || travelPlanConfirm(msg) || emailPlanConfirm(msg)
            || workflowNextNode(msg)
            || (hasInteractivePicker(msg) && !workflowCancelConfirm(msg) && !meetingCancelSelection(msg))"
          class="workflow-advance"
          :class="{
            'interactive-focus': focusedInteractiveId === msg.id,
            'continuation-card': hasContinuationCard(msg),
          }"
        >
        <p v-if="completedNode(msg)" class="continuation-label">上一节点 · 已确认信息</p>
        <WorkflowCompletedSummary
          v-if="completedNode(msg)"
          class="completed-summary-trigger"
          :node="completedNode(msg)!"
          @click="handleCompletedSummaryClick(msg)"
        />

        <p v-if="hasOaEntry(msg)" class="continuation-label">前往 OA</p>
        <template v-if="relatedTasks(msg).length">
          <div class="task-card-grid">
            <button
              v-for="task in relatedTasks(msg)"
              :key="task.task_id"
              type="button"
              class="task-card task-card-compact oa-entry"
              :class="{
                completed: taskCardMetaFromRelated(task).completed,
                active: props.activeTaskId === task.task_id,
              }"
              @click.stop="handleRelatedTaskClick(task)"
              @mousedown.stop
            >
              <div class="task-card-header">
                <span class="task-card-title">{{ taskCardMetaFromRelated(task).title }}</span>
                <span class="task-card-progress">
                  {{ taskCardMetaFromRelated(task).completed
                    ? '已完成'
                    : `${taskCardMetaFromRelated(task).progress} 步骤` }}
                </span>
              </div>
              <div class="progress-bar">
                <div
                  class="progress-fill"
                  :style="{ width: `${taskCardMetaFromRelated(task).percent}%` }"
                />
              </div>
              <div class="task-card-desc">{{ taskCardMetaFromRelated(task).stepsDesc }}</div>
              <div class="task-card-hint">{{ relatedTaskHint(task) }} →</div>
            </button>
          </div>
        </template>

        <button
          v-else-if="hasOaEntry(msg)"
          type="button"
          class="task-card oa-entry"
          :class="{
            completed: taskMeta(msg).completed,
            active: props.activeTaskId === oaEntryTaskId(msg),
          }"
          @click.stop="handleSingleTaskClick(msg)"
          @mousedown.stop
        >
          <div class="task-card-header">
            <span class="task-card-title">{{ completedNode(msg)?.oa_label || taskMeta(msg).title }}</span>
            <span class="task-card-progress">
              {{ taskMeta(msg).completed ? '已完成' : `${taskMeta(msg).progress} 步骤` }}
            </span>
          </div>
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: `${taskMeta(msg).percent}%` }"
            />
          </div>
          <div class="task-card-desc">{{ taskMeta(msg).stepsDesc }}</div>
          <div class="task-card-hint">{{ oaEntryHint(msg) }} →</div>
        </button>

        <p
          v-if="hasContinuationCard(msg) && (hasPendingPlanForNextNode(msg) || workflowNextNode(msg))"
          class="continuation-label"
        >
          下一节点 · 请核对并确认
        </p>

        <div
          v-if="travelPlanConfirm(msg) || emailPlanConfirm(msg)"
          class="node-drawer-trigger"
          @mousedown="handleConfirmPanelFocus(msg)"
        >
        <TravelPlanConfirmPanel
          v-if="travelPlanConfirm(msg)"
          :confirm="travelPlanConfirm(msg)!"
          :submitting="workflowSubmitting"
          @update-draft="emit('updateCardDraft', {
            messageId: msg.id,
            metaKey: 'travel_plan_confirm',
            payload: $event,
          })"
          @confirm="emit('confirmTravelPlan', {
            messageId: msg.id,
            ...$event,
          })"
        />

        <EmailPlanConfirmPanel
          v-if="emailPlanConfirm(msg)"
          :confirm="emailPlanConfirm(msg)!"
          :submitting="workflowSubmitting"
          @update-draft="emit('updateCardDraft', {
            messageId: msg.id,
            metaKey: 'travel_plan_confirm',
            payload: $event,
          })"
          @confirm="emit('confirmTravelPlan', {
            messageId: msg.id,
            ...$event,
          })"
        />
        </div>

        <div
          v-if="hasInteractivePicker(msg) && !travelPlanConfirm(msg) && !emailPlanConfirm(msg)"
          class="interactive-zone"
          @mousedown="handleConfirmPanelFocus(msg)"
        >
        <TravelBookingPicker
          v-if="bookingSelection(msg)"
          :selection="bookingSelection(msg)!"
          :submitting="workflowSubmitting"
          @confirm="(payload) => handleBookingConfirm(msg.id, payload)"
        />

        <MeetingRoomPicker
          v-if="roomSelection(msg)"
          :selection="roomSelection(msg)!"
          :submitting="workflowSubmitting"
          @confirm="(payload) => emit('confirmRoom', { messageId: msg.id, ...payload })"
        />


        <MeetingPlanConfirmPanel
          v-if="meetingPlanConfirm(msg)"
          :confirm="meetingPlanConfirm(msg)!"
          :message-id="msg.id"
          :submitting="workflowSubmitting"
          @update-draft="emit('updateCardDraft', {
            messageId: msg.id,
            metaKey: 'meeting_plan_confirm',
            payload: $event,
          })"
          @confirm="emit('confirmMeetingPlan', {
            messageId: msg.id,
            ...$event,
          })"
        />

        <LeavePlanConfirmPanel
          v-if="leavePlanConfirm(msg)"
          :confirm="leavePlanConfirm(msg)!"
          :submitting="workflowSubmitting"
          @update-draft="emit('updateCardDraft', {
            messageId: msg.id,
            metaKey: 'leave_plan_confirm',
            payload: $event,
          })"
          @confirm="emit('confirmLeavePlan', {
            messageId: msg.id,
            ...$event,
          })"
        />

        <MemoryCollectConfirmPanel
          v-if="infoCollectPlanConfirm(msg)"
          :confirm="infoCollectPlanConfirm(msg)!"
          :submitting="workflowSubmitting"
          @update-draft="emit('updateCardDraft', {
            messageId: msg.id,
            metaKey: 'info_collect_plan_confirm',
            payload: $event,
          })"
          @confirm="emit('confirmInfoCollectPlan', {
            messageId: msg.id,
            structured: $event.structured,
          })"
        />

        <WorkpackagePlanConfirmPanel
          v-if="workpackagePlanConfirm(msg)"
          :confirm="workpackagePlanConfirm(msg)!"
          :submitting="workflowSubmitting"
          @update-draft="emit('updateCardDraft', {
            messageId: msg.id,
            metaKey: 'workpackage_plan_confirm',
            payload: $event,
          })"
          @confirm="emit('confirmWorkpackagePlan', {
            messageId: msg.id,
            project: $event.project,
            all_days_eight_hours: $event.all_days_eight_hours,
            hours_per_day: $event.hours_per_day,
          })"
        />

        <WorkpackageConfirmPanel
          v-if="workpackageConfirm(msg)"
          :confirm="workpackageConfirm(msg)!"
          :submitting="workflowSubmitting"
          @confirm="emit('confirmWorkpackage', { messageId: msg.id, entries: $event.entries })"
        />
        </div>

        <div
          v-if="workflowNextNode(msg) && !hasPendingPlanForNextNode(msg)"
          class="next-node-block"
        >
          <button
            type="button"
            class="next-node-body"
            :disabled="quickActionsDisabled"
            @click="handleNextNodeClick(msg)"
          >
            <div class="next-node-label">下一办理节点</div>
            <div v-if="workflowNextNode(msg)?.label" class="next-node-title">
              {{ workflowNextNode(msg)?.label }}
            </div>
          </button>
          <div
            v-if="workflowNextNode(msg)?.node_id === 'booking' && workflowNextNode(msg)?.origin"
            class="next-node-route"
          >
            <span class="route-label">出发地</span>
            <span class="route-value">{{ workflowNextNode(msg)?.origin }}</span>
            <button
              v-if="showBookingSwitchToFlight(workflowNextNode(msg))"
              type="button"
              class="btn-switch-flight"
              :disabled="quickActionsDisabled"
              @click.stop="handleSwitchToFlightBooking"
            >
              改订机票
            </button>
          </div>
        </div>
        </div>

        <div v-if="policyReminders(msg).length" class="reminder-block">
          <div class="reminder-label">差旅规定提醒</div>
          <ul class="reminder-list">
            <li v-for="item in policyReminders(msg)" :key="item.rule_id">
              {{ item.message }}
              <span class="reminder-clause">（{{ item.clause }}）</span>
            </li>
          </ul>
        </div>

        <div v-if="policySources(msg).length" class="source-block">
          <button
            type="button"
            class="source-toggle"
            :aria-expanded="isPolicyExpanded(msg.id)"
            @click="togglePolicyBasis(msg.id)"
          >
            <span class="source-toggle-left">
              <span class="source-chevron" :class="{ open: isPolicyExpanded(msg.id) }" aria-hidden="true" />
              <span class="source-label">政策依据</span>
              <span class="source-count">{{ policySources(msg).length }} 条</span>
            </span>
            <span class="source-toggle-hint">
              {{ isPolicyExpanded(msg.id) ? '收起' : '展开' }}
            </span>
          </button>

          <Transition name="policy-drawer">
            <div v-show="isPolicyExpanded(msg.id)" class="source-body">
              <div
                v-for="(src, i) in policySources(msg)"
                :key="i"
                class="source-card"
              >
                <p v-if="src.excerpt" class="source-excerpt">{{ src.excerpt }}</p>
                <button
                  type="button"
                  class="source-item"
                  @click="emit('openSource', src)"
                >
                  查看原文 · 《{{ src.filename }}》{{ src.clause }}
                </button>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </div>
    <div ref="bottomRef" class="scroll-anchor" aria-hidden="true" />
  </div>
</template>

<style scoped>
.messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message-row {
  display: flex;
  max-width: 78%;
}

.message-row.user {
  align-self: flex-end;
  justify-content: flex-end;
}

.message-row.assistant {
  align-self: flex-start;
}

.message-row.welcome-row {
  align-self: center;
  max-width: none;
  width: 100%;
  justify-content: center;
  margin-top: 8vh;
}

.message-row.wide-form-row {
  max-width: min(96%, 840px);
}

.message-row.wide-form-row .bubble {
  width: 100%;
}

.message-row.focused .bubble {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 28%, transparent);
  animation: focusPulse 2.4s ease-out;
}

@keyframes focusPulse {
  0% {
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--primary) 42%, transparent);
  }
  100% {
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 18%, transparent);
  }
}

.bubble {
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  line-height: 1.6;
  border: 1px solid var(--border);
}

.bubble.user {
  background: var(--user-bubble-bg);
  border-color: var(--user-bubble-border);
}

.bubble.assistant {
  background: var(--surface);
  white-space: pre-line;
}

.message-text :deep(strong) {
  font-weight: 700;
  color: var(--primary, #c41e3a);
}

.bubble.pending {
  color: var(--text-secondary);
  border-style: dashed;
  white-space: pre-line;
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.typing-label {
  font-size: 13px;
  color: var(--text-muted);
}

.typing-dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: typing-bounce 1.2s infinite ease-in-out;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes typing-bounce {
  0%,
  80%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

.task-card {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font: inherit;
  color: inherit;
  transition: border-color 0.15s;
}

.task-card-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.task-card-compact {
  flex: 1 1 200px;
  max-width: calc(50% - 5px);
  margin-top: 0;
  padding: 10px;
}

.task-card-hint {
  margin-top: 8px;
  font-size: 11px;
  color: var(--primary);
  font-weight: 500;
}

.task-card:hover {
  border-color: var(--primary);
}

.task-card.active {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 16%, transparent);
}

.task-card.completed {
  border-color: #86efac;
  background: color-mix(in srgb, #059669 6%, var(--bg));
}

.task-card.completed .task-card-progress {
  color: #059669;
}

.task-card.completed .progress-fill {
  background: #059669;
}

.task-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.task-card-title {
  font-size: 13px;
  font-weight: 600;
}

.task-card-progress {
  font-size: 12px;
  color: var(--accent);
  font-weight: 500;
}

.progress-bar {
  height: 2px;
  background: #e2e5e9;
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 2px;
  transition: width 0.3s;
}

.task-card-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

.completion-flow {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.completion-flow :deep(.result-card) {
  margin-top: 0;
}

.completion-flow .next-node-block {
  margin-top: 0;
}

.next-node-block {
  display: block;
  width: 100%;
  margin-top: 12px;
  border: 1px solid #bfdbfe;
  border-left: 4px solid #2563eb;
  border-radius: var(--radius-sm);
  background: #eff6ff;
  overflow: hidden;
}

.next-node-body {
  display: block;
  width: 100%;
  padding: 12px 14px;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
}

.next-node-block:hover .next-node-body:not(:disabled) {
  background: #dbeafe;
}

.next-node-body:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: -2px;
}

.next-node-body:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.next-node-route {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 14px 12px;
  border-top: 1px dashed #bfdbfe;
}

.next-node-route .route-label {
  font-size: 12px;
  font-weight: 600;
  color: #1d4ed8;
}

.next-node-route .route-value {
  font-size: 14px;
  font-weight: 600;
  color: #1e3a8a;
}

.next-node-route .btn-switch-flight {
  margin-left: auto;
  height: 26px;
  padding: 0 10px;
  border: 1px solid #93c5fd;
  border-radius: 999px;
  background: #fff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.next-node-route .btn-switch-flight:hover:not(:disabled) {
  background: #dbeafe;
  border-color: #2563eb;
}

.next-node-route .btn-switch-flight:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.next-node-label {
  font-size: 11px;
  font-weight: 600;
  color: #1d4ed8;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: 6px;
}

.next-node-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e3a8a;
  margin-bottom: 8px;
}

.next-node-slots {
  font-size: 13px;
  color: #334155;
  line-height: 1.6;
}

.interactive-zone.interactive-focus {
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25);
  animation: interactive-pulse 1.2s ease-in-out 2;
}

:deep(.plan-confirm.interactive-focus) {
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25);
  animation: interactive-pulse 1.2s ease-in-out 2;
}

@keyframes interactive-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(37, 99, 235, 0.35);
  }
}

.slot-chip {
  display: inline-block;
  margin: 2px 6px 2px 0;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #93c5fd;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 500;
}

.interactive-zone {
  margin-top: 4px;
}

.workflow-advance {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.continuation-card {
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--bg) 70%, var(--surface));
}

.continuation-label {
  margin: 0;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.oa-entry {
  width: 100%;
  text-align: left;
}

.completed-summary-trigger {
  cursor: pointer;
}

.node-drawer-trigger {
  cursor: pointer;
}

.continuation-card .task-card,
.continuation-card .interactive-zone,
.continuation-card .next-node-block {
  margin-top: 0;
}

.workflow-advance.interactive-focus {
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.25);
  animation: interactive-pulse 1.2s ease-in-out 2;
}

.source-block {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.source-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.source-toggle:hover {
  border-color: var(--primary);
  background: #fdf2f2;
}

.source-toggle-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.source-chevron {
  display: inline-block;
  width: 0;
  height: 0;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 6px solid var(--text-muted);
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.source-chevron.open {
  transform: rotate(90deg);
}

.source-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.source-count {
  font-size: 12px;
  color: var(--text-muted);
  padding: 1px 6px;
  border-radius: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
}

.source-toggle-hint {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.source-body {
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.policy-drawer-enter-active,
.policy-drawer-leave-active {
  transition: opacity 0.2s ease, max-height 0.25s ease, margin-top 0.25s ease;
  max-height: 480px;
}

.policy-drawer-enter-from,
.policy-drawer-leave-to {
  opacity: 0;
  max-height: 0;
  margin-top: 0;
}

.reminder-block {
  margin-top: 12px;
  padding: 10px 12px;
  background: #fff8f0;
  border: 1px solid #f0dcc8;
  border-radius: var(--radius-sm);
}

.reminder-label {
  font-size: 12px;
  font-weight: 600;
  color: #b45309;
  margin-bottom: 6px;
}

.reminder-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-secondary);
}

.reminder-clause {
  color: var(--text-muted);
  font-size: 12px;
}

.source-card + .source-card {
  margin-top: 10px;
}

.source-excerpt {
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-secondary);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  margin-bottom: 6px;
  white-space: pre-line;
}

.source-item {
  display: block;
  width: 100%;
  text-align: left;
  font-size: 12px;
  color: var(--primary);
  background: none;
  border: none;
  padding: 2px 0 0;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.source-item:hover {
  color: var(--accent);
}

.scroll-anchor {
  height: 1px;
  flex-shrink: 0;
}
</style>
