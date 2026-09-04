<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { MeetingPlanConfirmMeta, MeetingRoomOption, MeetingTimeOption } from '@/types'

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

const needsRoomBooking = computed(() => {
  if (props.confirm.plan_mode === 'gn_only') return false
  if (props.confirm.needs_room_booking === false) return false
  if (props.confirm.needs_room_booking === true) return true
  return props.confirm.plan_mode === 'room_only'
    || props.confirm.plan_mode === 'combined'
    || (props.confirm.room_options?.length ?? 0) > 0
})

const planMode = computed(() => props.confirm.plan_mode ?? 'room_only')
const timeOptions = computed(() => props.confirm.time_options ?? [])
const roomOptions = computed(() => (needsRoomBooking.value ? props.confirm.room_options ?? [] : []))

const defaultOption = computed(
  () => timeOptions.value.find((item) => item.selected) ?? timeOptions.value[0] ?? null,
)
const selectedTime = ref<MeetingTimeOption | null>(defaultOption.value)

watch(
  () => props.confirm,
  (value) => {
    subject.value = value.subject ?? '工作会议'
    attendees.value = value.attendees ?? ''
    roomFlexible.value = Boolean(value.room_flexible)
    selectedTime.value = value.time_options?.find((item) => item.selected)
      ?? value.time_options?.[0]
      ?? null

    const room = value.selected_room ?? null
    const inOptions = value.room_options?.some((item) => item.room === room)
    if (room && inOptions) {
      selectedRoom.value = room
      customRoom.value = ''
    } else if (room) {
      selectedRoom.value = null
      customRoom.value = room
    } else {
      selectedRoom.value = null
      customRoom.value = ''
    }
  },
  { deep: true },
)

const isPending = computed(() => props.confirm.status === 'pending')

const effectiveRoom = computed(() => {
  if (roomFlexible.value) return null
  return selectedRoom.value ?? (customRoom.value.trim() || null)
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

function buildTimePhrase(option: MeetingTimeOption): string | undefined {
  const hour = Number.parseInt(option.start_hint.split(':')[0] ?? '14', 10)
  const dateHint = option.date_hint || '今天'
  if (dateHint === '今天' && hour >= 18) return `今晚${hour}点`
  if (dateHint === '今天') {
    const period = hour < 12 ? '上午' : '下午'
    return `今天${period}${hour}点`
  }
  if (dateHint === '明天') {
    const period = hour < 12 ? '上午' : '下午'
    return `明天${period}${hour}点`
  }
  return `${dateHint}${hour}点`
}

function buildDraftPayload() {
  const timeChanged = selectedTime.value
    && defaultOption.value
    && selectedTime.value.start_hint !== defaultOption.value.start_hint
  const room = effectiveRoom.value

  return {
    subject: subject.value.trim(),
    room,
    selected_room: room,
    room_flexible: roomFlexible.value,
    attendees: attendees.value.trim(),
    date_hint: selectedTime.value?.date_hint,
    start_hint: selectedTime.value?.start_hint,
    end_hint: selectedTime.value?.end_hint,
    supplementary_content: timeChanged && selectedTime.value
      ? buildTimePhrase(selectedTime.value)
      : undefined,
  }
}

function syncDraft() {
  if (!isPending.value) return
  emit('update-draft', buildDraftPayload())
}

watch([subject, attendees, selectedRoom, roomFlexible, customRoom, selectedTime], syncDraft, {
  deep: true,
  immediate: true,
})

function selectTime(option: MeetingTimeOption) {
  if (!isPending.value) return
  selectedTime.value = option
}

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

function onCustomRoomInput() {
  if (!isPending.value || !customRoom.value.trim()) return
  roomFlexible.value = false
  selectedRoom.value = null
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
        <span class="field-key">会议主题</span>
        <div class="field-col">
          <input
            v-model="subject"
            type="text"
            class="field-input"
            placeholder="填写会议主题"
            :disabled="submitting"
          />
        </div>
      </div>

      <div class="field-row">
        <span class="field-key">会议时间</span>
        <div class="field-col">
          <p v-if="timeOptions.length" class="field-hint">
            {{ confirm.time_hint ?? '点选确认时段' }}
          </p>
          <div v-if="timeOptions.length" class="chip-list">
            <button
              v-for="option in timeOptions"
              :key="option.label"
              type="button"
              class="chip"
              :class="{ selected: selectedTime?.start_hint === option.start_hint }"
              :disabled="submitting"
              @click="selectTime(option)"
            >
              {{ option.label }}
            </button>
          </div>
          <span v-else class="editable-display static">
            {{ confirm.items.find((item) => item.label.includes('时间'))?.value ?? '—' }}
          </span>
        </div>
      </div>

      <div v-if="needsRoomBooking" class="field-row">
        <span class="field-key">会议室</span>
        <div class="field-col">
          <p class="field-hint">{{ confirm.room_hint ?? '点选、灵活选择，或在下方输入会议室名称' }}</p>
          <div class="chip-list">
            <button
              v-for="option in roomOptions"
              :key="option.room"
              type="button"
              class="chip"
              :class="{ selected: !roomFlexible && !customRoom.trim() && selectedRoom === option.room }"
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
              灵活选择
            </button>
          </div>
          <input
            v-model="customRoom"
            type="text"
            class="field-input room-input"
            placeholder="或直接输入会议室名称，如 236、总部 A301"
            :disabled="submitting || roomFlexible"
            @input="onCustomRoomInput"
          />
        </div>
      </div>

      <div v-else-if="planMode === 'gn_only'" class="field-row">
        <span class="field-key">会议形式</span>
        <div class="field-col">
          <span class="editable-display static">国能会议（线上/视频）</span>
        </div>
      </div>

      <div class="field-row">
        <span class="field-key">参会人员</span>
        <div class="field-col">
          <p class="field-hint">{{ confirm.attendees_hint ?? '填写参会人员' }}</p>
          <input
            v-model="attendees"
            type="text"
            class="field-input"
            placeholder="如：张明、李经理（可留空）"
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

.field-key {
  padding-top: 8px;
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

.editable-display {
  width: 100%;
  min-height: 36px;
  padding: 8px 10px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.editable-display.static {
  cursor: default;
  border-style: solid;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
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

.chip:disabled,
.field-input:disabled,
.editable-display:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.inline-edit {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.mini-btn {
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  cursor: pointer;
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
