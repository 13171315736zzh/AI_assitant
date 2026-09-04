<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { LeavePlanConfirmMeta } from '@/types'

const LEAVE_TYPES = ['事假', '病假', '年假', '调休', '婚假', '产假', '陪产假', '丧假'] as const
const PERIOD_OPTIONS = ['全天', '上午', '下午'] as const

const props = defineProps<{
  confirm: LeavePlanConfirmMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: {
    reason: string
    attachment_name?: string
    leave_type?: string
    date_start?: string
    date_end?: string
    start_period?: string
    end_period?: string
  }]
  'update-draft': [payload: {
    reason: string
    attachment_name?: string
    leave_type?: string
    date_start?: string
    date_end?: string
    start_period?: string
    end_period?: string
  }]
}>()

const leaveType = ref(props.confirm.leave_type ?? '事假')
const dateStart = ref(props.confirm.date_start ?? '')
const dateEnd = ref(props.confirm.date_end ?? '')
const startPeriod = ref(props.confirm.start_period ?? '全天')
const endPeriod = ref(props.confirm.end_period ?? '全天')
const reason = ref(props.confirm.reason ?? '')
const attachmentName = ref(props.confirm.attachment_name ?? '')

watch(
  () => props.confirm,
  (value) => {
    leaveType.value = value.leave_type ?? '事假'
    dateStart.value = value.date_start ?? ''
    dateEnd.value = value.date_end ?? ''
    startPeriod.value = value.start_period ?? '全天'
    endPeriod.value = value.end_period ?? '全天'
    reason.value = value.reason ?? ''
    attachmentName.value = value.attachment_name ?? ''
  },
  { deep: true },
)

function buildDraftPayload() {
  return {
    reason: reason.value.trim(),
    attachment_name: attachmentName.value.trim() || undefined,
    leave_type: leaveType.value,
    date_start: dateStart.value || undefined,
    date_end: dateEnd.value || undefined,
    start_period: startPeriod.value,
    end_period: endPeriod.value,
  }
}

watch([leaveType, dateStart, dateEnd, startPeriod, endPeriod, reason, attachmentName], () => {
  if (!isPending.value) return
  emit('update-draft', buildDraftPayload())
}, { immediate: true })

const isPending = computed(() => props.confirm.status === 'pending')
const requiresReason = computed(() => props.confirm.requires_reason !== false)
const sameDay = computed(() => dateStart.value && dateEnd.value && dateStart.value === dateEnd.value)

const canConfirm = computed(() => {
  if (!isPending.value || props.submitting) return false
  if (requiresReason.value && !reason.value.trim()) return false
  if (!dateStart.value || !dateEnd.value) return false
  return true
})

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  attachmentName.value = file?.name ?? ''
}

function handleConfirm() {
  if (!canConfirm.value) return
  emit('confirm', buildDraftPayload())
}
</script>

<template>
  <div class="plan-confirm" :class="{ confirmed: !isPending }">
    <h4 class="section-title">{{ confirm.title }}</h4>

    <dl v-if="!isPending" class="info-list">
      <div v-for="(item, i) in confirm.items" :key="i" class="info-row">
        <dt>{{ item.label }}</dt>
        <dd>{{ item.value }}</dd>
      </div>
    </dl>

    <div v-if="isPending" class="fields">
      <div class="field-row">
        <span class="field-key">请假类型</span>
        <select v-model="leaveType" class="field-input field-select" :disabled="submitting">
          <option v-for="opt in LEAVE_TYPES" :key="opt" :value="opt">{{ opt }}</option>
        </select>
      </div>
      <div class="field-row">
        <span class="field-key">开始日期</span>
        <input v-model="dateStart" type="date" class="field-input" :disabled="submitting" />
      </div>
      <div class="field-row">
        <span class="field-key">结束日期</span>
        <input v-model="dateEnd" type="date" class="field-input" :disabled="submitting" />
      </div>
      <div v-if="sameDay" class="field-row">
        <span class="field-key">时段</span>
        <select v-model="startPeriod" class="field-input field-select" :disabled="submitting">
          <option v-for="opt in PERIOD_OPTIONS" :key="opt" :value="opt">{{ opt }}</option>
        </select>
      </div>
      <template v-else>
        <div class="field-row">
          <span class="field-key">开始时段</span>
          <select v-model="startPeriod" class="field-input field-select" :disabled="submitting">
            <option v-for="opt in PERIOD_OPTIONS" :key="`s-${opt}`" :value="opt">{{ opt }}</option>
          </select>
        </div>
        <div class="field-row">
          <span class="field-key">结束时段</span>
          <select v-model="endPeriod" class="field-input field-select" :disabled="submitting">
            <option v-for="opt in PERIOD_OPTIONS" :key="`e-${opt}`" :value="opt">{{ opt }}</option>
          </select>
        </div>
      </template>
      <div class="field-row field-row-top">
        <span class="field-key">请假事由<span class="required">*</span></span>
        <textarea
          v-model="reason"
          class="reason-input"
          rows="3"
          placeholder="请填写请假原因"
          :disabled="submitting"
        />
      </div>
      <div class="field-row field-row-top">
        <span class="field-key">附件</span>
        <div class="upload-col">
          <input
            type="file"
            accept="image/*,.pdf"
            class="file-input"
            :disabled="submitting"
            @change="handleFileChange"
          />
          <span v-if="attachmentName" class="file-name">{{ attachmentName }}</span>
        </div>
      </div>
    </div>

    <div v-if="isPending" class="confirm-footer">
      <button
        type="button"
        class="btn-confirm"
        :disabled="!canConfirm"
        @click="handleConfirm"
      >
        {{ submitting ? '处理中…' : '确认提交请假' }}
      </button>
    </div>
    <p v-else class="confirmed-hint">信息已确认，正在继续办理。</p>
  </div>
</template>

<style scoped>
.plan-confirm {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.section-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.field-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.field-row-top {
  align-items: flex-start;
}

.field-key {
  width: 88px;
  flex-shrink: 0;
  padding-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.field-row-top .field-key {
  padding-top: 10px;
}

.required {
  color: #dc2626;
  margin-left: 2px;
}

.field-input {
  flex: 1;
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
}

.field-select {
  cursor: pointer;
}

.reason-input {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: inherit;
  resize: vertical;
  min-height: 72px;
  box-sizing: border-box;
  background: var(--surface);
  color: var(--text);
}

.upload-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 6px;
}

.file-input {
  font-size: 13px;
}

.file-name {
  font-size: 12px;
  color: var(--text-muted);
}

.info-list {
  margin: 0 0 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.info-row {
  display: grid;
  grid-template-columns: 88px 1fr;
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
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.btn-confirm:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.confirmed-hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
