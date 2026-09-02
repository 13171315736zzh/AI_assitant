<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import type {
  BookingSelectionMeta,
  Message,
  MessageSource,
  RoomSelectionMeta,
  WorkpackageConfirmMeta,
  WorkpackagePlanConfirmMeta,
  PlanConfirmMeta,
} from '@/types'
import { formatMessageHtml } from '@/utils/messageFormat'
import TravelBookingPicker from '@/components/chat/TravelBookingPicker.vue'
import MeetingRoomPicker from '@/components/chat/MeetingRoomPicker.vue'
import WorkpackageConfirmPanel from '@/components/chat/WorkpackageConfirmPanel.vue'
import WorkpackagePlanConfirmPanel from '@/components/chat/WorkpackagePlanConfirmPanel.vue'
import IntentPlanConfirmPanel from '@/components/chat/IntentPlanConfirmPanel.vue'
import WelcomeQuickActions from '@/components/chat/WelcomeQuickActions.vue'

const props = defineProps<{
  messages: Message[]
  workflowSubmitting?: boolean
  quickActionsDisabled?: boolean
}>()

const emit = defineEmits<{
  openTask: [taskId: string]
  openSource: [source: MessageSource]
  confirmBooking: [payload: { messageId: string; flight_no?: string; hotel_name?: string }]
  confirmRoom: [payload: { messageId: string; room: string }]
  confirmWorkpackage: [payload: { messageId: string; entries: import('@/types').TimesheetEntry[] }]
  confirmWorkpackagePlan: [payload: { messageId: string; project?: string }]
  confirmTravelPlan: [payload: { messageId: string }]
  confirmMeetingPlan: [payload: { messageId: string }]
  quickStart: [prompt: string]
}>()

const containerRef = ref<HTMLElement | null>(null)
const bottomRef = ref<HTMLElement | null>(null)
const expandedPolicyIds = ref<Set<string>>(new Set())

async function scrollToLatest(behavior: ScrollBehavior = 'smooth') {
  await nextTick()
  bottomRef.value?.scrollIntoView({ behavior, block: 'end' })
}

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
  return {
    title: (m.task_title as string) ?? '任务进行中',
    progress: (m.progress as string) ?? '',
    percent: (m.progress_percent as number) ?? 50,
    stepsDesc: (m.steps_desc as string) ?? '',
    taskId: (m.task_id as string) ?? '',
  }
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

function policyReminders(msg: Message): PolicyReminderMeta[] {
  if (
    msg.metadata?.workpackage_confirm
    || msg.metadata?.workpackage_plan_confirm
    || msg.metadata?.meeting_plan_confirm
    || msg.metadata?.room_selection
  ) {
    return []
  }
  const list = msg.metadata?.policy_reminders as PolicyReminderMeta[] | undefined
  return list ?? []
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
  const hasHotels = (raw.hotels?.length ?? 0) > 0
  if (raw.needs_flight && !hasFlights && !raw.needs_hotel) return null
  if (raw.needs_hotel && !hasHotels && !raw.needs_flight) return null
  if (raw.needs_flight && raw.needs_hotel && !hasFlights && !hasHotels) return null
  return raw
}

function hasInteractivePicker(msg: Message): boolean {
  return Boolean(
    msg.metadata?.interactive
    || bookingSelection(msg)
    || roomSelection(msg)
    || workpackageConfirm(msg)
    || workpackagePlanConfirm(msg)
    || travelPlanConfirm(msg)
    || meetingPlanConfirm(msg),
  )
}

function handleBookingConfirm(
  messageId: string,
  payload: { flight_no?: string; hotel_name?: string },
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

function travelPlanConfirm(msg: Message): PlanConfirmMeta | null {
  const raw = msg.metadata?.travel_plan_confirm as PlanConfirmMeta | undefined
  if (!raw?.items?.length) return null
  return raw
}

function meetingPlanConfirm(msg: Message): PlanConfirmMeta | null {
  const raw = msg.metadata?.meeting_plan_confirm as PlanConfirmMeta | undefined
  if (!raw?.items?.length) return null
  return raw
}
</script>

<template>
  <div ref="containerRef" class="messages">
    <div
      v-for="msg in messages"
      :key="msg.id"
      class="message-row"
      :class="[msg.role, { 'welcome-row': msg.metadata?.is_welcome }]"
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

        <div v-if="hasInteractivePicker(msg)" class="interactive-zone">
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

        <IntentPlanConfirmPanel
          v-if="travelPlanConfirm(msg)"
          :confirm="travelPlanConfirm(msg)!"
          :submitting="workflowSubmitting"
          @confirm="emit('confirmTravelPlan', { messageId: msg.id })"
        />

        <IntentPlanConfirmPanel
          v-if="meetingPlanConfirm(msg)"
          :confirm="meetingPlanConfirm(msg)!"
          :submitting="workflowSubmitting"
          @confirm="emit('confirmMeetingPlan', { messageId: msg.id })"
        />

        <WorkpackagePlanConfirmPanel
          v-if="workpackagePlanConfirm(msg)"
          :confirm="workpackagePlanConfirm(msg)!"
          :submitting="workflowSubmitting"
          @confirm="emit('confirmWorkpackagePlan', { messageId: msg.id, project: $event.project })"
        />

        <WorkpackageConfirmPanel
          v-if="workpackageConfirm(msg)"
          :confirm="workpackageConfirm(msg)!"
          :submitting="workflowSubmitting"
          @confirm="emit('confirmWorkpackage', { messageId: msg.id, entries: $event.entries })"
        />
        </div>

        <div
          v-if="msg.message_type === 'task'"
          class="task-card"
          @click="emit('openTask', taskMeta(msg).taskId)"
        >
          <div class="task-card-header">
            <span class="task-card-title">{{ taskMeta(msg).title }}</span>
            <span class="task-card-progress">{{ taskMeta(msg).progress }} 步骤</span>
          </div>
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: `${taskMeta(msg).percent}%` }"
            />
          </div>
          <div class="task-card-desc">{{ taskMeta(msg).stepsDesc }}</div>
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

        <div v-if="sources(msg).length" class="source-block">
          <button
            type="button"
            class="source-toggle"
            :aria-expanded="isPolicyExpanded(msg.id)"
            @click="togglePolicyBasis(msg.id)"
          >
            <span class="source-toggle-left">
              <span class="source-chevron" :class="{ open: isPolicyExpanded(msg.id) }" aria-hidden="true" />
              <span class="source-label">政策依据</span>
              <span class="source-count">{{ sources(msg).length }} 条</span>
            </span>
            <span class="source-toggle-hint">
              {{ isPolicyExpanded(msg.id) ? '收起' : '展开' }}
            </span>
          </button>

          <Transition name="policy-drawer">
            <div v-show="isPolicyExpanded(msg.id)" class="source-body">
              <div
                v-for="(src, i) in sources(msg)"
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

.task-card:hover {
  border-color: var(--primary);
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
