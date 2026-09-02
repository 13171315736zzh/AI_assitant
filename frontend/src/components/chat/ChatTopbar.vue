<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'
import { computed } from 'vue'

const emit = defineEmits<{
  ticket: []
  clearMemory: []
}>()

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const adminLinks = [
  { name: 'admin-knowledge', label: '知识库管理', path: '/admin/knowledge' },
  { name: 'admin-project-mapping', label: '项目映射', path: '/admin/project-mapping' },
  { name: 'admin-conversations', label: '对话监控', path: '/admin/conversations' },
  { name: 'admin-settings', label: '系统设置', path: '/admin/settings' },
]

const isAdminRoute = computed(() => route.path.startsWith('/admin'))
const isMyTasksActive = computed(() => route.name === 'my-tasks')

function goSettings() {
  router.push({ name: 'settings-account' })
}

function goHelp() {
  router.push({ name: 'knowledge-help' })
}

function goMyTasks() {
  router.push({ name: 'my-tasks' })
}

function goAdmin(path: string) {
  router.push(path)
}
</script>

<template>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="product-name">智能办公助手</div>
      <nav class="topbar-actions">
        <button
          type="button"
          class="topbar-link"
          :class="{ 'link-active': isMyTasksActive }"
          @click="goMyTasks"
        >
          我的任务
        </button>
        <button type="button" class="topbar-link" @click="goHelp">知识库帮助</button>
        <button type="button" class="topbar-link" @click="emit('ticket')">人工协助</button>
        <button type="button" class="topbar-link" @click="emit('clearMemory')">清除记忆</button>
        <button type="button" class="topbar-link" @click="goSettings">设置</button>

        <template v-if="auth.isAdmin">
          <span class="admin-divider" />
          <button
            v-for="link in adminLinks"
            :key="link.name"
            type="button"
            class="topbar-link admin"
            :class="{ 'admin-active': route.name === link.name || (isAdminRoute && route.name === link.name) }"
            @click="goAdmin(link.path)"
          >
            {{ link.label }}
          </button>
        </template>
      </nav>
    </div>
    <div class="brand-line" aria-hidden="true" />
  </header>
</template>

<style scoped>
.topbar {
  background: var(--surface);
  flex-shrink: 0;
}

.topbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 56px;
  gap: 16px;
}

.product-name {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.02em;
  flex-shrink: 0;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.topbar-link {
  padding: 6px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
  white-space: nowrap;
}

.topbar-link:hover {
  color: var(--accent);
  background: rgba(246, 171, 0, 0.08);
}

.topbar-link.link-active {
  color: var(--primary);
  background: #fdf2f2;
  font-weight: 600;
}

.admin-divider {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 4px;
}

.topbar-link.admin {
  color: var(--primary);
  border: 1px solid #f5c6c6;
  background: #fdf2f2;
}

.topbar-link.admin:hover {
  background: #fce8e8;
  color: var(--primary);
}

.topbar-link.admin-active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.brand-line {
  height: 2px;
  background: var(--gradient-brand);
}
</style>
