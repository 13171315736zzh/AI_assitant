<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { fetchDocumentPreviewUrl, type MessageSource } from '@/services/documentPreviewService'

const props = defineProps<{
  source: MessageSource | null
}>()

const emit = defineEmits<{
  close: []
}>()

const loading = ref(false)
const error = ref('')
const previewUrl = ref('')
const isPdf = ref(true)

async function loadPreview() {
  if (!props.source) return
  loading.value = true
  error.value = ''
  revokeUrl()
  isPdf.value = props.source.filename.toLowerCase().endsWith('.pdf')
  if (!isPdf.value) {
    loading.value = false
    error.value = '当前仅支持在线预览 PDF，Word 文档请稍后从知识库下载。'
    return
  }
  try {
    previewUrl.value = await fetchDocumentPreviewUrl(props.source)
  } catch {
    error.value = '文档加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

function revokeUrl() {
  if (previewUrl.value.startsWith('blob:')) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = ''
}

watch(
  () => props.source,
  (src) => {
    if (src) loadPreview()
    else revokeUrl()
  },
  { immediate: true },
)

onUnmounted(revokeUrl)
</script>

<template>
  <div v-if="source" class="overlay" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" :aria-label="source.filename">
      <header class="modal-header">
        <div class="title-wrap">
          <h3>{{ source.filename }}</h3>
          <p v-if="source.clause" class="clause">{{ source.clause }}</p>
        </div>
        <button type="button" class="btn-close" aria-label="关闭" @click="emit('close')">×</button>
      </header>

      <div class="modal-body">
        <div v-if="loading" class="state">正在加载文档…</div>
        <div v-else-if="error" class="state error">{{ error }}</div>
        <iframe
          v-else-if="previewUrl && isPdf"
          :src="previewUrl"
          class="pdf-frame"
          title="政策文档预览"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}

.modal {
  width: min(920px, 100%);
  height: min(85vh, 900px);
  background: var(--surface);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.18);
}

.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.title-wrap h3 {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
}

.clause {
  margin-top: 4px;
  font-size: 13px;
  color: var(--text-secondary);
}

.btn-close {
  border: none;
  background: none;
  font-size: 24px;
  line-height: 1;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0 4px;
}

.modal-body {
  flex: 1;
  min-height: 0;
  background: #525659;
}

.pdf-frame {
  width: 100%;
  height: 100%;
  border: none;
  background: #fff;
}

.state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  background: var(--bg);
  font-size: 14px;
}

.state.error {
  color: var(--primary);
  padding: 24px;
  text-align: center;
}
</style>
