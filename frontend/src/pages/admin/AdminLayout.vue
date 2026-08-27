<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { name: 'admin-knowledge', label: '知识库管理', path: '/admin/knowledge' },
  { name: 'admin-conversations', label: '对话监控', path: '/admin/conversations' },
  { name: 'admin-settings', label: '系统设置', path: '/admin/settings' },
]

const activeName = computed(() => route.name as string)
</script>

<template>
  <div class="app-shell admin-layout">
    <aside class="admin-nav">
      <div class="nav-header">
        <div class="system-name">智能办公助手</div>
        <div class="badge">管理员后台</div>
        <RouterLink to="/chat" class="back">← 返回对话</RouterLink>
      </div>
      <nav class="nav-menu">
        <RouterLink
          v-for="item in navItems"
          :key="item.name"
          :to="item.path"
          class="nav-item"
          :class="{ active: activeName === item.name }"
        >
          <span class="bar" />
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="admin-content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.admin-layout {
  flex-direction: row;
}

.admin-nav {
  width: 240px;
  flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}

.nav-header {
  padding: 20px;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.system-name {
  font-family: 'Outfit', sans-serif;
  font-size: 15px;
  font-weight: 600;
}

.badge {
  font-size: 12px;
  color: var(--text-muted);
}

.back {
  margin-top: 12px;
  font-size: 13px;
  color: var(--primary);
}

.nav-menu {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 10px 12px 10px 0;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--text-secondary);
}

.nav-item.active {
  background: #fdf2f2;
  color: var(--primary);
  font-weight: 600;
}

.nav-item .bar {
  width: 4px;
  height: 32px;
  margin-right: 12px;
  border-radius: 0 2px 2px 0;
  background: transparent;
}

.nav-item.active .bar {
  background: var(--primary);
}

.admin-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: var(--bg);
}
</style>
