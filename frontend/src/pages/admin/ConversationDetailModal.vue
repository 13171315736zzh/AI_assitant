<script setup lang="ts">
import { ref, watch } from 'vue'
import type { AdminConversationDetail } from '@/services/adminService'
import { fetchAdminConversationDetail } from '@/services/adminService'

const props = defineProps<{ sessionId: string }>()
const emit = defineEmits<{ close: [] }>()

const detail = ref<AdminConversationDetail | null>(null)
const loading = ref(false)

async function load() {
  loading.value = true
  detail.value = null
  try {
    const res = await fetchAdminConversationDetail(props.sessionId)
    if (res.code === 200) detail.value = res.data
  } finally {
    loading.value = false
  }
}

watch(() => props.sessionId, load, { immediate: true })

function formatTime(iso: string) {
  return iso.replace('T', ' ').slice(0, 16)
}

function endedReasonLabel(reason: AdminConversationDetail['ended_reason']) {
  if (!reason) return '—'
  return reason === 'completed' ? '任务完成' : '用户手动结束'
}
</script>

<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal">
      <header class="modal-header">
        <div>
          <h2>会话详情</h2>
          <p v-if="detail" class="subtitle">{{ detail.title }}</p>
        </div>
        <button type="button" class="btn-close" aria-label="关闭" @click="emit('close')">×</button>
      </header>

      <div v-if="loading" class="modal-body loading">加载中…</div>

      <div v-else-if="detail" class="modal-body">
        <section class="info-grid">
          <div class="info-item">
            <span class="label">用户</span>
            <span>{{ detail.user.display_name }}</span>
          </div>
          <div class="info-item">
            <span class="label">工号</span>
            <span>{{ detail.user.employee_id }}</span>
          </div>
          <div class="info-item">
            <span class="label">会话 ID</span>
            <span class="mono">{{ detail.id }}</span>
          </div>
          <div class="info-item">
            <span class="label">状态</span>
            <span
              class="status-tag"
              :class="detail.status === 'active' ? 'active' : 'ended'"
            >
              {{ detail.status === 'active' ? '进行中' : '已结束' }}
            </span>
          </div>
          <div class="info-item">
            <span class="label">消息数</span>
            <span>{{ detail.message_count }}</span>
          </div>
          <div class="info-item">
            <span class="label">结束原因</span>
            <span>{{ endedReasonLabel(detail.ended_reason) }}</span>
          </div>
          <div class="info-item">
            <span class="label">开始时间</span>
            <span>{{ formatTime(detail.created_at) }}</span>
          </div>
          <div class="info-item">
            <span class="label">最后活跃</span>
            <span>{{ formatTime(detail.updated_at) }}</span>
          </div>
        </section>

        <div v-if="detail.task_summary" class="task-banner">
          <span class="task-label">关联任务</span>
          <span>{{ detail.task_summary }}</span>
        </div>

        <section class="messages-section">
          <h3>对话摘要</h3>
          <div class="messages">
            <div
              v-for="(msg, idx) in detail.messages"
              :key="idx"
              class="message-row"
              :class="msg.role"
            >
              <span class="role">{{ msg.role === 'user' ? '用户' : '助手' }}</span>
              <div class="bubble" :class="msg.role">
                <p>{{ msg.content }}</p>
                <time>{{ formatTime(msg.created_at) }}</time>
              </div>
            </div>
          </div>
          <p v-if="detail.message_count > detail.messages.length" class="more-hint">
            仅展示最近 {{ detail.messages.length }} 条，共 {{ detail.message_count }} 条消息
          </p>
        </section>
      </div>

      <footer class="modal-footer">
        <button type="button" class="btn-primary" @click="emit('close')">关闭</button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 24px;
}

.modal {
  width: 1280px;
  max-width: 100%;
  max-height: calc(100vh - 48px);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.modal-header h2 {
  font-size: 18px;
  font-weight: 600;
}

.subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

.btn-close {
  border: none;
  background: none;
  font-size: 24px;
  color: var(--text-muted);
  cursor: pointer;
  line-height: 1;
}

.modal-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.modal-body.loading {
  text-align: center;
  color: var(--text-muted);
  padding: 48px;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 24px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.info-item .label {
  font-size: 12px;
  color: var(--text-muted);
}

.mono {
  font-family: ui-monospace, monospace;
  font-size: 12px;
}

.status-tag {
  display: inline-block;
  width: fit-content;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.status-tag.active {
  background: #fdf2f2;
  color: var(--primary);
}

.status-tag.ended {
  background: var(--bg);
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.task-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.task-label {
  font-weight: 600;
  color: #92400e;
  flex-shrink: 0;
}

.messages-section h3 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.message-row.user {
  flex-direction: row-reverse;
}

.role {
  font-size: 11px;
  color: var(--text-muted);
  width: 32px;
  flex-shrink: 0;
  padding-top: 8px;
  text-align: center;
}

.message-row.user .role {
  text-align: center;
}

.bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.6;
  border: 1px solid var(--border);
}

.bubble.user {
  background: var(--user-bubble-bg);
  border-color: var(--user-bubble-border);
}

.bubble.assistant {
  background: var(--surface);
}

.bubble time {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 6px;
}

.more-hint {
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
  margin-top: 8px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  padding: 16px 24px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
</style>
