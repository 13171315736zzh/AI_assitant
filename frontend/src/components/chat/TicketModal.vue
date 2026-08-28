<script setup lang="ts">
import { ref } from 'vue'
import { createTicket } from '@/services/ticketService'

const props = defineProps<{ sessionId?: string | null }>()
const emit = defineEmits<{ close: [] }>()

const title = ref('差旅订票失败需人工协助')
const description = ref(
  'Agent 重规划 3 次后仍无法预订周三下午航班，请协助处理',
)
const submitted = ref(false)
const ticketId = ref('')
const submitting = ref(false)
const errorMsg = ref('')

async function submit() {
  if (!title.value.trim() || !description.value.trim()) {
    errorMsg.value = '请填写标题和描述'
    return
  }
  submitting.value = true
  errorMsg.value = ''
  try {
    const res = await createTicket({
      session_id: props.sessionId ?? null,
      title: title.value.trim(),
      description: description.value.trim(),
    })
    if (res.code === 200 && res.data) {
      ticketId.value = res.data.id
      submitted.value = true
    } else {
      errorMsg.value = res.message || '提交失败'
    }
  } catch (err: unknown) {
    const axiosErr = err as { response?: { data?: { message?: string } } }
    errorMsg.value = axiosErr.response?.data?.message || '提交失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal">
      <header class="modal-header">
        <h2>人工协助</h2>
        <button type="button" class="btn-close" aria-label="关闭" @click="emit('close')">
          ×
        </button>
      </header>

      <div v-if="!submitted" class="modal-body">
        <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
        <div class="field">
          <label>问题标题</label>
          <input v-model="title" type="text" placeholder="请输入问题标题" />
        </div>
        <div class="field">
          <label>问题描述</label>
          <textarea v-model="description" rows="4" placeholder="请描述您遇到的问题" />
        </div>
      </div>

      <div v-else class="success">
        <p class="success-title">工单已提交</p>
        <p>工单号 {{ ticketId }} · 状态：待处理</p>
      </div>

      <footer class="modal-footer">
        <button type="button" class="btn-secondary" @click="emit('close')">
          {{ submitted ? '关闭' : '取消' }}
        </button>
        <button
          v-if="!submitted"
          type="button"
          class="btn-primary"
          :disabled="submitting"
          @click="submit"
        >
          {{ submitting ? '提交中…' : '提交工单' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal {
  width: 520px;
  max-width: calc(100% - 32px);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.modal-header h2 {
  font-size: 18px;
  font-weight: 600;
}

.btn-close {
  border: none;
  background: none;
  font-size: 24px;
  line-height: 1;
  color: var(--text-muted);
  cursor: pointer;
}

.modal-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.error-msg {
  color: var(--danger, #c0392b);
  font-size: 13px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field label {
  font-size: 13px;
  color: var(--text-secondary);
}

.field input,
.field textarea {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  font-size: 14px;
  outline: none;
}

.field input:focus,
.field textarea:focus {
  border-color: var(--primary);
}

.success {
  padding: 32px 20px;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.success-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--success);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
}
</style>
