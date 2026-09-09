<script setup lang="ts">
import { computed } from 'vue'
import type { WorkflowCancelConfirmMeta } from '@/types'

const props = defineProps<{
  confirm: WorkflowCancelConfirmMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: { task_id: string }]
}>()

const isPending = computed(() => props.confirm.status === 'pending')

function handleConfirm() {
  if (!isPending.value || props.submitting || !props.confirm.task_id) return
  emit('confirm', { task_id: props.confirm.task_id })
}
</script>

<template>
  <div class="cancel-confirm" :class="{ confirmed: !isPending }">
    <dl class="info-list">
      <div
        v-for="item in confirm.items"
        :key="item.label"
        class="info-row"
      >
        <dt>{{ item.label }}</dt>
        <dd>{{ item.value }}</dd>
      </div>
    </dl>

    <div v-if="isPending" class="confirm-footer">
      <button
        type="button"
        class="btn-confirm danger"
        :disabled="submitting"
        @click="handleConfirm"
      >
        {{ submitting ? '处理中…' : (confirm.confirm_label ?? '确认取消') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.cancel-confirm {
  margin-top: 12px;
  padding: 12px;
  background: #fffafa;
  border: 1px solid #fecaca;
  border-radius: var(--radius-sm);
}

.info-list {
  margin: 0 0 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-row {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 8px;
  padding: 8px 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.info-row dt {
  color: var(--text-secondary);
}

.info-row dd {
  margin: 0;
  color: var(--text);
  word-break: break-word;
}

.confirm-footer {
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.btn-confirm {
  width: 100%;
  height: 38px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.btn-confirm.danger {
  background: #dc2626;
  color: #fff;
}

.btn-confirm:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
