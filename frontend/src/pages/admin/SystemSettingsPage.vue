<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { SystemConfig } from '@/services/adminService'
import { fetchSystemConfig, updateSystemConfig } from '@/services/adminService'

const config = ref<SystemConfig | null>(null)
const saving = ref(false)

async function load() {
  const res = await fetchSystemConfig()
  if (res.code === 200) config.value = { ...res.data }
}

onMounted(load)

async function save() {
  if (!config.value) return
  saving.value = true
  try {
    const res = await updateSystemConfig(config.value)
    if (res.code === 200) {
      config.value = res.data
      alert('配置已保存')
    }
  } finally {
    saving.value = false
  }
}

function reset() {
  if (confirm('确认恢复默认配置？')) load()
}
</script>

<template>
  <div class="admin-page">
    <header class="page-header">
      <div>
        <h1>系统设置</h1>
        <p class="desc">配置系统基础参数、AI 模型与会话策略</p>
      </div>
    </header>

    <template v-if="config">
      <section class="section">
        <h3>基础配置</h3>
        <div class="field">
          <label>系统名称</label>
          <input v-model="config.system_name" type="text" />
          <span class="hint">对外展示的产品名称</span>
        </div>
        <div class="field">
          <label>默认欢迎语</label>
          <input v-model="config.welcome_message" type="text" />
          <span class="hint">新会话首条系统消息</span>
        </div>
      </section>

      <section class="section">
        <h3>AI 模型配置</h3>
        <div class="field">
          <label>默认模型</label>
          <input v-model="config.default_model" type="text" />
          <span class="hint">阿里云百炼模型，如 qwen-max、qwen-plus、qwen-long</span>
        </div>
        <div class="field">
          <label>温度参数</label>
          <input v-model.number="config.temperature" type="number" step="0.1" min="0" max="1" />
          <span class="hint">控制回复创造性，范围 0.0–1.0</span>
        </div>
      </section>

      <section class="section">
        <h3>会话策略</h3>
        <div class="field">
          <label>会话保留天数</label>
          <input v-model.number="config.session_retention_days" type="number" />
        </div>
        <div class="field">
          <label>单用户最大并发</label>
          <input v-model.number="config.max_concurrent_sessions" type="number" />
        </div>
      </section>

      <section class="section">
        <h3>日志与调试</h3>
        <div class="field">
          <label>日志级别</label>
          <select v-model="config.log_level">
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARN">WARN</option>
            <option value="ERROR">ERROR</option>
          </select>
        </div>
        <div class="field">
          <label>API 超时 (秒)</label>
          <input v-model.number="config.api_timeout_seconds" type="number" />
        </div>
      </section>

      <footer class="footer">
        <button type="button" class="btn-secondary" @click="reset">恢复默认</button>
        <button type="button" class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存配置' }}
        </button>
      </footer>
    </template>
  </div>
</template>

<style scoped>
.admin-page {
  padding: 24px 32px;
  max-width: 720px;
}

.page-header {
  display: flex;
  justify-content: space-between;
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

.section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 24px;
  margin-bottom: 20px;
}

.section h3 {
  font-size: 16px;
  margin-bottom: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}

.field:last-child {
  margin-bottom: 0;
}

.field label {
  font-size: 13px;
  font-weight: 500;
}

.field input,
.field select {
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  font-size: 13px;
}

.hint {
  font-size: 12px;
  color: var(--text-muted);
}

.footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
