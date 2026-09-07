<script setup lang="ts">
import { ref } from 'vue'
import type { WorkflowSessionSummary } from '@/types'

const props = defineProps<{
  summary: WorkflowSessionSummary
}>()

const copied = ref(false)

async function copySummary() {
  try {
    await navigator.clipboard.writeText(props.summary.text)
    copied.value = true
    window.setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    alert('复制失败，请手动选择下方文本复制')
  }
}
</script>

<template>
  <div class="summary-panel">
    <header class="summary-head">
      <strong>办理结果汇总</strong>
      <button type="button" class="btn-copy" @click="copySummary">
        {{ copied ? '已复制' : '一键复制' }}
      </button>
    </header>
    <pre class="summary-text">{{ summary.text }}</pre>
  </div>
</template>

<style scoped>
.summary-panel {
  margin-top: 12px;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: var(--radius-sm);
}

.summary-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 13px;
}

.btn-copy {
  padding: 4px 12px;
  border: 1px solid var(--primary);
  border-radius: 6px;
  background: #fff;
  color: var(--primary);
  font-size: 12px;
  cursor: pointer;
}

.btn-copy:hover {
  background: color-mix(in srgb, var(--primary) 8%, #fff);
}

.summary-text {
  margin: 0;
  padding: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: #334155;
  max-height: 320px;
  overflow: auto;
}
</style>
