<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{ close: [] }>()

const title = ref('差旅订票失败需人工协助')
const description = ref(
  'Agent 重规划 3 次后仍无法预订周三下午航班，请协助处理',
)
const submitted = ref(false)
const ticketId = ref('')

function submit() {
  if (!title.value.trim() || !description.value.trim()) {
    alert('请填写标题和描述')
    return
  }
  ticketId.value = 'WO20260325001'
  submitted.value = true
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
        <button v-if="!submitted" type="button" class="btn-primary" @click="submit">
          提交工单
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
