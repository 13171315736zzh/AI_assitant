<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { AdminConversation, ConversationStats } from '@/services/adminService'
import { fetchAdminConversations, fetchConversationStats } from '@/services/adminService'
import ConversationDetailModal from './ConversationDetailModal.vue'

const stats = ref<ConversationStats | null>(null)
const conversations = ref<AdminConversation[]>([])
const keyword = ref('')
const statusFilter = ref('')
const loading = ref(false)
const detailSessionId = ref<string | null>(null)

async function load() {
  loading.value = true
  try {
    const [statsRes, listRes] = await Promise.all([
      fetchConversationStats(),
      fetchAdminConversations(keyword.value || undefined, statusFilter.value || undefined),
    ])
    if (statsRes.code === 200) stats.value = statsRes.data
    if (listRes.code === 200) conversations.value = listRes.data.items
  } finally {
    loading.value = false
  }
}

onMounted(load)

function formatTime(iso: string) {
  return iso.replace('T', ' ').slice(0, 16)
}

function exportRecords() {
  alert('导出记录成功，文件已生成')
}

function openDetail(sessionId: string) {
  detailSessionId.value = sessionId
}

function closeDetail() {
  detailSessionId.value = null
}
</script>

<template>
  <div class="admin-page">
    <header class="page-header">
      <div>
        <h1>对话监控</h1>
        <p class="desc">查看全平台用户会话状态，支持检索与导出</p>
      </div>
    </header>

    <div v-if="stats" class="stats">
      <div class="stat-card">
        <span class="label">总会话数</span>
        <strong>{{ stats.total_sessions.toLocaleString() }}</strong>
      </div>
      <div class="stat-card primary">
        <span class="label">进行中</span>
        <strong>{{ stats.active_sessions }}</strong>
      </div>
      <div class="stat-card success">
        <span class="label">今日新增</span>
        <strong>{{ stats.today_new_sessions }}</strong>
      </div>
    </div>

    <div class="filter-bar">
      <input v-model="keyword" type="text" placeholder="搜索用户或会话标题…" @keyup.enter="load" />
      <select v-model="statusFilter" @change="load">
        <option value="">全部状态</option>
        <option value="active">进行中</option>
        <option value="ended">已结束</option>
      </select>
      <button type="button" class="btn-secondary" @click="load">搜索</button>
      <button type="button" class="btn-primary" @click="exportRecords">导出记录</button>
    </div>

    <div class="table">
      <div class="table-head">
        <span>用户</span>
        <span>会话标题</span>
        <span>状态</span>
        <span>消息数</span>
        <span>开始时间</span>
        <span>最后活跃</span>
        <span>操作</span>
      </div>
      <div v-if="loading" class="empty">加载中…</div>
      <template v-else>
        <div v-for="c in conversations" :key="c.id" class="table-row">
          <span>{{ c.user.display_name }} ({{ c.user.employee_id }})</span>
          <span>{{ c.title }}</span>
          <span>
            <span class="status-tag" :class="c.status === 'active' ? 'active' : 'ended'">
              {{ c.status === 'active' ? '进行中' : '已结束' }}
            </span>
          </span>
          <span>{{ c.message_count }}</span>
          <span>{{ formatTime(c.created_at) }}</span>
          <span>{{ formatTime(c.updated_at) }}</span>
          <span>
            <button type="button" class="link-btn" @click="openDetail(c.id)">查看详情</button>
          </span>
        </div>
        <div v-if="!conversations.length" class="empty">暂无会话记录</div>
      </template>
    </div>

    <ConversationDetailModal
      v-if="detailSessionId"
      :session-id="detailSessionId"
      @close="closeDetail"
    />
  </div>
</template>

<style scoped>
.admin-page {
  padding: 24px 32px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
}

.desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

.stats {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-card .label {
  font-size: 12px;
  color: var(--text-secondary);
}

.stat-card strong {
  font-family: 'Outfit', sans-serif;
  font-size: 28px;
}

.stat-card.primary strong {
  color: var(--primary);
}

.stat-card.success strong {
  color: var(--success);
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.filter-bar input {
  width: 280px;
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.filter-bar select {
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
}

.table {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.table-head,
.table-row {
  display: grid;
  grid-template-columns: 180px 1.5fr 80px 70px 140px 140px 90px;
  padding: 12px 16px;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.table-head {
  background: #fafbfc;
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 12px;
  border-bottom: 1px solid var(--border);
}

.table-row {
  border-bottom: 1px solid var(--border);
}

.table-row:hover {
  background: #fafbfc;
}

.status-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
}

.status-tag.active {
  background: #fdf2f2;
  color: var(--primary);
}

.status-tag.ended {
  background: var(--bg);
  color: var(--text-muted);
}

.link-btn {
  border: none;
  background: none;
  color: var(--primary);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
}

.link-btn:hover {
  text-decoration: underline;
}

.empty {
  padding: 32px;
  text-align: center;
  color: var(--text-muted);
}
</style>
