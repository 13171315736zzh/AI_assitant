<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TravelPlanConfirmMeta } from '@/types'

const TRANSPORT_MODES = ['飞机', '火车', '自驾', '其他'] as const

const props = defineProps<{
  confirm: TravelPlanConfirmMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: {
    origin: string
    destination: string
    start_date: string
    end_date: string
    purpose: string
    transport_mode: string
    transport_other?: string
  }]
  'update-draft': [payload: {
    origin: string
    destination: string
    start_date: string
    end_date: string
    purpose: string
    transport_mode: string
    transport_other?: string
  }]
}>()

const origin = ref(props.confirm.origin ?? '')
const destination = ref(props.confirm.destination ?? '')
const startDate = ref(props.confirm.start_date ?? '')
const endDate = ref(props.confirm.end_date ?? '')
const purpose = ref(props.confirm.purpose ?? '')
const transportMode = ref(props.confirm.transport_mode ?? '飞机')
const transportOther = ref(props.confirm.transport_other ?? '')

watch(
  () => props.confirm,
  (value) => {
    origin.value = value.origin ?? ''
    destination.value = value.destination ?? ''
    startDate.value = value.start_date ?? ''
    endDate.value = value.end_date ?? ''
    purpose.value = value.purpose ?? ''
    transportMode.value = value.transport_mode ?? '飞机'
    transportOther.value = value.transport_other ?? ''
  },
  { deep: true, immediate: true },
)

const isPending = computed(() => props.confirm.status === 'pending')
const showTransportOther = computed(() => transportMode.value === '其他')

function buildDraftPayload() {
  return {
    origin: origin.value.trim(),
    destination: destination.value.trim(),
    start_date: startDate.value,
    end_date: endDate.value,
    purpose: purpose.value.trim(),
    transport_mode: transportMode.value,
    transport_other: showTransportOther.value ? transportOther.value.trim() : undefined,
  }
}

watch([origin, destination, startDate, endDate, purpose, transportMode, transportOther], () => {
  if (!isPending.value) return
  emit('update-draft', buildDraftPayload())
}, { immediate: true })

const canConfirm = computed(() => {
  if (!isPending.value || props.submitting) return false
  if (!origin.value.trim() || !destination.value.trim()) return false
  if (!startDate.value || !endDate.value) return false
  if (showTransportOther.value && !transportOther.value.trim()) return false
  return true
})

function handleConfirm() {
  if (!canConfirm.value) return
  emit('confirm', buildDraftPayload())
}
</script>

<template>
  <div class="plan-confirm" :class="{ confirmed: !isPending }">
    <h4 class="section-title">{{ confirm.title }}</h4>

    <dl v-if="isPending" class="info-list">
      <div class="info-row">
        <dt>出发地</dt>
        <dd>
          <input v-model="origin" type="text" class="field-control field-input" placeholder="如：北京" :disabled="submitting" />
        </dd>
      </div>
      <div class="info-row">
        <dt>目的地</dt>
        <dd>
          <input v-model="destination" type="text" class="field-control field-input" placeholder="如：鄂尔多斯" :disabled="submitting" />
        </dd>
      </div>
      <div class="info-row">
        <dt>开始时间</dt>
        <dd>
          <input v-model="startDate" type="date" class="field-control field-input" :disabled="submitting" />
        </dd>
      </div>
      <div class="info-row">
        <dt>结束时间</dt>
        <dd>
          <input v-model="endDate" type="date" class="field-control field-input" :disabled="submitting" />
        </dd>
      </div>
      <div class="info-row info-row-top info-row-purpose">
        <dt>出差目的</dt>
        <dd>
          <textarea
            v-model="purpose"
            class="field-control field-textarea"
            rows="3"
            placeholder="如：项目现场维护"
            :disabled="submitting"
          />
        </dd>
      </div>
      <div class="info-row">
        <dt>交通方式</dt>
        <dd>
          <select v-model="transportMode" class="field-control field-select" :disabled="submitting">
            <option v-for="mode in TRANSPORT_MODES" :key="mode" :value="mode">{{ mode }}</option>
          </select>
        </dd>
      </div>
      <div v-if="showTransportOther" class="info-row">
        <dt>其他说明</dt>
        <dd>
          <input
            v-model="transportOther"
            type="text"
            class="field-control field-input"
            placeholder="请填写具体交通方式"
            :disabled="submitting"
          />
        </dd>
      </div>
    </dl>

    <dl v-else class="info-list">
      <div v-for="(item, i) in confirm.items" :key="i" class="info-row">
        <dt>{{ item.label }}</dt>
        <dd>{{ item.value }}</dd>
      </div>
    </dl>

    <div v-if="isPending" class="confirm-footer">
      <button
        type="button"
        class="btn-confirm"
        :disabled="!canConfirm"
        @click="handleConfirm"
      >
        {{ submitting ? '处理中…' : (confirm.confirm_label ?? '确认并开始办理差旅单') }}
      </button>
    </div>
    <p v-else class="confirmed-hint">信息已确认，正在继续办理。</p>
  </div>
</template>

<style scoped>
.plan-confirm {
  margin-top: 12px;
  padding: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  width: 100%;
  min-width: 0;
}

.section-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
}

.info-list {
  margin: 0 0 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.info-row {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 10px;
  padding: 8px 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  width: 100%;
  max-width: 100%;
}

.info-row-top {
  align-items: start;
}

.info-row-top dt {
  padding-top: 8px;
}

.info-row dt {
  color: var(--text-secondary);
}

.info-row dd {
  margin: 0;
  min-width: 0;
  width: 100%;
}

/* 统一输入/选择框：浅色底、同宽 */
.field-control {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  display: block;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: #ffffff;
  color: var(--text);
  font-size: 13px;
  font-family: inherit;
}

.field-input {
  height: 36px;
  padding: 0 10px;
}

.field-input[type='date'] {
  min-width: 0;
}

.field-select {
  height: 36px;
  padding: 0 10px;
  cursor: pointer;
  appearance: none;
  background-color: #ffffff;
  background-image: linear-gradient(45deg, transparent 50%, var(--text-secondary) 50%),
    linear-gradient(135deg, var(--text-secondary) 50%, transparent 50%);
  background-position: calc(100% - 16px) calc(50% + 2px), calc(100% - 11px) calc(50% + 2px);
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
  padding-right: 28px;
}

.field-textarea {
  min-height: 72px;
  padding: 8px 10px;
  resize: vertical;
  line-height: 1.5;
}

.info-row-purpose dd {
  width: 100%;
}

.field-control:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

[data-resolved-theme='dark'] .plan-confirm .field-control {
  background-color: #3a4049;
}

[data-resolved-theme='dark'] .plan-confirm .field-select {
  background-color: #3a4049;
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
