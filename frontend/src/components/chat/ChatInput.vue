<script setup lang="ts">
defineProps<{
  disabled?: boolean
  sending?: boolean
}>()

const emit = defineEmits<{
  send: [content: string]
}>()

const text = defineModel<string>({ default: '' })

function submit() {
  if (!text.value.trim()) return
  emit('send', text.value)
  text.value = ''
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="input-area">
    <div v-if="disabled" class="ended-hint">当前会话已结束，无法发送新消息</div>
    <div class="input-box" :class="{ disabled }">
      <textarea
        v-model="text"
        rows="1"
        :disabled="disabled || sending"
        placeholder="输入您的需求，或直接说…"
        @keydown="onKeydown"
      />
      <button
        type="button"
        class="btn-send"
        :disabled="disabled || sending || !text.trim()"
        aria-label="发送"
        @click="submit"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.input-area {
  padding: 16px 24px 24px;
  background: var(--bg);
  flex-shrink: 0;
}

.ended-hint {
  font-size: 13px;
  color: var(--text-muted);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  margin-bottom: 12px;
  text-align: center;
}

.input-box {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
}

.input-box.disabled {
  opacity: 0.6;
}

.input-box textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-size: 14px;
  line-height: 1.5;
  min-height: 44px;
  color: var(--text);
  background: transparent;
}

.input-box textarea::placeholder {
  color: var(--text-muted);
}

.btn-send {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.btn-send:hover:not(:disabled) {
  background: var(--accent);
}

.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-send svg {
  width: 20px;
  height: 20px;
}
</style>
