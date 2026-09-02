<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Task, TaskStep } from '@/types'
import { fetchTask, cancelTask, confirmTask } from '@/services/taskService'
import {
  HIDDEN_RESULT_KEYS,
  taskFieldLabel,
  taskFieldValue,
} from '@/utils/taskFieldLabels'
import { isTravelTask, openOaTravelApply } from '@/utils/oaTravel'

const props = defineProps<{ taskId: string }>()

const emit = defineEmits<{
  close: []
  openForm: [formId: string]
}>()

const task = ref<Task | null>(null)
const loading = ref(false)
const expandedStep = ref<number | null>(null)

async function load() {
  loading.value = true
  try {
    const res = await fetchTask(props.taskId)
    if (res.code === 200) task.value = res.data
  } finally {
    loading.value = false
  }
}

watch(() => props.taskId, load, { immediate: true })

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
  if (!confirm('确认取消此任务？')) return
  const res = await cancelTask(props.taskId)
  if (res.code === 200) await load()
}

async function handleConfirm() {
  if (!task.value) return
  const res = await confirmTask(props.taskId, task.value.current_step)
  if (res.code !== 200) return
  await load()
  if (task.value && isTravelTask(task.value)) {
    const opened = openOaTravelApply(props.taskId)
    if (!opened) {
      alert('无法打开新窗口，请检查浏览器是否拦截弹窗，或手动访问 OA 差旅申请页。')
    }
  }
}

function openFormFromStep(step: TaskStep) {
  const formId = step.result?.form_id as string | undefined
  if (formId) emit('openForm', formId)
}
</script>

<template>
  <aside class="task-panel">
    <header class="panel-header">
      <h2>任务详情</h2>
      <button type="button" class="btn-close" aria-label="关闭" @click="emit('close')">×</button>
    </header>

    <div v-if="loading" class="loading">加载中…</div>

    <template v-else-if="task">
      <div class="panel-body">
        <p class="goal">{{ task.goal }}</p>

        <div class="progress-section">
          <div class="progress-meta">
            <span>{{ task.current_step }}/{{ task.total_steps }} 步骤已完成</span>
            <span v-if="task.replan_count > 0" class="replan">重规划 {{ task.replan_count }} 次</span>
          </div>
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: `${(task.current_step / task.total_steps) * 100}%` }"
            />
          </div>
        </div>

        <div class="timeline">
          <div
            v-for="step in task.steps"
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
                查看差旅申请单 →
              </button>
            </div>
          </div>
        </div>
      </div>

      <footer class="panel-footer">
        <button type="button" class="btn-danger" @click="handleCancel">取消任务</button>
        <button
          v-if="task.status === 'running'"
          type="button"
          class="btn-primary"
          @click="handleConfirm"
        >
          确认继续
        </button>
      </footer>
    </template>
  </aside>
</template>

<style scoped>
.task-panel {
  width: 480px;
  flex-shrink: 0;
  background: var(--surface);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.panel-header h2 {
  font-size: 18px;
  font-weight: 600;
}

.btn-close {
  border: none;
  background: none;
  font-size: 24px;
  color: var(--text-muted);
  cursor: pointer;
  line-height: 1;
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
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
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

.panel-footer .btn-primary {
  flex: 1;
}
</style>
