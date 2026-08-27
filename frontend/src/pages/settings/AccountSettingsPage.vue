<script setup lang="ts">
import { useAuthStore } from '@/stores/useAuthStore'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="settings-page">
    <h1>账号管理</h1>
    <div class="card">
      <div class="info-row">
        <span class="label">用户名</span>
        <span>{{ auth.user?.display_name }}（{{ auth.user?.username }}）</span>
      </div>
      <div class="info-row">
        <span class="label">角色</span>
        <span>{{ auth.user?.role === 'admin' ? '管理员' : '员工' }}</span>
      </div>
      <div class="info-row">
        <span class="label">工号</span>
        <span>{{ auth.user?.employee_id }}</span>
      </div>
      <div class="actions">
        <button type="button" class="btn-secondary" @click="logout">退出登录</button>
        <button type="button" class="btn-secondary" @click="logout">切换账号</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page h1 {
  font-size: 22px;
  margin-bottom: 24px;
}

.card {
  max-width: 560px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-row {
  display: flex;
  gap: 24px;
  font-size: 14px;
}

.label {
  width: 80px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}
</style>
