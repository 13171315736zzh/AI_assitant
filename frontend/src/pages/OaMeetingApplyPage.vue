<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'
import { approveOaApplication, fetchTask, submitOaApplication } from '@/services/taskService'
import { fetchForm } from '@/services/formService'
import { formFieldLabels } from '@/mocks/forms'
import type { Task } from '@/types'
import {
  buildMeetingApprovalChain,
  detectOaPhase,
  isPrimaryButtonDisabled,
  isPrimaryButtonSubmittedStyle,
  notifyAssistantOaUpdate,
  primaryButtonLabel,
  type OaPhase,
} from '@/utils/oaDemo'
import {
  findMeetingFormId,
  findGnMeetingFormId,
  findRoomSelection,
  isGnMeetingTask,
} from '@/utils/oaMeeting'

const route = useRoute()
const auth = useAuthStore()

const loading = ref(true)
const error = ref<string | null>(null)
const task = ref<Task | null>(null)
const fields = ref<Record<string, string>>({})
const roomSelection = ref<{ room: string; time: string } | null>(null)
const phase = ref<OaPhase>('draft')
const submitting = ref(false)
const toastMessage = ref<string | null>(null)

const taskId = computed(() => String(route.params.taskId ?? ''))
const labels = formFieldLabels.meeting

const isGnMeeting = computed(() => (task.value ? isGnMeetingTask(task.value) : false))

const systemTitle = computed(() =>
  isGnMeeting.value ? '国能集团 · 国能会议系统' : '国能集团 · 智慧会议系统',
)

const systemSubtitle = computed(() =>
  isGnMeeting.value
    ? 'China Energy Video Meeting · OA Module'
    : 'China Energy Meeting Room Booking · OA Module',
)

const navSection = computed(() => (isGnMeeting.value ? '国能会议' : '会议管理'))

const formTitle = computed(() =>
  isGnMeeting.value ? '国能会议预约单' : '会议室预约单',
)

const applicationNo = computed(() => {
  const tool = isGnMeeting.value ? 'gn_meeting_book' : 'meeting_book'
  const receipt = task.value?.steps.find((s) => s.tool === tool)?.result?.receipt_id
  if (typeof receipt === 'string' && receipt) return receipt
  const prefix = isGnMeeting.value ? 'GN' : 'MR'
  return `${prefix}-${taskId.value.replace(/^task_/, '').toUpperCase()}`
})

const approvalChain = computed(() =>
  buildMeetingApprovalChain(auth.user?.display_name ?? '—', phase.value, {
    gnMeeting: isGnMeeting.value,
  }),
)

const statusBadge = computed(() => {
  if (phase.value === 'approved') return { label: '已通过', class: 'approved' }
  if (phase.value === 'submitted') return { label: '审批中', class: 'pending' }
  return { label: '草稿', class: 'draft' }
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
    roomSelection.value = isGnMeetingTask(taskRes.data)
      ? null
      : findRoomSelection(taskRes.data)

    const formId = isGnMeetingTask(taskRes.data)
      ? findGnMeetingFormId(taskRes.data)
      : findMeetingFormId(taskRes.data)
    if (!formId) {
      error.value = isGnMeetingTask(taskRes.data)
        ? '未找到关联的国能会议表单'
        : '未找到关联的会议室预约表单'
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
  if (!task.value || submitting.value || isPrimaryButtonDisabled(phase.value, submitting.value)) {
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
      const label = isGnMeeting.value ? '国能会议预约' : '会议室预约'
      toastMessage.value = `${label} ${applicationNo.value} 已进入 OA 审批流程（演示）。再次点击灰色按钮可模拟审批通过。`
      notifyAssistantOaUpdate({
        sessionId: res.data.session_id,
        taskId: taskId.value,
        action: 'submitted',
      })
      return
    }

    if (phase.value === 'submitted') {
      const res = await approveOaApplication(taskId.value)
      if (res.code !== 200 || !res.data) {
        error.value = res.message || '审批完成失败，请重试'
        return
      }
      task.value = res.data.task
      phase.value = 'approved'
      toastMessage.value = '审批已全部通过，状态已同步至智能办公助手。'
      notifyAssistantOaUpdate({
        sessionId: res.data.session_id,
        taskId: taskId.value,
        action: 'completed',
      })
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
          <div class="oa-title">{{ systemTitle }}</div>
          <div class="oa-subtitle">{{ systemSubtitle }}</div>
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
      <span class="nav-item">{{ navSection }}</span>
      <span class="nav-sep">/</span>
      <span class="nav-item active">{{ isGnMeeting ? '国能会议预约' : '会议室预约' }}</span>
    </nav>

    <main class="oa-main">
      <div v-if="loading" class="oa-state">正在同步智能助手填报数据…</div>
      <div v-else-if="error" class="oa-state error">{{ error }}</div>

      <template v-else>
        <div class="sync-banner">
          <span class="sync-icon">↗</span>
          <div>
            <strong>数据已从「智能办公助手」同步</strong>
            <p>以下内容为助手根据对话自动预填，请在 OA 系统中核对后提交审批。</p>
          </div>
          <span class="sync-tag">自动同步</span>
        </div>

        <section class="oa-card">
          <header class="card-head">
            <h1>{{ formTitle }}</h1>
            <div class="head-meta">
              <span class="badge" :class="statusBadge.class">{{ statusBadge.label }}</span>
              <span class="app-no">单号：{{ applicationNo }}</span>
            </div>
          </header>

          <div class="section-title">一、基本信息</div>
          <table class="oa-table">
            <tbody>
              <tr>
                <th>预约人</th>
                <td>{{ auth.user?.display_name ?? '—' }}</td>
                <th>工号</th>
                <td>{{ auth.user?.employee_id ?? '—' }}</td>
              </tr>
              <tr>
                <th>所属部门</th>
                <td>智能矿山事业部</td>
                <th>会议类型</th>
                <td>{{ isGnMeeting ? '国能会（线上/视频）' : '线下会议室' }}</td>
              </tr>
              <tr>
                <th>{{ labels.subject }}</th>
                <td colspan="3">{{ fields.subject || '—' }}</td>
              </tr>
              <tr v-if="!isGnMeeting">
                <th>{{ labels.room }}</th>
                <td>{{ fields.room || (roomSelection ? `${roomSelection.room} 会议室` : '—') }}</td>
                <th>时段</th>
                <td>{{ roomSelection?.time || fields.start_time || '—' }}</td>
              </tr>
              <tr>
                <th>{{ labels.start_time }}</th>
                <td>{{ fields.start_time || '—' }}</td>
                <th>{{ labels.end_time }}</th>
                <td>{{ fields.end_time || '—' }}</td>
              </tr>
              <tr>
                <th>{{ labels.attendees }}</th>
                <td colspan="3">{{ fields.attendees || '—' }}</td>
              </tr>
            </tbody>
          </table>

          <div v-if="isGnMeeting" class="section-title">二、国能会接入说明</div>
          <p v-if="isGnMeeting" class="gn-hint">
            审批通过后，系统将自动创建国能会会议号并通知参会人员。请确认主题、时间与参会名单无误。
          </p>

          <div class="section-title">{{ isGnMeeting ? '三' : '二' }}、审批流程</div>
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
            演示说明：首次点击「提交审批」进入审批中；再次点击灰色「已提交审批」可模拟全流程通过并同步回助手。
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

        <div v-if="toastMessage" class="submit-toast">
          <strong>{{ phase === 'approved' ? '审批完成' : '提交成功' }}</strong>
          <p>{{ toastMessage }}</p>
        </div>
      </template>
    </main>
  </div>
</template>

<style scoped>
.oa-shell {
  min-height: 100vh;
  background: #eef2f7;
  color: #1f2937;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.oa-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  height: 64px;
  background: linear-gradient(90deg, #0b3d91 0%, #1565c0 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(11, 61, 145, 0.25);
}

.oa-brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.oa-logo {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 1px;
}

.oa-title {
  font-size: 18px;
  font-weight: 600;
}

.oa-subtitle {
  font-size: 11px;
  opacity: 0.75;
  margin-top: 2px;
}

.oa-user {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-size: 14px;
}

.oa-user-id {
  font-size: 12px;
  opacity: 0.8;
}

.oa-nav {
  padding: 12px 32px;
  font-size: 13px;
  color: #64748b;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}

.nav-item.active {
  color: #1565c0;
  font-weight: 600;
}

.nav-sep {
  margin: 0 8px;
  color: #cbd5e1;
}

.oa-main {
  max-width: 1080px;
  margin: 0 auto;
  padding: 24px 24px 48px;
}

.oa-state {
  text-align: center;
  padding: 80px 24px;
  color: #64748b;
  font-size: 15px;
}

.oa-state.error {
  color: #dc2626;
}

.sync-banner {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px 20px;
  margin-bottom: 20px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
}

.sync-banner strong {
  display: block;
  color: #1e40af;
  margin-bottom: 4px;
}

.sync-banner p {
  margin: 0;
  font-size: 13px;
  color: #475569;
}

.sync-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #2563eb;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.sync-tag {
  margin-left: auto;
  align-self: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.oa-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}

.card-head h1 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.head-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.badge {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.badge.draft {
  background: #fef3c7;
  color: #b45309;
}

.badge.pending {
  background: #dbeafe;
  color: #1d4ed8;
}

.badge.approved {
  background: #dcfce7;
  color: #15803d;
}

.app-no {
  font-size: 13px;
  color: #64748b;
}

.section-title {
  padding: 16px 24px 8px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  border-top: 1px solid #f1f5f9;
}

.section-title:first-of-type {
  border-top: none;
}

.oa-table {
  width: calc(100% - 48px);
  margin: 0 24px 8px;
  border-collapse: collapse;
  font-size: 14px;
}

.oa-table th,
.oa-table td {
  border: 1px solid #e2e8f0;
  padding: 10px 14px;
  text-align: left;
  vertical-align: top;
}

.oa-table > tbody > tr > th {
  width: 120px;
  background: #f8fafc;
  color: #475569;
  font-weight: 500;
}

.gn-hint {
  margin: 0 24px 12px;
  padding: 12px 14px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 6px;
  font-size: 13px;
  color: #166534;
}

.approval-flow {
  display: flex;
  gap: 0;
  padding: 8px 24px 24px;
  overflow-x: auto;
}

.approval-node {
  display: flex;
  gap: 10px;
  flex: 1;
  min-width: 140px;
  position: relative;
  padding-right: 16px;
}

.approval-node:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 14px;
  left: 28px;
  right: 0;
  height: 2px;
  background: #e2e8f0;
  z-index: 0;
}

.approval-node.done:not(:last-child)::after {
  background: #93c5fd;
}

.node-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  z-index: 1;
}

.approval-node.done .node-dot {
  background: #2563eb;
  color: #fff;
}

.node-body {
  padding-top: 2px;
}

.node-role {
  font-size: 12px;
  color: #64748b;
}

.node-name {
  font-size: 14px;
  font-weight: 600;
  margin-top: 2px;
}

.node-time {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.oa-footer {
  margin-top: 20px;
  padding: 16px 20px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.footer-note {
  margin: 0;
  font-size: 12px;
  color: #94a3b8;
}

.footer-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.btn-primary,
.btn-secondary {
  height: 38px;
  padding: 0 20px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  border: none;
}

.btn-primary {
  background: #1565c0;
  color: #fff;
}

.btn-primary:disabled {
  background: #94a3b8;
  cursor: default;
}

.btn-primary.submitted:not(:disabled) {
  background: #94a3b8;
  cursor: pointer;
}

.btn-primary.submitted:not(:disabled):hover {
  background: #64748b;
}

.btn-secondary {
  background: #fff;
  border: 1px solid #cbd5e1;
  color: #475569;
}

.submit-toast {
  position: fixed;
  bottom: 32px;
  right: 32px;
  width: 320px;
  padding: 16px 20px;
  background: #fff;
  border: 1px solid #86efac;
  border-left: 4px solid #059669;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
}

.submit-toast strong {
  color: #059669;
  display: block;
  margin-bottom: 4px;
}

.submit-toast p {
  margin: 0;
  font-size: 13px;
  color: #475569;
}
</style>
