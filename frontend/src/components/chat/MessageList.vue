<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
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
  GnMeetingResultMeta,
  RoomBookingResultMeta,
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
import GnMeetingResultPanel from '@/components/chat/GnMeetingResultPanel.vue'
import RoomBookingResultPanel from '@/components/chat/RoomBookingResultPanel.vue'
import WorkflowSessionSummaryPanel from '@/components/chat/WorkflowSessionSummaryPanel.vue'
import WelcomeQuickActions from '@/components/chat/WelcomeQuickActions.vue'
import { openOaBookingByKind } from '@/utils/oaBooking'
import { extractWorkflowPlan, nodeActivationPrompt } from '@/utils/workflowPlan'
import type { WorkflowSessionSummary } from '@/types'

const props = defineProps<{
  messages: Message[]
  workflowSubmitting?: boolean
  quickActionsDisabled?: boolean
}>()

const emit = defineEmits<{
  openTask: [taskId: string]
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
    attendees?: string
    date_hint?: string
    start_hint?: string
    end_hint?: string
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
  options?: { highlightInteractive?: boolean },
) {
  await nextTick()
  const el = containerRef.value?.querySelector(
    `[data-message-id="${messageId}"]`,
  ) as HTMLElement | null
  if (!el) return false

  if (options?.highlightInteractive) {
    const zone = el.querySelector('.interactive-zone') as HTMLElement | null
    const planConfirm = el.querySelector('.plan-confirm') as HTMLElement | null
    const focusEl = zone ?? planConfirm
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

function taskMeta(msg: Message) {
  const m = msg.metadata ?? {}
  const percent = (m.progress_percent as number) ?? 50
  const status = (m.status as string) ?? ''
  return {
    title: (m.task_title as string) ?? '任务进行中',
    progress: (m.progress as string) ?? '',
    percent,
    stepsDesc: (m.steps_desc as string) ?? '',
    taskId: (m.task_id as string) ?? '',
    completed: status === 'completed' || percent >= 100,
  }
}

function relatedTasks(msg: Message): RelatedTaskMeta[] {
  const raw = msg.metadata?.related_tasks as RelatedTaskMeta[] | undefined
  return Array.isArray(raw) ? raw : []
}

function roomBookingResult(msg: Message): RoomBookingResultMeta | null {
  const raw = msg.metadata?.room_booking_result as RoomBookingResultMeta | undefined
  return raw?.room_name ? raw : null
}

const suppressGnMeetingCard = computed(() => {
  const plan = extractWorkflowPlan(props.messages)
  const gnNode = plan?.nodes.find((node) => node.id === 'gn_meeting')
  const roomNode = plan?.nodes.find((node) => node.id === 'room')
  if (gnNode && roomNode) {
    return gnNode.status === 'completed' && roomNode.status === 'completed'
  }
  return props.messages.some((msg) => roomBookingResult(msg) !== null)
})

function gnMeetingResult(msg: Message): GnMeetingResultMeta | null {
  const raw = msg.metadata?.gn_meeting_result as GnMeetingResultMeta | undefined
  if (!raw?.meeting_link) return null
  if (msg.metadata?.oa_completion) return raw
  if (suppressGnMeetingCard.value) return null
  return raw
}

function taskCardMetaFromRelated(task: RelatedTaskMeta) {
  return {
    title: task.task_title,
    progress: task.progress,
    percent: task.progress_percent ?? 50,
    stepsDesc: task.steps_desc,
    taskId: task.task_id,
    completed: (task.progress_percent ?? 0) >= 100,
    bookingKind: task.booking_kind ?? null,
  }
}

function sessionSummary(msg: Message): WorkflowSessionSummary | null {
  const raw = msg.metadata?.workflow_session_summary as WorkflowSessionSummary | undefined
  return raw?.text ? raw : null
}

function handleRelatedTaskClick(task: RelatedTaskMeta) {
  if (task.booking_kind === 'transport' || task.booking_kind === 'hotel') {
    const opened = openOaBookingByKind(task.task_id, task.booking_kind)
    if (!opened) {
      alert('无法打开新窗口，请检查浏览器是否拦截弹窗。')
    }
    return
  }
  emit('openTask', task.task_id)
}

function handleSingleTaskClick(msg: Message) {
  const meta = msg.metadata ?? {}
  const kind = meta.booking_kind as 'transport' | 'hotel' | undefined
  const taskId = meta.task_id as string | undefined
  if (taskId && (kind === 'transport' || kind === 'hotel')) {
    const opened = openOaBookingByKind(taskId, kind)
    if (!opened) {
      alert('无法打开新窗口，请检查浏览器是否拦截弹窗。')
    }
    return
  }
  emit('openTask', taskMeta(msg).taskId)
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
    || infoCollectPlanConfirm(msg),
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

function handleNextNodeClick(msg: Message) {
  const nextNode = workflowNextNode(msg)
  if (!nextNode?.node_id || props.quickActionsDisabled) return
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
          'wide-form-row': travelPlanConfirm(msg) || emailPlanConfirm(msg),
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

        <div
          v-if="gnMeetingResult(msg) || roomBookingResult(msg) || workflowNextNode(msg)"
          class="completion-flow"
        >
          <GnMeetingResultPanel
            v-if="gnMeetingResult(msg)"
            :result="gnMeetingResult(msg)!"
          />

          <RoomBookingResultPanel
            v-if="roomBookingResult(msg)"
            :result="roomBookingResult(msg)!"
          />

          <div
            v-if="workflowNextNode(msg)"
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
              <div
                v-if="(workflowNextNode(msg)?.missing_slots?.length ?? 0) > 0"
                class="next-node-slots"
              >
                待补充：
                <span
                  v-for="slot in workflowNextNode(msg)?.missing_slots"
                  :key="slot"
                  class="slot-chip"
                >
                  {{ slot }}
                </span>
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

        <TravelPlanConfirmPanel
          v-if="travelPlanConfirm(msg)"
          :class="{ 'interactive-focus': focusedInteractiveId === msg.id }"
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

        <div
          v-if="hasInteractivePicker(msg) && !travelPlanConfirm(msg) && !emailPlanConfirm(msg)"
          class="interactive-zone"
          :class="{ 'interactive-focus': focusedInteractiveId === msg.id }"
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

        <template v-if="relatedTasks(msg).length">
          <div class="task-card-grid">
            <div
              v-for="task in relatedTasks(msg)"
              :key="task.task_id"
              class="task-card task-card-compact"
              :class="{ completed: taskCardMetaFromRelated(task).completed }"
              @click="handleRelatedTaskClick(task)"
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
              <div v-if="task.booking_kind" class="task-card-hint">点击前往 OA 预订 →</div>
            </div>
          </div>
        </template>

        <div
          v-else-if="msg.message_type === 'task'"
          class="task-card"
          :class="{ completed: taskMeta(msg).completed }"
          @click="handleSingleTaskClick(msg)"
        >
          <div class="task-card-header">
            <span class="task-card-title">{{ taskMeta(msg).title }}</span>
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
          <div
            v-if="msg.metadata?.booking_kind"
            class="task-card-hint"
          >
            点击前往 OA 预订 →
          </div>
        </div>

        <WorkflowSessionSummaryPanel
          v-if="sessionSummary(msg)"
          :summary="sessionSummary(msg)!"
        />

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
