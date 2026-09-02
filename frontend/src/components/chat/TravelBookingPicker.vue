<script setup lang="ts">
import { computed, ref } from 'vue'
import type { BookingSelectionMeta, FlightOption, HotelOption } from '@/types'

const props = defineProps<{
  selection: BookingSelectionMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: { flight_no?: string; hotel_name?: string }]
}>()

const selectedFlightNo = ref<string | null>(
  props.selection.flights[0]?.flight_no ?? null,
)
const selectedHotelName = ref<string | null>(
  props.selection.hotels[0]?.name ?? null,
)

const isPending = computed(() => props.selection.status === 'pending')

const canSubmit = computed(() => {
  if (!isPending.value || props.submitting) return false
  if (props.selection.needs_flight && !selectedFlightNo.value) return false
  if (props.selection.needs_hotel && !selectedHotelName.value) return false
  return true
})

function selectFlight(flight: FlightOption) {
  if (!isPending.value) return
  selectedFlightNo.value = flight.flight_no
}

function selectHotel(hotel: HotelOption) {
  if (!isPending.value) return
  selectedHotelName.value = hotel.name
}

function handleConfirm() {
  if (!canSubmit.value) return
  emit('confirm', {
    flight_no: props.selection.needs_flight ? selectedFlightNo.value ?? undefined : undefined,
    hotel_name: props.selection.needs_hotel ? selectedHotelName.value ?? undefined : undefined,
  })
}

function formatTime(value: string): string {
  const parts = value.split(' ')
  return parts.length > 1 ? parts.slice(1).join(' ') : value
}
</script>

<template>
  <div class="booking-picker" :class="{ confirmed: !isPending }">
    <div class="picker-banner">
      <span class="picker-banner-icon" aria-hidden="true">☑</span>
      <span>请直接点击勾选 · 航班与酒店各选一项</span>
    </div>

    <section v-if="selection.needs_flight && selection.flights.length" class="picker-section">
      <h4 class="section-title">航班选项（{{ selection.flights.length }} 个备选）</h4>
      <div class="option-list">
        <label
          v-for="(flight, idx) in selection.flights"
          :key="flight.flight_no"
          class="option-card"
          :class="{ selected: selectedFlightNo === flight.flight_no, disabled: !isPending }"
        >
          <input
            type="radio"
            class="option-checkbox"
            name="flight-option"
            :value="flight.flight_no"
            :checked="selectedFlightNo === flight.flight_no"
            :disabled="!isPending"
            @change="selectFlight(flight)"
          />
          <span class="checkbox-box" aria-hidden="true">
            <span v-if="selectedFlightNo === flight.flight_no" class="check-mark">✓</span>
          </span>
          <div class="option-body" @click.prevent="selectFlight(flight)">
            <div class="option-head">
              <span class="option-title">{{ flight.flight_no }}</span>
              <span v-if="idx === 0" class="tag-recommend">推荐</span>
              <span class="option-sub">{{ flight.airline }}</span>
              <span class="option-price">{{ flight.price }} 元</span>
            </div>
            <div class="option-detail">
              {{ flight.origin }} → {{ flight.destination }}
            </div>
            <div class="option-detail muted">
              {{ formatTime(flight.departure_time) }} 出发 ·
              {{ formatTime(flight.arrival_time) }} 到达 · {{ flight.cabin }}
            </div>
          </div>
        </label>
      </div>
    </section>

    <section v-if="selection.needs_hotel && selection.hotels.length" class="picker-section">
      <h4 class="section-title">酒店选项（{{ selection.hotels.length }} 个备选）</h4>
      <div class="option-list">
        <label
          v-for="(hotel, idx) in selection.hotels"
          :key="hotel.name"
          class="option-card"
          :class="{ selected: selectedHotelName === hotel.name, disabled: !isPending }"
        >
          <input
            type="radio"
            class="option-checkbox"
            name="hotel-option"
            :value="hotel.name"
            :checked="selectedHotelName === hotel.name"
            :disabled="!isPending"
            @change="selectHotel(hotel)"
          />
          <span class="checkbox-box" aria-hidden="true">
            <span v-if="selectedHotelName === hotel.name" class="check-mark">✓</span>
          </span>
          <div class="option-body" @click.prevent="selectHotel(hotel)">
            <div class="option-head">
              <span class="option-title">{{ hotel.name }}</span>
              <span v-if="idx === 0" class="tag-recommend">推荐</span>
              <span class="option-price">{{ hotel.price_per_night }} 元/晚</span>
            </div>
            <div class="option-detail">
              {{ hotel.room_type }} · 距目的地约 {{ hotel.distance_km }} km
            </div>
            <div class="option-detail muted">
              {{ hotel.address }} · 入住 {{ hotel.check_in }} 至 {{ hotel.check_out }}
            </div>
          </div>
        </label>
      </div>
    </section>

    <div v-if="isPending" class="picker-footer">
      <button
        type="button"
        class="btn-confirm"
        :disabled="!canSubmit"
        @click="handleConfirm"
      >
        {{ submitting ? '提交中…' : '确认预订' }}
      </button>
    </div>
    <p v-else class="confirmed-hint">方案已确认，正在按所选内容继续办理。</p>
  </div>
</template>

<style scoped>
.booking-picker {
  margin-top: 12px;
  padding: 12px;
  background: linear-gradient(180deg, #fffafa 0%, var(--bg) 100%);
  border: 2px solid #f0b4b4;
  border-radius: var(--radius-sm);
  box-shadow: 0 2px 8px rgba(196, 30, 58, 0.06);
}

.booking-picker.confirmed {
  opacity: 0.88;
  border-color: var(--border);
  box-shadow: none;
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

.picker-banner-icon {
  font-size: 16px;
}

.picker-section + .picker-section {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--border);
}

.section-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
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
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
  position: relative;
}

.option-checkbox {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
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
  transition: border-color 0.15s, background 0.15s;
}

.check-mark {
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  line-height: 1;
}

.option-card:hover:not(.disabled) {
  border-color: #f0b4b4;
  background: #fffafa;
}

.option-card.selected {
  border-color: var(--primary);
  background: #fdf2f2;
  box-shadow: 0 0 0 1px rgba(196, 30, 58, 0.12);
}

.option-card.selected .checkbox-box {
  border-color: var(--primary);
  background: var(--primary);
}

.option-card.disabled {
  cursor: default;
}

.option-body {
  flex: 1;
  min-width: 0;
}

.option-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.option-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.tag-recommend {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  background: #fdf2f2;
  color: var(--primary);
  border: 1px solid #fecaca;
}

.option-sub {
  font-size: 12px;
  color: var(--text-secondary);
}

.option-price {
  margin-left: auto;
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
}

.option-detail {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.option-detail.muted {
  color: var(--text-muted);
}

.picker-footer {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.btn-confirm {
  width: 100%;
  height: 40px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
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
