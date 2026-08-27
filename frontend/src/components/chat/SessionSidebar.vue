<script setup lang="ts">
import type { Session } from '@/types'

defineProps<{
  sessions: Session[]
  activeId: string | null
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [id: string]
  newSession: []
  endSession: []
}>()

function formatTime(iso: string) {
  const d = new Date(iso)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  const isYesterday = d.toDateString() === yesterday.toDateString()

  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (isToday) return `今天 ${time}`
  if (isYesterday) return `昨天 ${time}`
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}
</script>

<template>
  <aside class="sidebar-left">
    <div class="sidebar-header">
      <button type="button" class="btn-new" @click="emit('newSession')">+ 新建对话</button>
    </div>

    <div class="session-list">
      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ active: session.id === activeId }"
        @click="emit('select', session.id)"
      >
        <div class="session-title">{{ session.title }}</div>
        <div class="session-meta">
          <span class="session-time">{{ formatTime(session.updated_at) }}</span>
          <span
            class="tag"
            :class="session.status === 'active' ? 'tag-active' : 'tag-ended'"
          >
            {{ session.status === 'active' ? '进行中' : '已结束' }}
          </span>
        </div>
      </div>
      <p v-if="!loading && sessions.length === 0" class="empty">暂无会话</p>
    </div>

    <div class="sidebar-footer">
      <button type="button" class="btn-end" @click="emit('endSession')">结束当前会话</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar-left {
  width: 260px;
  flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.btn-new {
  width: 100%;
  height: 40px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.btn-new:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.session-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  position: relative;
  padding: 12px 12px 12px 16px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.15s;
}

.session-item:hover {
  background: var(--bg);
}

.session-item.active {
  background: #fdf2f2;
}

.session-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 4px;
  background: var(--primary);
  border-radius: 0 2px 2px 0;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.session-time {
  font-size: 12px;
  color: var(--text-muted);
}

.empty {
  text-align: center;
  font-size: 13px;
  color: var(--text-muted);
  padding: 24px 8px;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.btn-end {
  width: 100%;
  height: 36px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
}

.btn-end:hover {
  border-color: var(--primary);
  color: var(--primary);
}
</style>
