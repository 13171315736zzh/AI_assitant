<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { ThemeValue } from '@/services/settingsService'
import { fetchTheme, updateTheme } from '@/services/settingsService'
import { applyTheme, themeLabels } from '@/utils/theme'

const theme = ref<ThemeValue>('light')
const loading = ref(true)
const saving = ref(false)

const options = [
  { value: 'light' as const, label: '浅色' },
  { value: 'dark' as const, label: '深色' },
  { value: 'system' as const, label: '跟随系统' },
]

const currentLabel = computed(() => themeLabels[theme.value])

async function load() {
  loading.value = true
  try {
    const res = await fetchTheme()
    if (res.code === 200) {
      theme.value = res.data.theme
      applyTheme(res.data.theme)
    }
  } finally {
    loading.value = false
  }
}

watch(theme, async (value, oldValue) => {
  if (loading.value || value === oldValue) return
  applyTheme(value)
  saving.value = true
  try {
    await updateTheme(value)
  } finally {
    saving.value = false
  }
})

onMounted(load)
</script>

<template>
  <div class="settings-page">
    <h1>外观主题</h1>
    <p class="desc">
      选择界面配色方案，更改后立即生效。当前：{{ currentLabel }}
      <span v-if="saving" class="saving">（保存中…）</span>
    </p>

    <div v-if="loading" class="loading">加载中…</div>
    <div v-else class="card">
      <label v-for="opt in options" :key="opt.value" class="radio-row">
        <input v-model="theme" type="radio" :value="opt.value" />
        <span>{{ opt.label }}</span>
      </label>
    </div>

    <div class="preview-section">
      <h3>主题预览</h3>
      <div class="preview-row">
        <div v-for="opt in options" :key="opt.value" class="preview-item">
          <div class="preview-card" :class="opt.value">
            <div class="preview-bar" />
            <div class="preview-body">
              <div class="line" />
              <div class="line short" />
            </div>
          </div>
          <span>{{ opt.label }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page h1 {
  font-size: 22px;
  margin-bottom: 8px;
}

.desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 24px;
}

.saving {
  margin-left: 4px;
}

.loading {
  color: var(--text-muted);
  font-size: 14px;
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
  gap: 12px;
  margin-bottom: 32px;
}

.radio-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  cursor: pointer;
  font-size: 14px;
}

.preview-section h3 {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 12px;
}

.preview-row {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.preview-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.preview-card {
  width: 160px;
  height: 100px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.preview-card.light,
.preview-card.system {
  background: #f1f4f6;
}

.preview-card.dark {
  background: #1a1d21;
}

.preview-bar {
  height: 20px;
  background: var(--surface);
}

.preview-card.dark .preview-bar {
  background: #2d3139;
}

.preview-body {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.line {
  height: 6px;
  width: 80px;
  background: var(--border);
  border-radius: 2px;
}

.line.short {
  width: 100px;
}
</style>
