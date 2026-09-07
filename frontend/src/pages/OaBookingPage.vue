<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'
import { approveOaApplication, fetchTask, submitOaApplication } from '@/services/taskService'
import { fetchForm } from '@/services/formService'
import { formFieldLabels } from '@/mocks/forms'
import type { Task } from '@/types'
import {
  buildOaNotifyPayload,
  detectOaPhase,
  isPrimaryButtonDisabled,
  isPrimaryButtonSubmittedStyle,
  notifyAssistantOaUpdate,
  primaryButtonLabel,
  type OaPhase,
} from '@/utils/oaDemo'
import { findBookingFormId, type BookingKind } from '@/utils/oaBooking'
import { formatOaDate } from '@/utils/oaTravel'

const props = defineProps<{
  bookingType: BookingKind
}>()

const route = useRoute()
const auth = useAuthStore()

const loading = ref(true)
const error = ref<string | null>(null)
const task = ref<Task | null>(null)
const fields = ref<Record<string, string>>({})
const phase = ref<OaPhase>('draft')
const submitting = ref(false)
const toastMessage = ref<string | null>(null)

const taskId = computed(() => String(route.params.taskId ?? ''))
const applyTool = computed(() => (props.bookingType === 'transport' ? 'flight_book' : 'hotel_book'))
const formType = computed(() => (props.bookingType === 'transport' ? 'transport_book' : 'hotel_book'))
const labels = computed(() => formFieldLabels[formType.value] ?? {})

const pageTitle = computed(() =>
  props.bookingType === 'transport' ? '交通预订' : '酒店预订',
)

const navLabel = computed(() =>
  props.bookingType === 'transport' ? '交通预订' : '酒店预订',
)

const applicationNo = computed(() => {
  const receipt = task.value?.steps.find((s) => s.tool === applyTool.value)?.result?.receipt_id
  if (typeof receipt === 'string' && receipt) return receipt
  const prefix = props.bookingType === 'transport' ? 'TR' : 'HT'
  return `${prefix}-${taskId.value.replace(/^task_/, '').toUpperCase()}`
})

const statusBadge = computed(() => {
  if (phase.value === 'approved') return { label: '已确认', class: 'approved' }
  if (phase.value === 'submitted') return { label: '确认中', class: 'pending' }
  return { label: '待提交', class: 'draft' }
})

const approvalChain = computed(() => {
  const name = auth.user?.display_name ?? '—'
  const nodes = [
    { role: '预订人', name, status: 'done' as const, time: '刚刚' },
    {
      role: props.bookingType === 'transport' ? '票务审核' : '酒店审核',
      name: '国能商旅平台',
      status: (phase.value === 'approved' ? 'done' : 'pending') as 'done' | 'pending',
      time: phase.value === 'approved' ? '刚刚' : '—',
    },
  ]
  if (phase.value === 'submitted') {
    return nodes
  }
  if (phase.value === 'approved') {
    return nodes.map((node) => ({ ...node, status: 'done' as const, time: '刚刚' }))
  }
  return nodes
})

async function load() {
  loading.value = true
  error.value = null
  try {
    const taskRes = await fetchTask(taskId.value)
    if (taskRes.code !== 200 || !taskRes.data) {
      error.value = taskRes.message || '任务不存在'
      return
    }
    task.value = taskRes.data
    phase.value = detectOaPhase(taskRes.data)
    const formId = findBookingFormId(taskRes.data, applyTool.value)
    if (!formId) {
      error.value = '未找到关联的预订表单'
      return
    }
    const formRes = await fetchForm(formId)
    if (formRes.code !== 200 || !formRes.data) {
      error.value = formRes.message || '表单加载失败'
      return
    }
    fields.value = { ...formRes.data.fields }
  } catch {
    error.value = '加载失败，请返回助手重试'
  } finally {
    loading.value = false
  }
}

async function handlePrimaryClick() {
  if (!task.value || submitting.value || isPrimaryButtonDisabled(phase.value, submitting)) {
    return
  }

  submitting.value = true
  toastMessage.value = null
  try {
    if (phase.value === 'draft') {
      const res = await submitOaApplication(taskId.value)
      if (res.code !== 200 || !res.data) {
        error.value = res.message || '提交失败，请重试'
        return
      }
      task.value = res.data.task
      phase.value = 'submitted'
      toastMessage.value = `${pageTitle.value} ${applicationNo.value} 已提交，再次点击可模拟确认完成。`
      notifyAssistantOaUpdate(buildOaNotifyPayload(res.data, taskId.value, 'submitted'))
      return
    }

    if (phase.value === 'submitted') {
      const res = await approveOaApplication(taskId.value)
      if (res.code !== 200 || !res.data) {
        error.value = res.message || '确认失败，请重试'
        return
      }
      task.value = res.data.task
      phase.value = 'approved'
      toastMessage.value = '预订已确认，状态已同步至智能办公助手。'
      notifyAssistantOaUpdate(buildOaNotifyPayload(res.data, taskId.value, 'completed'))
    }
  } catch {
    error.value = '操作失败，请返回助手重试'
  } finally {
    submitting.value = false
  }
}

function closeWindow() {
  window.close()
}

onMounted(load)
</script>

<template>
  <div class="oa-shell">
    <header class="oa-topbar">
      <div class="oa-brand">
        <span class="oa-logo">CE</span>
        <div>
          <div class="oa-title">国能集团 · 商旅预订平台</div>
          <div class="oa-subtitle">China Energy Travel Booking · OA Module</div>
        </div>
      </div>
      <div class="oa-user">
        <span>{{ auth.user?.display_name ?? '员工' }}</span>
        <span class="oa-user-id">{{ auth.user?.employee_id ?? '' }}</span>
      </div>
    </header>

    <nav class="oa-nav">
      <span class="nav-item">首页</span>
      <span class="nav-sep">/</span>
      <span class="nav-item">商旅预订</span>
      <span class="nav-sep">/</span>
      <span class="nav-item active">{{ navLabel }}</span>
    </nav>

    <main class="oa-main">
      <div v-if="loading" class="oa-state">正在同步智能助手填报数据…</div>
      <div v-else-if="error" class="oa-state error">{{ error }}</div>

      <template v-else>
        <div v-if="toastMessage" class="toast">{{ toastMessage }}</div>

        <div class="sync-banner">
          <span class="sync-icon">↗</span>
          <div>
            <strong>数据已从「智能办公助手」同步</strong>
            <p>请核对乘客/入住信息后提交，确认后将同步回助手任务进度。</p>
          </div>
          <span class="sync-tag">自动同步</span>
        </div>

        <section class="oa-card">
          <header class="card-head">
            <h1>{{ pageTitle }}单</h1>
            <div class="head-meta">
              <span class="badge" :class="statusBadge.class">{{ statusBadge.label }}</span>
              <span class="app-no">单号：{{ applicationNo }}</span>
            </div>
          </header>

          <template v-if="bookingType === 'transport'">
            <div class="section-title">一、乘客信息</div>
            <table class="oa-table">
              <tbody>
                <tr>
                  <th>{{ labels.passenger_name }}</th>
                  <td>{{ fields.passenger_name || '—' }}</td>
                  <th>{{ labels.id_number }}</th>
                  <td>{{ fields.id_number || '—' }}</td>
                </tr>
                <tr>
                  <th>{{ labels.phone }}</th>
                  <td colspan="3">{{ fields.phone || '—' }}</td>
                </tr>
              </tbody>
            </table>

            <div class="section-title">二、行程与航班</div>
            <table class="oa-table">
              <tbody>
                <tr>
                  <th>{{ labels.origin }}</th>
                  <td>{{ fields.origin || '—' }}</td>
                  <th>{{ labels.destination }}</th>
                  <td>{{ fields.destination || '—' }}</td>
                </tr>
                <tr>
                  <th>{{ labels.departure_date }}</th>
                  <td>{{ formatOaDate(fields.departure_date) }}</td>
                  <th>{{ labels.departure_time }}</th>
                  <td>{{ fields.departure_time || '—' }}</td>
                </tr>
                <tr>
                  <th>{{ labels.flight_no }}</th>
                  <td>{{ fields.flight_no || '—' }}</td>
                  <th>{{ labels.amount }}</th>
                  <td><strong class="amount">{{ fields.amount || '—' }}</strong> 元</td>
                </tr>
              </tbody>
            </table>
          </template>

          <template v-else>
            <div class="section-title">一、入住人信息</div>
            <table class="oa-table">
              <tbody>
                <tr>
                  <th>{{ labels.guest_name }}</th>
                  <td>{{ fields.guest_name || '—' }}</td>
                  <th>{{ labels.id_number }}</th>
                  <td>{{ fields.id_number || '—' }}</td>
                </tr>
                <tr>
                  <th>{{ labels.phone }}</th>
                  <td colspan="3">{{ fields.phone || '—' }}</td>
                </tr>
              </tbody>
            </table>

            <div class="section-title">二、酒店信息</div>
            <table class="oa-table">
              <tbody>
                <tr>
                  <th>{{ labels.hotel_name }}</th>
                  <td colspan="3">{{ fields.hotel_name || '—' }}</td>
                </tr>
                <tr>
                  <th>{{ labels.room_type }}</th>
                  <td>{{ fields.room_type || '—' }}</td>
                  <th>{{ labels.amount }}</th>
                  <td><strong class="amount">{{ fields.amount || '—' }}</strong> 元/晚</td>
                </tr>
                <tr>
                  <th>{{ labels.check_in }}</th>
                  <td>{{ formatOaDate(fields.check_in) }}</td>
                  <th>{{ labels.check_out }}</th>
                  <td>{{ formatOaDate(fields.check_out) }}</td>
                </tr>
              </tbody>
            </table>
          </template>

          <div class="section-title">三、确认流程</div>
          <div class="approval-flow">
            <div
              v-for="(node, idx) in approvalChain"
              :key="node.role"
              class="approval-node"
              :class="node.status"
            >
              <div class="node-dot">{{ idx + 1 }}</div>
              <div class="node-body">
                <div class="node-role">{{ node.role }}</div>
                <div class="node-name">{{ node.name }}</div>
                <div class="node-time">{{ node.time }}</div>
              </div>
            </div>
          </div>
        </section>

        <footer class="oa-footer">
          <p class="footer-note">
            演示：首次点击提交进入确认中；再次点击可模拟完成并同步回智能办公助手（进度 2/2）。
          </p>
          <div class="footer-actions">
            <button type="button" class="btn-secondary" @click="closeWindow">关闭窗口</button>
            <button
              type="button"
              class="btn-primary"
              :class="{ submitted: isPrimaryButtonSubmittedStyle(phase) }"
              :disabled="isPrimaryButtonDisabled(phase, submitting)"
              @click="handlePrimaryClick"
            >
              {{ primaryButtonLabel(phase, submitting) }}
            </button>
          </div>
        </footer>
      </template>
    </main>
  </div>
</template>

<style scoped>
.oa-shell {
  min-height: 100vh;
  background: #f0f2f5;
  color: #1f2937;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.oa-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  background: #c41e3a;
  color: #fff;
}

.oa-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.oa-logo {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}

.oa-title {
  font-size: 16px;
  font-weight: 600;
}

.oa-subtitle {
  font-size: 11px;
  opacity: 0.85;
}

.oa-user {
  text-align: right;
  font-size: 13px;
}

.oa-user-id {
  display: block;
  font-size: 11px;
  opacity: 0.85;
}

.oa-nav {
  padding: 10px 32px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  font-size: 13px;
  color: #6b7280;
}

.nav-item.active {
  color: #c41e3a;
  font-weight: 600;
}

.nav-sep {
  margin: 0 8px;
}

.oa-main {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 32px 48px;
}

.oa-state {
  padding: 48px;
  text-align: center;
  color: #6b7280;
}

.oa-state.error {
  color: #dc2626;
}

.toast {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #ecfdf5;
  border: 1px solid #86efac;
  border-radius: 8px;
  color: #166534;
  font-size: 13px;
}

.sync-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  margin-bottom: 20px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  font-size: 13px;
}

.sync-icon {
  font-size: 20px;
  color: #2563eb;
}

.sync-tag {
  margin-left: auto;
  padding: 2px 8px;
  background: #dbeafe;
  border-radius: 4px;
  font-size: 11px;
  color: #1d4ed8;
  white-space: nowrap;
}

.oa-card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  padding: 24px;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 2px solid #c41e3a;
}

.card-head h1 {
  margin: 0;
  font-size: 20px;
}

.head-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  font-size: 12px;
}

.badge {
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.badge.draft {
  background: #f3f4f6;
  color: #6b7280;
}

.badge.pending {
  background: #fef3c7;
  color: #b45309;
}

.badge.approved {
  background: #dcfce7;
  color: #15803d;
}

.section-title {
  margin: 20px 0 10px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.oa-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.oa-table th,
.oa-table td {
  border: 1px solid #e5e7eb;
  padding: 10px 12px;
  text-align: left;
}

.oa-table th {
  width: 120px;
  background: #f9fafb;
  color: #6b7280;
  font-weight: 500;
}

.amount {
  color: #c41e3a;
  font-size: 15px;
}

.approval-flow {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.approval-node {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  min-width: 160px;
}

.approval-node.done {
  border-color: #86efac;
  background: #f0fdf4;
}

.node-dot {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: #c41e3a;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.approval-node.pending .node-dot {
  background: #d1d5db;
}

.node-role {
  font-size: 11px;
  color: #6b7280;
}

.node-name {
  font-size: 13px;
  font-weight: 600;
}

.node-time {
  font-size: 11px;
  color: #9ca3af;
}

.oa-footer {
  margin-top: 24px;
}

.footer-note {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 12px;
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-secondary,
.btn-primary {
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  border: none;
}

.btn-secondary {
  background: #fff;
  border: 1px solid #d1d5db;
  color: #374151;
}

.btn-primary {
  background: #c41e3a;
  color: #fff;
}

.btn-primary.submitted {
  background: #9ca3af;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
