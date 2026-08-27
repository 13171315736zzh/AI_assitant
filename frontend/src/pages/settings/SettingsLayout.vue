<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { name: 'settings-theme', label: '外观主题', path: '/settings/theme' },
  { name: 'settings-account', label: '账号管理', path: '/settings/account' },
  { name: 'settings-version', label: '版本升级', path: '/settings/version' },
  { name: 'settings-memory', label: '记忆设置', path: '/settings/memory' },
]

const activeName = computed(() => route.name as string)
</script>

<template>
  <div class="app-shell settings-layout">
    <aside class="settings-nav">
      <div class="nav-header">
        <RouterLink to="/chat" class="back">← 返回</RouterLink>
        <h2>个人设置</h2>
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
    <main class="settings-content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.settings-layout {
  flex-direction: row;
}

.settings-nav {
  width: 260px;
  flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}

.nav-header {
  padding: 20px;
  border-bottom: 1px solid var(--border);
}

.nav-header h2 {
  font-size: 18px;
  margin-top: 8px;
}

.back {
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

.settings-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: var(--bg);
  padding: 32px;
}
</style>
