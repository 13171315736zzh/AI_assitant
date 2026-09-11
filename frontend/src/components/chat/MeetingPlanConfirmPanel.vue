<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { MeetingPlanConfirmMeta, MeetingRoomOption } from '@/types'
import { useChatStore } from '@/stores/useChatStore'

const props = defineProps<{
  confirm: MeetingPlanConfirmMeta
  messageId?: string
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: {
    supplementary_content?: string
    subject?: string
    meeting_name?: string
    meeting_topic?: string
    room?: string | null
    room_flexible?: boolean
    room_preference?: string
    attendees?: string
    date_hint?: string
    start_hint?: string
    end_hint?: string
    confirm_node_id?: string
  }]
  'update-draft': [payload: Record<string, unknown>]
}>()

const chat = useChatStore()

const meetingTopic = ref('')
const attendees = ref('')
const roomInput = ref('')
const roomPreference = ref('')
const meetingDate = ref('')
const startTime = ref('14:00')
const endTime = ref('15:00')
const initialDate = ref('')
const initialStart = ref('14:00')
const initialEnd = ref('15:00')

const planMode = computed(() => {
  if (props.confirm.confirm_node_id === 'gn_meeting') return 'gn_only'
  if (props.confirm.confirm_node_id === 'room') return 'room_only'
  if (props.confirm.plan_mode === 'gn_only' || props.confirm.plan_mode === 'room_only') {
    return props.confirm.plan_mode
  }
  if (props.confirm.needs_gn_meeting && !props.confirm.needs_room_booking) return 'gn_only'
  if (props.confirm.needs_room_booking && !props.confirm.needs_gn_meeting) return 'room_only'
  if (props.confirm.needs_gn_meeting) return 'gn_only'
  return 'room_only'
})

const isGnCard = computed(() => planMode.value === 'gn_only')
const isRoomCard = computed(() => planMode.value === 'room_only')
const showRoomFields = computed(() => isRoomCard.value)

const cardTitle = computed(() => {
  if (isGnCard.value) return '国能会议（线上）'
  if (isRoomCard.value) return '会议室预约（线下）'
  return props.confirm.title ?? '会议预约'
})

const roomOptions = computed(() => (
  showRoomFields.value ? props.confirm.room_options ?? [] : []
))

function formatDateIso(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function dateHintToIso(dateHint: string | undefined): string {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  if (!dateHint) return formatDateIso(today)
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateHint)) return dateHint
  if (dateHint.includes('后天')) {
    const d = new Date(today)
    d.setDate(d.getDate() + 2)
    return formatDateIso(d)
  }
  if (dateHint.includes('明天')) {
    const d = new Date(today)
    d.setDate(d.getDate() + 1)
    return formatDateIso(d)
  }
  if (dateHint.includes('今天') || dateHint.includes('今日') || dateHint.includes('今晚')) {
    return formatDateIso(today)
  }
  return formatDateIso(today)
}

function normalizeTime(value: string | undefined, fallback: string): string {
  const raw = (value || fallback).trim()
  const match = raw.match(/^(\d{1,2}):(\d{2})/)
  if (!match) return fallback
  return `${match[1].padStart(2, '0')}:${match[2]}`
}

function syncTimeFieldsFromConfirm(value: MeetingPlanConfirmMeta) {
  const date = dateHintToIso(value.date_hint)
  const start = normalizeTime(value.start_hint, '14:00')
  const end = normalizeTime(value.end_hint, normalizeTime(value.start_hint, '14:00'))
  meetingDate.value = date
  startTime.value = start
  endTime.value = end
  initialDate.value = date
  initialStart.value = start
  initialEnd.value = end
}

let syncedFormKey = ''

function readSavedDraft(): Record<string, unknown> | null {
  if (!props.messageId) return null
  return chat.getWorkflowCardDraft(props.messageId, 'meeting_plan_confirm')
}

function syncFormFromConfirm(value: MeetingPlanConfirmMeta) {
  const formKey = `${props.messageId ?? ''}:${value.confirm_node_id ?? ''}:${value.status}`
  if (formKey === syncedFormKey) return
  syncedFormKey = formKey

  const draft = readSavedDraft()
  const pick = <T,>(draftKey: string, fallback: T): T => {
    const fromDraft = draft?.[draftKey]
    if (fromDraft !== undefined && fromDraft !== null && fromDraft !== '') {
      return fromDraft as T
    }
    return fallback
  }

  meetingTopic.value = pick(
    'meeting_topic',
    value.meeting_topic
      || value.meeting_name
      || value.subject
      || '',
  )
  attendees.value = pick('attendees', value.attendees ?? '')
  roomPreference.value = pick('room_preference', value.room_preference ?? '')

  const draftRoom = pick('room', null as string | null)
  const roomFromMeta = value.room_display
    || (value.selected_room
      ? (String(value.selected_room).match(/^\d{3}$/)
        ? `${value.selected_room} 会议室`
        : String(value.selected_room))
      : '')
  roomInput.value = draftRoom ?? roomFromMeta

  if (draft?.date_hint) {
    meetingDate.value = String(draft.date_hint)
    startTime.value = normalizeTime(String(draft.start_hint), startTime.value)
    endTime.value = normalizeTime(String(draft.end_hint), endTime.value)
  } else {
    syncTimeFieldsFromConfirm(value)
  }
}

watch(
  () => [
    props.messageId,
    props.confirm.confirm_node_id,
    props.confirm.status,
  ] as const,
  () => syncFormFromConfirm(props.confirm),
  { immediate: true },
)

const isPending = computed(() => props.confirm.status === 'pending')

const effectiveRoom = computed(() => roomInput.value.trim() || null)

const selectedRoomCode = computed(() => {
  const digits = roomInput.value.replace(/[^\d]/g, '')
  return digits.length === 3 ? digits : null
})

const resolvedSubject = computed(() => {
  const topic = meetingTopic.value.trim()
  return topic || '工作会议'
})

const confirmLabel = computed(() => {
  if (props.confirm.confirm_label) return props.confirm.confirm_label
  if (isGnCard.value) return '确认并开始国能会议预约'
  if (isRoomCard.value) {
    return !effectiveRoom.value && !roomPreference.value.trim()
      ? '确认并选择会议室'
      : '确认并开始会议室预约'
  }
  return '确认开始办理'
})

const readonlyItems = computed(() => {
  const items = props.confirm.items ?? []
  if (!isGnCard.value) return items
  return items.filter((item) => !['会议室', '会议室偏好', '人数要求'].includes(item.label))
})

function buildTimePhrase(): string | undefined {
  if (!meetingDate.value || !startTime.value) return undefined
  return `会议时间改为 ${meetingDate.value} ${startTime.value}-${endTime.value || startTime.value}`
}

function buildDraftPayload() {
  const timeChanged = meetingDate.value !== initialDate.value
    || startTime.value !== initialStart.value
    || endTime.value !== initialEnd.value

  const base = {
    subject: resolvedSubject.value,
    meeting_name: resolvedSubject.value,
    meeting_topic: meetingTopic.value.trim(),
    attendees: attendees.value.trim(),
    date_hint: meetingDate.value,
    start_hint: startTime.value,
    end_hint: endTime.value,
    supplementary_content: timeChanged ? buildTimePhrase() : undefined,
    confirm_node_id: props.confirm.confirm_node_id,
  }

  if (isGnCard.value) {
    return base
  }

  const room = effectiveRoom.value
  return {
    ...base,
    room,
    selected_room: selectedRoomCode.value ?? room,
    room_flexible: !room,
    room_preference: roomPreference.value.trim(),
  }
}

function syncDraft() {
  if (!isPending.value) return
  emit('update-draft', buildDraftPayload())
}

watch(
  [
    meetingTopic,
    attendees,
    roomInput,
    roomPreference,
    meetingDate,
    startTime,
    endTime,
  ],
  syncDraft,
  { deep: true, immediate: true },
)

function selectRoom(option: MeetingRoomOption) {
  if (!isPending.value) return
  roomInput.value = option.label || `${option.room} 会议室`
}

function clearRoomInput() {
  if (!isPending.value) return
  roomInput.value = ''
}

function handleConfirm() {
  if (!isPending.value || props.submitting) return
  emit('confirm', buildDraftPayload())
}
</script>

<template>
  <div class="plan-confirm" :class="{ confirmed: !isPending }">
    <h4 class="section-title">{{ confirm.title }}</h4>

    <section v-if="isPending" class="sub-card editable">
      <h5 class="sub-card-title">{{ cardTitle }}</h5>
      <p class="sub-card-desc">以下字段均可直接修改，确认后将按您填写的内容办理。</p>

      <dl class="info-list editable-list">
        <div class="info-row">
          <dt>会议主题</dt>
          <dd>
            <input
              v-model="meetingTopic"
              type="text"
              class="field-control field-input"
              placeholder="填写会议主题"
            />
          </dd>
        </div>

        <div class="info-row info-row-top">
          <dt>会议时间</dt>
          <dd>
            <div class="time-inputs">
              <label class="time-field">
                <span class="time-label">日期</span>
                <input v-model="meetingDate" type="date" class="field-control field-input" />
              </label>
              <label class="time-field">
                <span class="time-label">开始</span>
                <input v-model="startTime" type="time" class="field-control field-input" />
              </label>
              <label class="time-field">
                <span class="time-label">结束</span>
                <input v-model="endTime" type="time" class="field-control field-input" />
              </label>
            </div>
          </dd>
        </div>

        <div v-if="showRoomFields" class="info-row info-row-top">
          <dt>会议室</dt>
          <dd>
            <input
              v-model="roomInput"
              type="text"
              class="field-control field-input"
              placeholder="如 236 会议室"
            />
            <div v-if="roomOptions.length" class="chip-list">
              <button
                v-for="option in roomOptions"
                :key="option.room"
                type="button"
                class="chip"
                :class="{ selected: selectedRoomCode === option.room }"
                @click="selectRoom(option)"
              >
                {{ option.label }}
              </button>
              <button
                type="button"
                class="chip"
                :class="{ selected: !roomInput.trim() }"
                @click="clearRoomInput"
              >
                暂不指定
              </button>
            </div>
          </dd>
        </div>

        <div v-if="showRoomFields" class="info-row info-row-top">
          <dt>会议室偏好</dt>
          <dd>
            <textarea
              v-model="roomPreference"
              class="field-control attendees-input"
              rows="2"
              :placeholder="confirm.room_preference_hint ?? '如投屏、20 人以上、靠近电梯等'"
            />
          </dd>
        </div>

        <div class="info-row info-row-top">
          <dt>参会人员</dt>
          <dd>
            <textarea
              v-model="attendees"
              class="field-control attendees-input"
              rows="2"
              :placeholder="confirm.attendees_hint ?? '姓名、邮箱或国能工号，多人用顿号/逗号分隔'"
            />
          </dd>
        </div>
      </dl>
    </section>

    <section v-else class="sub-card readonly">
      <h5 class="sub-card-title">{{ cardTitle }}</h5>
      <dl class="info-list">
        <div v-for="(item, i) in readonlyItems" :key="i" class="info-row">
          <dt>{{ item.label }}</dt>
          <dd>{{ item.value }}</dd>
        </div>
      </dl>
    </section>

    <div v-if="isPending" class="confirm-footer">
      <button
        type="button"
        class="btn-confirm"
        :disabled="submitting"
        @click="handleConfirm"
      >
        {{ submitting ? '处理中…' : confirmLabel }}
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
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 600;
}

.sub-card {
  padding: 12px;
  background: color-mix(in srgb, var(--text) 4%, var(--surface));
  border: 1px solid color-mix(in srgb, var(--border) 80%, transparent);
  border-radius: var(--radius-sm);
}

.sub-card.readonly {
  background: color-mix(in srgb, var(--text) 3%, var(--surface));
}

.sub-card-title {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.sub-card-desc {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.editable-list {
  margin: 0;
}

.info-row-top {
  align-items: start;
}

.info-row-top dt {
  padding-top: 8px;
}

.field-hint {
  margin: 0 0 6px;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.field-control {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  display: block;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: #fff;
  color: var(--text);
  font-size: 13px;
  font-family: inherit;
}

.field-input {
  height: 36px;
  padding: 0 10px;
}

.field-input:focus,
.attendees-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--primary) 16%, transparent);
}

.attendees-input {
  width: 100%;
  min-height: 64px;
  padding: 10px 12px;
  resize: vertical;
  line-height: 1.5;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.time-inputs {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr;
  gap: 8px;
}

.time-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.time-label {
  font-size: 11px;
  color: var(--text-muted);
}

.room-input {
  margin-top: 4px;
}

.chip {
  padding: 7px 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text);
  font-size: 12px;
  cursor: pointer;
}

.chip.selected {
  border-color: var(--primary);
  background: color-mix(in srgb, var(--primary) 12%, var(--surface));
  color: var(--primary);
  font-weight: 500;
}

.chip:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.info-list {
  margin: 0;
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
  margin-top: 12px;
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
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

@media (max-width: 520px) {
  .time-inputs {
    grid-template-columns: 1fr;
  }

  .info-row {
    grid-template-columns: 1fr;
  }

  .info-row-top dt {
    padding-top: 0;
  }
}
</style>
