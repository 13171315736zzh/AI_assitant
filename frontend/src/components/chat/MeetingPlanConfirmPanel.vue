<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { MeetingPlanConfirmMeta, MeetingRoomOption } from '@/types'

const props = defineProps<{
  confirm: MeetingPlanConfirmMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: {
    supplementary_content?: string
    subject?: string
    room?: string | null
    room_flexible?: boolean
    room_preference?: string
    attendees?: string
    date_hint?: string
    start_hint?: string
    end_hint?: string
  }]
  'update-draft': [payload: Record<string, unknown>]
}>()

const subject = ref(props.confirm.subject ?? '工作会议')
const attendees = ref(props.confirm.attendees ?? '')
const selectedRoom = ref<string | null>(props.confirm.selected_room ?? null)
const roomFlexible = ref(Boolean(props.confirm.room_flexible))
const customRoom = ref('')
const roomPreference = ref('')
const meetingDate = ref('')
const startTime = ref('14:00')
const endTime = ref('15:00')
const initialDate = ref('')
const initialStart = ref('14:00')
const initialEnd = ref('15:00')

const needsRoomBooking = computed(() => {
  if (props.confirm.plan_mode === 'gn_only') return false
  if (props.confirm.needs_room_booking === false) return false
  if (props.confirm.needs_room_booking === true) return true
  return props.confirm.plan_mode === 'room_only'
    || props.confirm.plan_mode === 'combined'
    || (props.confirm.room_options?.length ?? 0) > 0
})

const planMode = computed(() => props.confirm.plan_mode ?? 'room_only')
const roomOptions = computed(() => (needsRoomBooking.value ? props.confirm.room_options ?? [] : []))
const showGnMeetingForm = computed(
  () => planMode.value === 'gn_only' || (props.confirm.needs_gn_meeting && !needsRoomBooking.value),
)

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

watch(
  () => props.confirm,
  (value) => {
    subject.value = value.subject ?? '工作会议'
    attendees.value = value.attendees ?? ''
    roomPreference.value = value.room_preference ?? ''
    roomFlexible.value = Boolean(value.room_flexible)
    syncTimeFieldsFromConfirm(value)

    const room = value.selected_room ?? null
    const inOptions = value.room_options?.some((item) => item.room === room)
    if (roomFlexible.value) {
      selectedRoom.value = null
      customRoom.value = room && !inOptions ? room : ''
    } else if (room && inOptions) {
      selectedRoom.value = room
      customRoom.value = ''
    } else {
      selectedRoom.value = null
      customRoom.value = ''
    }
  },
  { deep: true, immediate: true },
)

const isPending = computed(() => props.confirm.status === 'pending')

const showCustomRoomInput = computed(() => roomFlexible.value)

const effectiveRoom = computed(() => {
  if (roomFlexible.value) {
    return customRoom.value.trim() || null
  }
  return selectedRoom.value
})

const confirmLabel = computed(() => {
  if (props.confirm.confirm_label) return props.confirm.confirm_label
  if (planMode.value === 'gn_only') return '确认并开始国能会议预约'
  if (planMode.value === 'combined') return '确认并办理（国能会议 + 会议室）'
  if (roomFlexible.value && !effectiveRoom.value) {
    return '确认并选择会议室'
  }
  return '确认开始办理'
})

function buildTimePhrase(): string | undefined {
  if (!meetingDate.value || !startTime.value) return undefined
  return `会议时间改为 ${meetingDate.value} ${startTime.value}-${endTime.value || startTime.value}`
}

function buildDraftPayload() {
  const room = effectiveRoom.value
  const timeChanged = meetingDate.value !== initialDate.value
    || startTime.value !== initialStart.value
    || endTime.value !== initialEnd.value

  return {
    subject: subject.value.trim(),
    room,
    selected_room: room,
    room_flexible: roomFlexible.value,
    room_preference: roomPreference.value.trim(),
    attendees: attendees.value.trim(),
    date_hint: meetingDate.value,
    start_hint: startTime.value,
    end_hint: endTime.value,
    supplementary_content: timeChanged ? buildTimePhrase() : undefined,
  }
}

function syncDraft() {
  if (!isPending.value) return
  emit('update-draft', buildDraftPayload())
}

watch(
  [subject, attendees, selectedRoom, roomFlexible, customRoom, roomPreference, meetingDate, startTime, endTime],
  syncDraft,
  { deep: true, immediate: true },
)

function selectRoom(option: MeetingRoomOption) {
  if (!isPending.value) return
  roomFlexible.value = false
  selectedRoom.value = option.room
  customRoom.value = ''
}

function selectFlexibleRoom() {
  if (!isPending.value) return
  roomFlexible.value = true
  selectedRoom.value = null
  customRoom.value = ''
}

function handleConfirm() {
  if (!isPending.value || props.submitting) return
  emit('confirm', buildDraftPayload())
}
</script>

<template>
  <div class="plan-confirm" :class="{ confirmed: !isPending }">
    <h4 class="section-title">{{ confirm.title }}</h4>

    <div v-if="isPending" class="fields">
      <div class="field-row">
        <span class="field-key">会议名称</span>
        <div class="field-col">
          <input
            v-model="subject"
            type="text"
            class="field-input"
            placeholder="填写会议名称或主题"
            :disabled="submitting"
          />
        </div>
      </div>

      <div class="field-row">
        <span class="field-key">会议时间</span>
        <div class="field-col">
          <div class="time-inputs">
            <label class="time-field">
              <span class="time-label">日期</span>
              <input
                v-model="meetingDate"
                type="date"
                class="field-input"
                :disabled="submitting"
              />
            </label>
            <label class="time-field">
              <span class="time-label">开始</span>
              <input
                v-model="startTime"
                type="time"
                class="field-input"
                :disabled="submitting"
              />
            </label>
            <label class="time-field">
              <span class="time-label">结束</span>
              <input
                v-model="endTime"
                type="time"
                class="field-input"
                :disabled="submitting"
              />
            </label>
          </div>
        </div>
      </div>

      <div v-if="needsRoomBooking" class="field-row field-row-top">
        <span class="field-key">会议室</span>
        <div class="field-col">
          <p class="field-hint">
            {{ confirm.room_hint ?? '点选具体会议室，或选择「输入其它」后填写名称' }}
          </p>
          <div class="chip-list">
            <button
              v-for="option in roomOptions"
              :key="option.room"
              type="button"
              class="chip"
              :class="{ selected: !roomFlexible && selectedRoom === option.room }"
              :disabled="submitting"
              @click="selectRoom(option)"
            >
              {{ option.label }}
            </button>
            <button
              type="button"
              class="chip"
              :class="{ selected: roomFlexible }"
              :disabled="submitting"
              @click="selectFlexibleRoom"
            >
              输入其它
            </button>
          </div>
          <input
            v-if="showCustomRoomInput"
            v-model="customRoom"
            type="text"
            class="field-input room-input"
            placeholder="请输入会议室名称"
            :disabled="submitting"
          />
        </div>
      </div>

      <div v-if="needsRoomBooking" class="field-row field-row-top">
        <span class="field-key">会议室偏好</span>
        <div class="field-col">
          <p class="field-hint">
            {{ confirm.room_preference_hint ?? '如投屏、20 人以上、靠近电梯等' }}
          </p>
          <textarea
            v-model="roomPreference"
            class="attendees-input"
            rows="2"
            placeholder="选填，描述对会议室的要求"
            :disabled="submitting"
          />
        </div>
      </div>

      <div v-else-if="showGnMeetingForm" class="field-row">
        <span class="field-key">会议形式</span>
        <div class="field-col">
          <span class="chip chip-fixed selected">国能会议</span>
        </div>
      </div>

      <div class="field-row field-row-top">
        <span class="field-key">参会人员</span>
        <div class="field-col">
          <p class="field-hint">
            {{ confirm.attendees_hint ?? '填写参会人姓名、邮箱或国能工号，多人用顿号/逗号分隔' }}
          </p>
          <textarea
            v-model="attendees"
            class="attendees-input"
            rows="2"
            placeholder="如：张明、zhangming@company.com、0176338"
            :disabled="submitting"
          />
        </div>
      </div>
    </div>

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
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
}

.field-row {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 8px;
}

.field-row-top {
  align-items: start;
}

.field-row-top .field-key {
  padding-top: 8px;
}

.field-key {
  font-size: 12px;
  color: var(--text-secondary);
}

.field-col {
  min-width: 0;
}

.field-hint {
  margin: 0 0 6px;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.field-input {
  width: 100%;
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
}

.attendees-input {
  width: 100%;
  min-height: 64px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  font-family: inherit;
  resize: vertical;
  line-height: 1.5;
}

.editable-display {
  width: 100%;
  min-height: 36px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
}

.editable-display.static {
  border-style: solid;
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

.chip-fixed {
  display: inline-flex;
  align-items: center;
  cursor: default;
  pointer-events: none;
  user-select: none;
}

.chip:disabled,
.field-input:disabled,
.attendees-input:disabled {
  opacity: 0.55;
  cursor: not-allowed;
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

@media (max-width: 520px) {
  .time-inputs {
    grid-template-columns: 1fr;
  }
}
</style>
