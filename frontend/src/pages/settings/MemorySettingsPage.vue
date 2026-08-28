<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { MemoryItem } from '@/services/settingsService'
import { fetchMemory, updateMemory } from '@/services/settingsService'

const memoryEnabled = ref(true)
const memoryItems = ref<MemoryItem[]>([])
const loading = ref(true)
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await fetchMemory()
    if (res.code === 200) {
      memoryEnabled.value = res.data.memory_enabled
      memoryItems.value = res.data.memory_items.map((item) => ({ ...item }))
    }
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const res = await updateMemory({
      memory_enabled: memoryEnabled.value,
      memory_items: memoryItems.value,
    })
    if (res.code === 200) {
      memoryEnabled.value = res.data.memory_enabled
      memoryItems.value = res.data.memory_items.map((item) => ({ ...item }))
      alert('记忆设置已保存')
    } else {
      alert(res.message || '保存失败')
    }
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="settings-page">
    <h1>记忆设置</h1>

    <div v-if="loading" class="loading">加载中…</div>
    <div v-else class="card full">
      <div class="toggle-row">
        <span>启用长期记忆</span>
        <label class="switch">
          <input v-model="memoryEnabled" type="checkbox" />
          <span class="slider" />
        </label>
      </div>
      <p class="hint">开启后系统将自动记录您的偏好与习惯；关闭后不再新增记忆，已有数据保留。</p>

      <template v-if="memoryEnabled">
        <div class="divider" />
        <h3>已提取的长期记忆</h3>
        <p class="sub-hint">以下为系统自动提取的记忆条目，您可直接修改并保存</p>

        <div class="fields">
          <div v-for="(item, i) in memoryItems" :key="i" class="field-row">
            <span class="field-key">{{ item.key }}</span>
            <input v-model="item.value" type="text" class="field-input" />
          </div>
        </div>
      </template>

      <div class="footer">
        <div class="warn">可在对话页顶栏「清除记忆」一键清空所有长期记忆</div>
        <button type="button" class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存修改' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page h1 {
  font-size: 22px;
  margin-bottom: 24px;
}

.loading {
  color: var(--text-muted);
  font-size: 14px;
}

.card.full {
  width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 500;
}

.switch {
  position: relative;
  width: 44px;
  height: 24px;
  display: inline-block;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  inset: 0;
  background: var(--border);
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.slider::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  left: 4px;
  top: 4px;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.2s;
}

.switch input:checked + .slider {
  background: var(--primary);
}

.switch input:checked + .slider::before {
  transform: translateX(20px);
}

.hint,
.sub-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.divider {
  height: 1px;
  background: var(--border);
}

.card h3 {
  font-size: 16px;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-row {
  display: flex;
  align-items: center;
  gap: 24px;
}

.field-key {
  width: 120px;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.field-input {
  flex: 1;
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 8px;
}

.warn {
  flex: 1;
  font-size: 12px;
  color: #b7791f;
  background: #fffbeb;
  border: 1px solid #f6e05e;
  border-radius: var(--radius-sm);
  padding: 12px;
}
</style>
