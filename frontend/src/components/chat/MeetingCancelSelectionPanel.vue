<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { MeetingCancelSelectionMeta } from '@/types'

const props = defineProps<{
  selection: MeetingCancelSelectionMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: { node_ids: string[] }]
}>()

const isPending = computed(() => props.selection.status === 'pending')

const selectedIds = ref<string[]>(
  props.selection.options.filter((item) => item.selected !== false).map((item) => item.node_id),
)

watch(
  () => props.selection.options,
  (options) => {
    selectedIds.value = options
      .filter((item) => item.selected !== false)
      .map((item) => item.node_id)
  },
  { deep: true },
)

const canConfirm = computed(() => isPending.value && selectedIds.value.length > 0)

function isSelected(nodeId: string) {
  return selectedIds.value.includes(nodeId)
}

function toggleOption(nodeId: string) {
  if (!isPending.value) return
  if (isSelected(nodeId)) {
    if (selectedIds.value.length <= 1) return
    selectedIds.value = selectedIds.value.filter((id) => id !== nodeId)
    return
  }
  selectedIds.value = [...selectedIds.value, nodeId]
}

function handleConfirm() {
  if (!canConfirm.value || props.submitting) return
  emit('confirm', { node_ids: [...selectedIds.value] })
}
</script>

<template>
  <div class="meeting-cancel-select" :class="{ confirmed: !isPending }">
    <div class="option-list">
      <button
        v-for="opt in selection.options"
        :key="opt.node_id"
        type="button"
        class="option-card"
        :class="{ selected: isSelected(opt.node_id), disabled: !isPending }"
        :disabled="!isPending"
        @click="toggleOption(opt.node_id)"
      >
        <span class="checkbox-box" aria-hidden="true">
          <span v-if="isSelected(opt.node_id)" class="check-mark">✓</span>
        </span>
        <span class="option-label">{{ opt.label }}</span>
      </button>
    </div>

    <div v-if="isPending" class="confirm-footer">
      <button
        type="button"
        class="btn-confirm danger"
        :disabled="submitting || !canConfirm"
        @click="handleConfirm"
      >
        {{ submitting ? '处理中…' : (selection.confirm_label ?? '确认选择') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.meeting-cancel-select {
  margin-top: 12px;
  padding: 12px;
  background: #fffafa;
  border: 1px solid #fecaca;
  border-radius: var(--radius-sm);
}

.option-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.option-card {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  text-align: left;
  cursor: pointer;
}

.option-card.selected {
  border-color: #dc2626;
  background: #fff5f5;
}

.option-card.disabled {
  cursor: default;
  opacity: 0.85;
}

.checkbox-box {
  width: 18px;
  height: 18px;
  border: 2px solid #d1d5db;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.option-card.selected .checkbox-box {
  border-color: #dc2626;
  background: #dc2626;
  color: #fff;
}

.check-mark {
  font-size: 12px;
  line-height: 1;
}

.option-label {
  font-size: 14px;
  color: var(--text);
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
