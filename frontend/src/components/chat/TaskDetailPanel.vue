<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import type { Task, TaskStep, WorkflowDrawerRequest } from '@/types'
import { fetchTask, confirmTask } from '@/services/taskService'
import { useChatStore } from '@/stores/useChatStore'
import {
  HIDDEN_RESULT_KEYS,
  taskFieldLabel,
  taskFieldValue,
} from '@/utils/taskFieldLabels'
import { isTravelTask, openOaTravelApply } from '@/utils/oaTravel'
import { isTransportBookTask, isHotelBookTask, openOaTransportBook, openOaHotelBook } from '@/utils/oaBooking'
import { isEmailTask } from '@/utils/emailMail'
import { isWorkpackageTask, openOaWorkpackageApply } from '@/utils/oaWorkpackage'
import { isLeaveTask, openOaLeaveApply } from '@/utils/oaLeave'
import { isGnMeetingTask, isRoomBookingTask, openOaGnMeetingApply, openOaRoomMeetingApply } from '@/utils/oaMeeting'
import { useOaTaskSync } from '@/composables/useOaTaskSync'
import {
  collectTaskOutcome,
  detectOaHandleStatus,
  filterDrawerItems,
  mergeLiveDrawerItems,
  OA_HANDLE_STATUS_LABEL,
} from '@/utils/taskOaStatus'
import { extractWorkflowPlan } from '@/utils/workflowPlan'
import GnMeetingResultPanel from '@/components/chat/GnMeetingResultPanel.vue'
import RoomBookingResultPanel from '@/components/chat/RoomBookingResultPanel.vue'

const props = defineProps<{
  taskId?: string | null
  nodeId?: string | null
  pending?: WorkflowDrawerRequest | null
}>()

const emit = defineEmits<{
  dismiss: []
  openForm: [formId: string]
  cancelRequested: [messageId: string]
  confirmPending: []
  bindTask: [taskId: string]
}>()

const chat = useChatStore()
const { workflowCardDrafts, messages } = storeToRefs(chat)

const OA_JUMP_NODES = new Set([
  'gn_meeting',
  'room',
  'leave',
  'travel',
  'workpackage',
  'booking',
  'hotel',
])

const task = ref<Task | null>(null)
const loading = ref(false)
const expandedStep = ref<number | null>(null)

const TRAVEL_DETAIL_TOOLS = new Set(['travel_apply', 'user_confirm'])
const BOOKING_DETAIL_TOOLS = new Set(['flight_book', 'hotel_book', 'user_confirm'])
const EMAIL_DETAIL_TOOLS = new Set(['email_notify', 'user_confirm'])

const visibleSteps = computed(() => {
  if (!task.value) return []
  if (isTransportBookTask(task.value) || isHotelBookTask(task.value)) {
    return task.value.steps.filter((step) => BOOKING_DETAIL_TOOLS.has(step.tool))
  }
  if (isTravelTask(task.value)) {
    return task.value.steps.filter((step) => TRAVEL_DETAIL_TOOLS.has(step.tool))
  }
  if (isEmailTask(task.value)) {
    return task.value.steps.filter((step) => EMAIL_DETAIL_TOOLS.has(step.tool))
  }
  return task.value.steps
})

const visibleProgress = computed(() => {
  const steps = visibleSteps.value
  if (!steps.length) {
    return { current: 0, total: 0, percent: 0 }
  }
  const completed = steps.filter((step) => step.status === 'completed').length
  return {
    current: completed,
    total: steps.length,
    percent: Math.round((completed / steps.length) * 100),
  }
})

const panelTitle = computed(() => {
  if (task.value) {
    if (isGnMeetingTask(task.value)) return '国能会议任务详情'
    if (isRoomBookingTask(task.value)) return '会议室预约任务详情'
    if (isLeaveTask(task.value)) return '请假任务详情'
    if (isTravelTask(task.value)) return '差旅任务详情'
    if (isWorkpackageTask(task.value)) return '工时任务详情'
    if (isTransportBookTask(task.value)) return '交通预订任务详情'
    if (isHotelBookTask(task.value)) return '酒店预订任务详情'
    if (isEmailTask(task.value)) return '邮件任务详情'
    return '任务详情'
  }
  if (props.pending?.title) return props.pending.title
  return '任务详情'
})

const oaStatus = computed(() => detectOaHandleStatus(task.value))
const oaStatusLabel = computed(() => OA_HANDLE_STATUS_LABEL[oaStatus.value])
const outcome = computed(() => collectTaskOutcome(task.value, messages.value))
const submittedItems = computed(() => {
  const extras = outcome.value
  return extras.items.filter((item) => {
    if (extras.gnMeeting && (item.label === '会议主题' || item.label.includes('链接') || item.label.includes('密码') || item.label.includes('会议号'))) {
      return false
    }
    if (extras.roomBooking && ['会议室', '会议主题', '使用时间', '参会人员'].includes(item.label)) {
      return false
    }
    return true
  })
})

const currentNodeId = computed(() => {
  if (props.nodeId) return props.nodeId
  if (props.pending?.nodeId) return props.pending.nodeId
  if (task.value && isGnMeetingTask(task.value)) return 'gn_meeting'
  if (task.value && isRoomBookingTask(task.value)) return 'room'
  if (task.value && isLeaveTask(task.value)) return 'leave'
  if (task.value && isTravelTask(task.value)) return 'travel'
  if (task.value && isWorkpackageTask(task.value)) return 'workpackage'
  return null
})

const liveDraft = computed(() => {
  const drafts = workflowCardDrafts.value
  const nodeId = currentNodeId.value
  if (!nodeId) return null
  for (let index = messages.value.length - 1; index >= 0; index -= 1) {
    const msg = messages.value[index]
    const meta = msg.metadata ?? {}
    if (nodeId === 'gn_meeting' || nodeId === 'room') {
      const payload = drafts[`${msg.id}:meeting_plan_confirm`]?.payload
      if (payload) {
        const meeting = meta.meeting_plan_confirm as {
          confirm_node_id?: string
          plan_mode?: string
          needs_gn_meeting?: boolean
        } | undefined
        const confirmNode = meeting?.confirm_node_id
          || (meeting?.plan_mode === 'gn_only' || meeting?.needs_gn_meeting ? 'gn_meeting' : meeting ? 'room' : nodeId)
        if (confirmNode === nodeId) return payload
      }
    }
    if (nodeId === 'leave' && (meta.leave_plan_confirm as { status?: string } | undefined)?.status === 'pending') {
      return drafts[`${msg.id}:leave_plan_confirm`]?.payload ?? null
    }
    if (nodeId === 'travel' && (meta.travel_plan_confirm as { status?: string; email_only?: boolean } | undefined)?.status === 'pending'
      && !(meta.travel_plan_confirm as { email_only?: boolean }).email_only) {
      return drafts[`${msg.id}:travel_plan_confirm`]?.payload ?? null
    }
    if (nodeId === 'email' && (meta.travel_plan_confirm as { status?: string; email_only?: boolean } | undefined)?.email_only
      && (meta.travel_plan_confirm as { status?: string }).status === 'pending') {
      return drafts[`${msg.id}:travel_plan_confirm`]?.payload ?? null
    }
    if (nodeId === 'workpackage' && (meta.workpackage_plan_confirm as { status?: string } | undefined)?.status === 'pending') {
      return drafts[`${msg.id}:workpackage_plan_confirm`]?.payload ?? null
    }
  }
  return null
})

const displayItems = computed(() => {
  const base = task.value
    ? submittedItems.value
    : filterDrawerItems(props.pending?.items ?? [], currentNodeId.value, props.pending?.title)
  return mergeLiveDrawerItems(
    currentNodeId.value,
    base,
    liveDraft.value,
    panelTitle.value,
  )
})

const linkedTaskId = computed(() => {
  if (props.taskId) return props.taskId
  const plan = extractWorkflowPlan(messages.value)
  return plan?.nodes.find((item) => item.id === currentNodeId.value)?.task_id ?? null
})

const canJumpOa = computed(() => {
  const taskId = linkedTaskId.value
  if (task.value && taskId) {
    return task.value.status !== 'completed'
      && task.value.status !== 'cancelled'
      && task.value.status !== 'failed'
  }
  return Boolean(taskId)
})

const showOaButton = computed(() => {
  if (task.value && !canJumpOa.value) return false
  return canJumpOa.value || OA_JUMP_NODES.has(currentNodeId.value || '')
})

const oaSubmitting = computed(() => chat.workflowSubmitting)

async function load() {
  if (!props.taskId) {
    task.value = null
    loading.value = false
    return
  }
  loading.value = true
  try {
    const res = await fetchTask(props.taskId)
    if (res.code === 200) task.value = res.data
  } finally {
    loading.value = false
  }
}

watch(
  () => props.taskId,
  (taskId, previousTaskId) => {
    if (taskId !== previousTaskId) {
      task.value = null
      expandedStep.value = null
    }
    void load()
  },
  { immediate: true },
)

watch(
  linkedTaskId,
  (taskId) => {
    if (taskId && taskId !== props.taskId) {
      emit('bindTask', taskId)
    }
  },
  { immediate: true },
)

useOaTaskSync((payload) => {
  if (payload.taskId && payload.taskId === props.taskId) {
    void load()
  }
})

function handleClose(event?: Event) {
  event?.preventDefault()
  event?.stopPropagation()
  emit('dismiss')
}

function stepIcon(status: TaskStep['status']) {
  if (status === 'completed') return '✅'
  if (status === 'running') return '🔄'
  if (status === 'failed') return '❌'
  return '⏳'
}

function stepStatusLabel(status: TaskStep['status']) {
  const map = { completed: '已完成', running: '进行中', pending: '待执行', failed: '失败' }
  return map[status]
}

async function handleCancel() {
  if (!props.taskId) return
  const assistantMsg = await chat.requestWorkflowCancelConfirm({ taskId: props.taskId })
  if (!assistantMsg) return
  emit('cancelRequested', assistantMsg.id)
  emit('dismiss')
}

function oaFormLinkLabel(step: TaskStep): string {
  if (step.tool === 'workpackage_fill') return '查看工时填报单 →'
  if (step.tool === 'travel_apply') return '查看差旅申请单 →'
  if (step.tool === 'flight_book') return '查看交通预订单 →'
  if (step.tool === 'hotel_book') return '查看酒店预订单 →'
  if (step.tool === 'leave_apply') return '查看请假申请单 →'
  if (step.tool === 'meeting_book') return '查看会议室预约单 →'
  if (step.tool === 'gn_meeting_book') return '查看国能会议预约单 →'
  return '查看业务表单 →'
}

async function handleConfirm() {
  const taskId = linkedTaskId.value || props.taskId
  if (!taskId) {
    emit('confirmPending')
    return
  }
  if (task.value) {
    try {
      await confirmTask(taskId, task.value.current_step)
    } catch {
      // 仍跳转 OA，避免确认步骤已完成时按钮无响应
    }
    await load()
  }
  const nodeId = currentNodeId.value
  if (nodeId === 'room' || (task.value && isRoomBookingTask(task.value))) {
    const opened = openOaRoomMeetingApply(taskId)
    if (!opened) {
      alert('无法打开新窗口，请检查浏览器是否拦截弹窗，或手动访问 OA 会议室预约页。')
    }
    return
  }
  if (!task.value) return
  if (isTravelTask(task.value)) {
    const opened = openOaTravelApply(taskId)
    if (!opened) {
      alert('无法打开新窗口，请检查浏览器是否拦截弹窗，或手动访问 OA 差旅申请页。')
    }
    return
  }
  if (isTransportBookTask(task.value)) {
    const opened = openOaTransportBook(taskId)
    if (!opened) {
      alert('无法打开新窗口，请检查浏览器是否拦截弹窗，或手动访问 OA 交通预订页。')
    }
    return
  }
  if (isHotelBookTask(task.value)) {
    const opened = openOaHotelBook(taskId)
    if (!opened) {
      alert('无法打开新窗口，请检查浏览器是否拦截弹窗，或手动访问 OA 酒店预订页。')
    }
    return
  }
  if (isWorkpackageTask(task.value)) {
    const opened = openOaWorkpackageApply(taskId)
    if (!opened) {
      alert('无法打开新窗口，请检查浏览器是否拦截弹窗，或手动访问 OA 工时填报页。')
    }
    return
  }
  if (isLeaveTask(task.value)) {
    const opened = openOaLeaveApply(taskId)
    if (!opened) {
      alert('无法打开新窗口，请检查浏览器是否拦截弹窗，或手动访问 OA 请假申请页。')
    }
    return
  }
  if (nodeId === 'gn_meeting' || isGnMeetingTask(task.value)) {
    const opened = openOaGnMeetingApply(taskId)
    if (!opened) {
      alert('无法打开新窗口，请检查浏览器是否拦截弹窗，或手动访问 OA 国能会议页。')
    }
  }
}

function openFormFromStep(step: TaskStep) {
  const formId = step.result?.form_id as string | undefined
  if (formId) emit('openForm', formId)
}
</script>

<template>
  <Teleport to="body">
  <aside class="task-panel" @click.stop>
    <header class="panel-header">
      <h2>{{ panelTitle }}</h2>
      <button
        type="button"
        class="btn-close"
        aria-label="关闭"
        @mousedown.stop
        @click.stop.prevent="handleClose"
      >
        ×
      </button>
    </header>

    <div v-if="loading" class="loading">加载中…</div>

    <template v-else-if="task">
      <div class="panel-body">
        <div class="status-row">
          <span class="status-badge" :class="oaStatus">{{ oaStatusLabel }}</span>
          <span class="status-hint">OA 办理状态</span>
        </div>

        <p class="goal">{{ task.goal }}</p>

        <section v-if="outcome.gnMeeting && isGnMeetingTask(task)" class="outcome-block">
          <GnMeetingResultPanel :result="outcome.gnMeeting" />
        </section>
        <section v-if="outcome.roomBooking && isRoomBookingTask(task)" class="outcome-block">
          <RoomBookingResultPanel :result="outcome.roomBooking" />
        </section>
        <section v-if="displayItems.length" class="outcome-block">
          <h3 class="outcome-title">提交信息</h3>
          <dl class="info-list">
            <div v-for="item in displayItems" :key="item.label" class="info-row">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>
        </section>

        <div class="progress-section">
          <div class="progress-meta">
            <span>{{ visibleProgress.current }}/{{ visibleProgress.total }} 步骤已完成</span>
            <span v-if="task.replan_count > 0" class="replan">重规划 {{ task.replan_count }} 次</span>
          </div>
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: `${visibleProgress.percent}%` }"
            />
          </div>
        </div>

        <div class="timeline">
          <div
            v-for="step in visibleSteps"
            :key="step.step_id"
            class="step-item"
            :class="step.status"
          >
            <div class="step-head" @click="expandedStep = expandedStep === step.step_id ? null : step.step_id">
              <span class="step-icon">{{ stepIcon(step.status) }}</span>
              <div class="step-info">
                <span class="step-action">{{ step.step_id }}. {{ step.action }}</span>
                <span class="step-status">{{ stepStatusLabel(step.status) }}</span>
              </div>
            </div>

            <div v-if="expandedStep === step.step_id" class="step-detail">
              <div v-if="Object.keys(step.params).length" class="params">
                <div v-for="(val, key) in step.params" :key="String(key)" class="param-row">
                  <span class="param-key">{{ taskFieldLabel(String(key)) }}</span>
                  <span>{{ taskFieldValue(val) }}</span>
                </div>
              </div>
              <div v-if="step.result" class="result">
                <div
                  v-for="(val, key) in step.result"
                  :key="String(key)"
                  v-show="!HIDDEN_RESULT_KEYS.has(String(key))"
                  class="param-row"
                >
                  <span class="param-key">{{ taskFieldLabel(String(key)) }}</span>
                  <span>{{ taskFieldValue(val) }}</span>
                </div>
              </div>
              <button
                v-if="step.result?.form_id"
                type="button"
                class="link-btn"
                @click="openFormFromStep(step)"
              >
                {{ oaFormLinkLabel(step) }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <footer class="panel-footer">
        <p v-if="task.status === 'completed'" class="completed-hint">任务已完成，办理结果见上方提交信息。</p>
        <p v-else-if="oaStatus === 'rejected'" class="rejected-hint">该事项已被驳回或取消。</p>
        <p v-else-if="oaStatus === 'reviewing'" class="reviewing-hint">已提交 OA，正在审核中。</p>
        <p v-else class="draft-hint">信息已确认，可点击「前往 OA 提交」跳转办理。</p>
        <button
          type="button"
          class="btn-secondary"
          @click.stop.prevent="handleClose"
        >
          关闭
        </button>
        <button
          v-if="task.status !== 'completed' && task.status !== 'cancelled'"
          type="button"
          class="btn-danger"
          @click="handleCancel"
        >
          取消任务
        </button>
        <button
          v-if="showOaButton"
          type="button"
          class="btn-primary"
          :disabled="oaSubmitting"
          title="前往 OA 提交"
          @click="handleConfirm"
        >
          前往 OA 提交
        </button>
      </footer>
    </template>

    <template v-else-if="pending">
      <div class="panel-body">
        <div class="status-row">
          <span class="status-badge unsubmitted">未提交</span>
          <span class="status-hint">OA 办理状态</span>
        </div>
        <section v-if="displayItems.length" class="outcome-block">
          <h3 class="outcome-title">待确认信息</h3>
          <dl class="info-list">
            <div v-for="item in displayItems" :key="item.label" class="info-row">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>
        </section>
        <p v-else class="draft-hint">请先在对话中核对并确认该事项信息。</p>
      </div>
      <footer class="panel-footer">
        <p class="draft-hint">信息已核对后，可点击「前往 OA 提交」跳转办理。</p>
        <button
          type="button"
          class="btn-secondary"
          @click.stop.prevent="handleClose"
        >
          关闭
        </button>
        <button
          v-if="showOaButton"
          type="button"
          class="btn-primary"
          :disabled="oaSubmitting"
          title="前往 OA 提交"
          @click="handleConfirm"
        >
          前往 OA 提交
        </button>
      </footer>
    </template>
    <footer v-else class="panel-footer">
      <button
        type="button"
        class="btn-secondary"
        @click.stop.prevent="handleClose"
      >
        关闭
      </button>
    </footer>
  </aside>
  </Teleport>
</template>

<style scoped>
.task-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
  width: min(480px, 100vw);
  background: var(--surface);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  min-height: 0;
  pointer-events: auto;
  box-shadow: -8px 0 24px rgba(15, 23, 42, 0.12);
}

.panel-header {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.panel-header h2 {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 18px;
  font-weight: 600;
}

.btn-close {
  position: relative;
  z-index: 3;
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: var(--bg);
  font-size: 22px;
  color: var(--text-secondary);
  cursor: pointer;
  line-height: 1;
  pointer-events: auto;
}

.btn-close:hover {
  background: color-mix(in srgb, var(--primary) 10%, var(--bg));
  color: var(--text);
}

.loading {
  padding: 32px;
  text-align: center;
  color: var(--text-muted);
}

.panel-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.goal {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text);
}

.status-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.status-badge.unsubmitted {
  color: #92400e;
  background: #fef3c7;
}

.status-badge.reviewing {
  color: #1d4ed8;
  background: #dbeafe;
}

.status-badge.completed {
  color: #047857;
  background: #d1fae5;
}

.status-badge.rejected {
  color: #b91c1c;
  background: #fee2e2;
}

.status-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.outcome-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.outcome-block :deep(.result-card) {
  margin-top: 0;
}

.outcome-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
}

.info-list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-row {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 8px;
  padding: 8px 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.info-row dt {
  color: var(--text-secondary);
}

.info-row dd {
  margin: 0;
  color: var(--text);
  word-break: break-word;
}

.progress-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-meta {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text-secondary);
}

.replan {
  color: var(--accent);
}

.progress-bar {
  height: 2px;
  background: #e2e5e9;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--primary);
  transition: width 0.3s;
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-item {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.step-item.running {
  border-color: #fde68a;
  background: #fffbeb;
}

.step-item.completed {
  border-color: #a7f3d0;
}

.step-head {
  display: flex;
  gap: 12px;
  padding: 12px;
  cursor: pointer;
}

.step-head:hover {
  background: var(--bg);
}

.step-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.step-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.step-action {
  font-size: 13px;
  font-weight: 500;
}

.step-status {
  font-size: 12px;
  color: var(--text-muted);
}

.step-detail {
  padding: 0 12px 12px 44px;
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.param-row {
  display: flex;
  gap: 8px;
}

.param-key {
  color: var(--text-muted);
  min-width: 72px;
  flex-shrink: 0;
}

.result {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.link-btn {
  border: none;
  background: none;
  color: var(--primary);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  padding: 0;
}

.link-btn:hover {
  color: var(--accent);
}

.panel-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.completed-hint,
.rejected-hint,
.reviewing-hint,
.draft-hint {
  width: 100%;
  margin: 0;
  font-size: 13px;
}

.completed-hint {
  color: #059669;
}

.rejected-hint {
  color: #b91c1c;
}

.reviewing-hint,
.draft-hint {
  color: var(--text-secondary);
}

.btn-danger {
  flex: 1;
  height: 40px;
  border: 1px solid var(--primary);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--primary);
  font-size: 14px;
  cursor: pointer;
}

.btn-secondary {
  height: 40px;
  padding: 0 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
}

.panel-footer .btn-primary {
  flex: 1;
}

.panel-footer .btn-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
