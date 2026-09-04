<script setup lang="ts">
import { computed, ref } from 'vue'
import type { RoomSelectionMeta } from '@/types'

const props = defineProps<{
  selection: RoomSelectionMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: { room: string }]
}>()

const preferredRooms = ['235', '236', '240']

const selectedRoom = ref<string | null>(
  props.selection.options.find((o) => preferredRooms.includes(o.room))?.room
    ?? props.selection.options[0]?.room
    ?? null,
)

const isPending = computed(() => props.selection.status === 'pending')
const isBrowseMode = computed(() => Boolean(props.selection.browse_mode))
const sectionTitle = computed(() => {
  if (isBrowseMode.value) {
    const equip = props.selection.equipment_pref || '投屏'
    return `可选会议室（${equip} · ${props.selection.time_label}）`
  }
  return `推荐可用会议室（${props.selection.time_label}）`
})

function selectRoom(room: string) {
  if (!isPending.value) return
  selectedRoom.value = room
}

function handleConfirm() {
  if (!isPending.value || !selectedRoom.value || props.submitting) return
  emit('confirm', { room: selectedRoom.value })
}
</script>

<template>
  <div class="room-picker" :class="{ confirmed: !isPending }">
    <div class="picker-banner">
      <span class="picker-banner-icon" aria-hidden="true">☑</span>
      <span>{{ isBrowseMode ? '请点选符合条件的会议室' : '请直接点击勾选 · 选择可用会议室' }}</span>
    </div>

    <div v-if="selection.conflict_reason && !isBrowseMode" class="conflict-box">
      {{ selection.conflict_reason }}
    </div>

    <section class="picker-section">
      <h4 class="section-title">{{ sectionTitle }}</h4>
      <div class="option-list">
        <button
          v-for="opt in selection.options"
          :key="opt.room"
          type="button"
          class="option-card"
          :class="{ selected: selectedRoom === opt.room, disabled: !isPending }"
          :disabled="!isPending"
          @click="selectRoom(opt.room)"
        >
          <span class="checkbox-box" aria-hidden="true">
            <span v-if="selectedRoom === opt.room" class="check-mark">✓</span>
          </span>
          <div class="option-body">
            <div class="option-head">
              <span class="option-title">{{ opt.room }} 会议室</span>
              <span v-if="opt.room === '235'" class="tag-recommend">推荐</span>
            </div>
            <div class="option-detail">
              {{ opt.floor }} · 容纳 {{ opt.capacity }} 人 · {{ opt.equipment }}
            </div>
          </div>
        </button>
      </div>
    </section>

    <div v-if="isPending" class="picker-footer">
      <button
        type="button"
        class="btn-confirm"
        :disabled="!selectedRoom || submitting"
        @click="handleConfirm"
      >
        {{ submitting ? '提交中…' : '确认预约' }}
      </button>
    </div>
    <p v-else class="confirmed-hint">会议室已确认，正在继续办理。</p>
  </div>
</template>

<style scoped>
.room-picker {
  margin-top: 12px;
  padding: 12px;
  background: linear-gradient(180deg, #fffafa 0%, var(--bg) 100%);
  border: 2px solid #f0b4b4;
  border-radius: var(--radius-sm);
}

.picker-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  margin-bottom: 12px;
  background: #fdf2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
}

.conflict-box {
  padding: 10px 12px;
  margin-bottom: 12px;
  background: #fff8f0;
  border: 1px solid #f0dcc8;
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.6;
  color: #92400e;
}

.picker-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
}

.option-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-card {
  display: flex;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.option-card:hover:not(:disabled) {
  border-color: #f0b4b4;
  background: #fffafa;
}

.option-card.selected {
  border-color: var(--primary);
  background: #fdf2f2;
}

.checkbox-box {
  width: 18px;
  height: 18px;
  margin-top: 2px;
  border: 2px solid #cbd5e1;
  border-radius: 4px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
}

.option-card.selected .checkbox-box {
  border-color: var(--primary);
  background: var(--primary);
}

.check-mark {
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  line-height: 1;
}

.option-card.disabled {
  cursor: default;
}

.option-radio {
  width: 16px;
  height: 16px;
  margin-top: 2px;
  border: 2px solid #cbd5e1;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
}

.option-card.selected .option-radio {
  border-color: var(--primary);
}

.option-card.selected .option-radio::after {
  content: '';
  position: absolute;
  inset: 3px;
  border-radius: 50%;
  background: var(--primary);
}

.option-body {
  flex: 1;
}

.option-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.option-title {
  font-size: 13px;
  font-weight: 600;
}

.tag-recommend {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  background: #fdf2f2;
  color: var(--primary);
  border: 1px solid #fecaca;
}

.option-detail {
  font-size: 12px;
  color: var(--text-secondary);
}

.picker-footer {
  margin-top: 14px;
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
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
