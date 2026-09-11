<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ChatTopbar from '@/components/chat/ChatTopbar.vue'
import TaskDetailPanel from '@/components/chat/TaskDetailPanel.vue'
import BusinessFormPanel from '@/components/chat/BusinessFormPanel.vue'
import { fetchTask, listTasks } from '@/services/taskService'
import type { TaskCategory, TaskSummary } from '@/types'
import {
  CATEGORY_ICONS,
  STATUS_LABELS,
} from '@/utils/taskCatalog'
import { isTravelTask, openOaTravelApply } from '@/utils/oaTravel'
import { isWorkpackageTask, openOaWorkpackageApply } from '@/utils/oaWorkpackage'
import { isLeaveTask, openOaLeaveApply } from '@/utils/oaLeave'
import { isGnMeetingTask, isRoomBookingTask, openOaGnMeetingApply, openOaRoomMeetingApply } from '@/utils/oaMeeting'
import { useOaTaskSync } from '@/composables/useOaTaskSync'

type FilterKey = 'all' | 'running' | 'completed' | 'cancelled'

const router = useRouter()

const loading = ref(false)
const tasks = ref<TaskSummary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filter = ref<FilterKey>('all')
const categoryFilter = ref<TaskCategory | 'all'>('all')
const activeTaskId = ref<string | null>(null)
const activeFormId = ref<string | null>(null)

const filterTabs: { key: FilterKey; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'running', label: '进行中' },
  { key: 'completed', label: '已完成' },
  { key: 'cancelled', label: '已取消' },
]

const categoryTabs: { key: TaskCategory | 'all'; label: string }[] = [
  { key: 'all', label: '全部类型' },
  { key: 'travel', label: '差旅办事' },
  { key: 'meeting', label: '会议室预约' },
  { key: 'gn_meeting', label: '国能会议' },
  { key: 'workpackage', label: '工时填报' },
  { key: 'leave', label: '请假申请' },
  { key: 'info_collect', label: '信息收集' },
  { key: 'email', label: '邮件撰写' },
]

const stats = computed(() => {
  const running = tasks.value.filter((t) => t.status === 'running').length
  const completed = tasks.value.filter((t) => t.status === 'completed').length
  return { running, completed, total: total.value }
})

const emptyHint = computed(() => {
  const map: Record<FilterKey, string> = {
    all: '暂无任务记录。在对话中办理差旅、会议、工包、邮件等业务后，任务会自动出现在这里。',
    running: '暂无进行中的任务。',
    completed: '暂无已完成的任务。',
    cancelled: '暂无已取消的任务。',
  }
  return map[filter.value]
})

async function loadTasks() {
  loading.value = true
  try {
    const status = filter.value === 'all' ? undefined : filter.value
    const category = categoryFilter.value === 'all' ? undefined : categoryFilter.value
    const res = await listTasks({ status, category, page: page.value, page_size: pageSize })
    if (res.code === 200) {
      tasks.value = res.data.items
      total.value = res.data.total
    }
  } finally {
    loading.value = false
  }
}

watch([filter, categoryFilter], () => {
  page.value = 1
  loadTasks()
})

onMounted(loadTasks)

useOaTaskSync(() => {
  loadTasks()
})

function formatTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function statusClass(status: TaskSummary['status']) {
  return `status-${status}`
}

function openDetail(taskId: string) {
  activeFormId.value = null
  activeTaskId.value = taskId
}

function closePanels() {
  activeTaskId.value = null
  activeFormId.value = null
  loadTasks()
}

function goToChat(sessionId: string, taskId?: string) {
  router.push({
    name: 'chat',
    query: {
      session: sessionId,
      ...(taskId ? { task: taskId } : {}),
    },
  })
}

function openForm(formId: string) {
  activeTaskId.value = null
  activeFormId.value = formId
}

async function handleOpenOa(
  taskId: string,
  category: 'travel' | 'workpackage' | 'leave' | 'meeting' | 'gn_meeting',
) {
  const res = await fetchTask(taskId)
  if (res.code !== 200) return
  if (category === 'travel' && isTravelTask(res.data)) {
    openOaTravelApply(taskId)
    return
  }
  if (category === 'workpackage' && isWorkpackageTask(res.data)) {
    openOaWorkpackageApply(taskId)
    return
  }
  if (category === 'leave' && isLeaveTask(res.data)) {
    openOaLeaveApply(taskId)
    return
  }
  if (category === 'gn_meeting' && isGnMeetingTask(res.data)) {
    openOaGnMeetingApply(taskId)
    return
  }
  if (category === 'meeting' && isRoomBookingTask(res.data)) {
    openOaRoomMeetingApply(taskId)
  }
}

function prevPage() {
  if (page.value > 1) {
    page.value -= 1
    loadTasks()
  }
}

function nextPage() {
  if (page.value * pageSize < total.value) {
    page.value += 1
    loadTasks()
  }
}
</script>

<template>
  <div class="app-shell my-tasks-page">
    <section class="main">
      <ChatTopbar />

      <div class="page-main">
        <header class="page-header">
          <div>
            <h1>我的任务</h1>
            <p class="subtitle">
              汇总通过智能办公助手创建的所有办事任务：差旅申请、机票/酒店预订、工时填报、请假申请、会议预约、邮件撰写等，随时查看办理进度与历史记录。
            </p>
          </div>
          <button type="button" class="btn-back" @click="router.push({ name: 'chat' })">
            返回对话
          </button>
        </header>

        <div class="stats-row">
          <div class="stat-card">
            <span class="stat-value">{{ total }}</span>
            <span class="stat-label">当前列表</span>
          </div>
          <div class="stat-card accent">
            <span class="stat-value">{{ stats.running }}</span>
            <span class="stat-label">本页进行中</span>
          </div>
          <div class="stat-card success">
            <span class="stat-value">{{ stats.completed }}</span>
            <span class="stat-label">本页已完成</span>
          </div>
        </div>

        <div class="filter-bar">
          <button
            v-for="tab in filterTabs"
            :key="tab.key"
            type="button"
            class="filter-tab"
            :class="{ active: filter === tab.key }"
            @click="filter = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <div class="category-bar">
          <button
            v-for="tab in categoryTabs"
            :key="tab.key"
            type="button"
            class="category-tab"
            :class="{ active: categoryFilter === tab.key }"
            @click="categoryFilter = tab.key"
          >
            <span v-if="tab.key !== 'all'" class="cat-icon">{{ CATEGORY_ICONS[tab.key] }}</span>
            {{ tab.label }}
          </button>
        </div>

        <div v-if="loading" class="state-box">加载中…</div>
        <div v-else-if="tasks.length === 0" class="state-box empty">{{ emptyHint }}</div>

        <div v-else class="task-list">
          <article v-for="task in tasks" :key="task.id" class="task-card">
            <div class="card-left">
              <span class="category-icon">{{ CATEGORY_ICONS[task.category] }}</span>
            </div>
            <div class="card-body">
              <div class="card-head">
                <span class="category-label">{{ task.category_label }}</span>
                <span class="status-badge" :class="statusClass(task.status)">
                  {{ STATUS_LABELS[task.status] }}
                </span>
              </div>
              <h3 class="task-goal">{{ task.goal }}</h3>
              <div class="task-tags">
                <span v-for="tag in task.tags" :key="tag" class="tag">{{ tag }}</span>
              </div>
              <div class="progress-row">
                <div class="progress-bar">
                  <div class="progress-fill" :style="{ width: `${task.progress_percent}%` }" />
                </div>
                <span class="progress-text">
                  {{ task.completed_steps }}/{{ task.total_steps }} 步骤 · {{ task.progress_percent }}%
                </span>
              </div>
              <div class="meta-row">
                <span class="task-id">{{ task.id }}</span>
                <span class="task-time">{{ formatTime(task.created_at) }}</span>
              </div>
            </div>
            <div class="card-actions">
              <button type="button" class="action-btn" @click="openDetail(task.id)">
                查看详情
              </button>
              <button
                type="button"
                class="action-btn secondary"
                @click="goToChat(task.session_id, task.id)"
              >
                回到对话
              </button>
              <button
                v-if="task.category === 'travel' && task.status === 'running'"
                type="button"
                class="action-btn secondary"
                @click="handleOpenOa(task.id, 'travel')"
              >
                OA 差旅页
              </button>
              <button
                v-if="task.category === 'workpackage' && task.status === 'running'"
                type="button"
                class="action-btn secondary"
                @click="handleOpenOa(task.id, 'workpackage')"
              >
                OA 工时页
              </button>
              <button
                v-if="task.category === 'leave' && task.status === 'running'"
                type="button"
                class="action-btn secondary"
                @click="handleOpenOa(task.id, 'leave')"
              >
                OA 请假页
              </button>
              <button
                v-if="task.category === 'meeting' && task.status === 'running'"
                type="button"
                class="action-btn secondary"
                @click="handleOpenOa(task.id, 'meeting')"
              >
                OA 会议室页
              </button>
              <button
                v-if="task.category === 'gn_meeting' && task.status === 'running'"
                type="button"
                class="action-btn secondary"
                @click="handleOpenOa(task.id, 'gn_meeting')"
              >
                OA 国能会页
              </button>
            </div>
          </article>
        </div>

        <footer v-if="total > pageSize" class="pagination">
          <button type="button" :disabled="page <= 1" @click="prevPage">上一页</button>
          <span>{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
          <button type="button" :disabled="page * pageSize >= total" @click="nextPage">下一页</button>
        </footer>
      </div>
    </section>

    <TaskDetailPanel
      v-if="activeTaskId"
      :task-id="activeTaskId"
      @dismiss="closePanels"
      @open-form="openForm"
    />
    <BusinessFormPanel v-if="activeFormId" :form-id="activeFormId" @close="closePanels" />
  </div>
</template>

<style scoped>
.my-tasks-page {
  flex-direction: row;
  min-height: 100vh;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}

.page-main {
  flex: 1;
  max-width: 960px;
  width: 100%;
  margin: 0 auto;
  padding: 24px 24px 48px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 8px;
}

.subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  max-width: 640px;
}

.btn-back {
  flex-shrink: 0;
  height: 36px;
  padding: 0 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 13px;
  cursor: pointer;
}

.stats-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  flex: 1;
  padding: 14px 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
}

.stat-card.accent .stat-value {
  color: #2563eb;
}

.stat-card.success .stat-value {
  color: #059669;
}

.filter-bar,
.category-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.filter-tab,
.category-tab {
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  font-size: 13px;
  cursor: pointer;
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.filter-tab.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.category-tab.active {
  background: #eff6ff;
  border-color: #93c5fd;
  color: #1d4ed8;
  font-weight: 600;
}

.cat-icon {
  font-size: 14px;
}

.state-box {
  text-align: center;
  padding: 64px 24px;
  color: var(--text-muted);
  font-size: 14px;
}

.state-box.empty {
  line-height: 1.6;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: box-shadow 0.15s;
}

.task-card:hover {
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
}

.card-left {
  flex-shrink: 0;
}

.category-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: var(--bg);
  font-size: 22px;
}

.card-body {
  flex: 1;
  min-width: 0;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.category-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.status-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.status-running {
  background: #eff6ff;
  color: #2563eb;
}

.status-completed {
  background: #ecfdf5;
  color: #059669;
}

.status-cancelled {
  background: #f3f4f6;
  color: #6b7280;
}

.status-failed {
  background: #fef2f2;
  color: #dc2626;
}

.task-goal {
  margin: 0 0 8px;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
}

.task-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.tag {
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg);
  font-size: 11px;
  color: var(--text-secondary);
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: var(--bg);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  transition: width 0.2s;
}

.progress-text {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.meta-row {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-muted);
}

.card-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
  justify-content: center;
}

.action-btn {
  padding: 8px 14px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #fff;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.action-btn.secondary {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-secondary);
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 24px;
  font-size: 13px;
  color: var(--text-secondary);
}

.pagination button {
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  cursor: pointer;
}

.pagination button:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
