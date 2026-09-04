<script setup lang="ts">
import { ref } from 'vue'
import type { GnMeetingResultMeta } from '@/types'

const props = defineProps<{
  result: GnMeetingResultMeta
}>()

const copiedField = ref<string | null>(null)

async function copyText(field: string, value: string) {
  try {
    await navigator.clipboard.writeText(value)
    copiedField.value = field
    window.setTimeout(() => {
      if (copiedField.value === field) copiedField.value = null
    }, 2000)
  } catch {
    window.prompt('请手动复制', value)
  }
}
</script>

<template>
  <div class="result-card gn">
    <h4 class="result-title">国能会议已创建</h4>
    <p v-if="result.subject" class="result-subtitle">{{ result.subject }}</p>

    <div class="copy-row">
      <div class="copy-main">
        <span class="copy-label">会议链接</span>
        <a :href="result.meeting_link" target="_blank" rel="noopener noreferrer" class="copy-value link">
          {{ result.meeting_link }}
        </a>
      </div>
      <button type="button" class="copy-btn" @click="copyText('link', result.meeting_link)">
        {{ copiedField === 'link' ? '已复制' : '复制' }}
      </button>
    </div>

    <div class="copy-row">
      <div class="copy-main">
        <span class="copy-label">会议密码</span>
        <span class="copy-value mono">{{ result.meeting_password }}</span>
      </div>
      <button type="button" class="copy-btn" @click="copyText('password', result.meeting_password)">
        {{ copiedField === 'password' ? '已复制' : '复制' }}
      </button>
    </div>

    <p v-if="result.meeting_no" class="meta-hint">会议号：{{ result.meeting_no }}</p>
  </div>
</template>

<style scoped>
.result-card {
  margin-top: 12px;
  padding: 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
}

.result-card.gn {
  border-color: color-mix(in srgb, var(--primary) 35%, var(--border));
  background: color-mix(in srgb, var(--primary) 6%, var(--surface));
}

.result-title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
}

.result-subtitle {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.copy-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-top: 1px solid var(--border);
}

.copy-row:first-of-type {
  border-top: none;
  padding-top: 0;
}

.copy-main {
  flex: 1;
  min-width: 0;
}

.copy-label {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.copy-value {
  display: block;
  font-size: 13px;
  word-break: break-all;
  color: var(--text);
}

.copy-value.link {
  color: var(--primary);
  text-decoration: none;
}

.copy-value.mono {
  font-family: ui-monospace, monospace;
  letter-spacing: 0.05em;
}

.copy-btn {
  flex-shrink: 0;
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  font-size: 12px;
  cursor: pointer;
}

.meta-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
