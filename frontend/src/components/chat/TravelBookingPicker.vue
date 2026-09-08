<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { BookingSelectionMeta, FlightOption, HotelOption, TrainOption } from '@/types'

const props = defineProps<{
  selection: BookingSelectionMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: { flight_no?: string; train_no?: string; hotel_name?: string; drive?: boolean }]
}>()

type TransportMode = 'flight' | 'train' | 'drive'

const transportMode = ref<TransportMode>(
  (props.selection.transport_type as TransportMode) ?? 'flight',
)

const isPending = computed(() => props.selection.status === 'pending')
const leg = computed(() => props.selection.leg ?? 'outbound')
const legLabel = computed(() => (leg.value === 'return' ? '返程' : '去程'))
const needsReturn = computed(() => Boolean(props.selection.needs_return))

const selectedFlightNo = ref<string | null>(
  props.selection.flights[0]?.flight_no ?? null,
)
const selectedTrainNo = ref<string | null>(
  props.selection.trains?.[0]?.train_no ?? null,
)
const selectedHotelName = ref<string | null>(
  props.selection.needs_flight ? null : (props.selection.hotels[0]?.name ?? null),
)

const routeOrigin = computed(() =>
  props.selection.origin?.trim()
  || props.selection.trains?.[0]?.origin?.trim()
  || props.selection.flights?.[0]?.origin?.trim()
  || '',
)

const routeDestination = computed(() =>
  props.selection.destination?.trim()
  || props.selection.trains?.[0]?.destination?.trim()
  || props.selection.flights?.[0]?.destination?.trim()
  || '',
)

const isTransportBooking = computed(
  () => props.selection.needs_flight && props.selection.booking_kind === 'transport',
)

const isDriveMode = computed(() => transportMode.value === 'drive')
const isTrainMode = computed(() => transportMode.value === 'train')
const isFlightMode = computed(() => transportMode.value === 'flight')

const showPickerBanner = computed(() => {
  if (isTransportBooking.value && isDriveMode.value) return false
  if (isTrainMode.value && isTransportBooking.value && !props.selection.needs_hotel) {
    return false
  }
  return true
})

const hasTransportSelected = computed(() => {
  if (isDriveMode.value) return true
  return isTrainMode.value ? Boolean(selectedTrainNo.value) : Boolean(selectedFlightNo.value)
})

const hotelSelectionEnabled = computed(() => {
  if (!props.selection.needs_hotel) return false
  if (!props.selection.needs_flight) return true
  return hasTransportSelected.value
})

const canSubmit = computed(() => {
  if (!isPending.value || props.submitting) return false
  if (props.selection.needs_flight && isTransportBooking.value) {
    if (isDriveMode.value) return true
    if (isTrainMode.value && !selectedTrainNo.value) return false
    if (isFlightMode.value && !selectedFlightNo.value) return false
  }
  if (props.selection.needs_hotel && !selectedHotelName.value) return false
  return true
})

const transportModeOptions: { value: TransportMode; label: string }[] = [
  { value: 'flight', label: '飞机' },
  { value: 'train', label: '火车' },
  { value: 'drive', label: '自驾' },
]

function selectFlight(flight: FlightOption) {
  if (!isPending.value) return
  selectedFlightNo.value = flight.flight_no
}

function selectTrain(train: TrainOption) {
  if (!isPending.value) return
  selectedTrainNo.value = train.train_no
}

function selectHotel(hotel: HotelOption) {
  if (!isPending.value || !hotelSelectionEnabled.value) return
  selectedHotelName.value = hotel.name
}

function handleConfirm() {
  if (!canSubmit.value) return
  emit('confirm', {
    flight_no: isFlightMode.value && props.selection.needs_flight
      ? selectedFlightNo.value ?? undefined
      : undefined,
    train_no: isTrainMode.value && props.selection.needs_flight
      ? selectedTrainNo.value ?? undefined
      : undefined,
    hotel_name: props.selection.needs_hotel ? selectedHotelName.value ?? undefined : undefined,
    drive: isDriveMode.value && isTransportBooking.value ? true : undefined,
  })
}

watch(selectedFlightNo, (flightNo) => {
  if (props.selection.needs_flight && props.selection.needs_hotel && !flightNo && isFlightMode.value) {
    selectedHotelName.value = null
  }
})

watch(selectedTrainNo, (trainNo) => {
  if (props.selection.needs_flight && props.selection.needs_hotel && !trainNo && isTrainMode.value) {
    selectedHotelName.value = null
  }
})

watch(
  () => props.selection.transport_type,
  (mode) => {
    if (mode === 'flight' || mode === 'train' || mode === 'drive') {
      transportMode.value = mode
    }
  },
)

function formatTime(value: string): string {
  const parts = value.split(' ')
  return parts.length > 1 ? parts.slice(1).join(' ') : value
}
</script>

<template>
  <div class="booking-picker" :class="{ confirmed: !isPending }">
    <div v-if="isTransportBooking" class="leg-card">
      <div class="leg-head">
        <span class="leg-badge">{{ legLabel }}</span>
        <span v-if="needsReturn" class="leg-step">
          {{ leg === 'outbound' ? '第 1 段 · 共 2 段' : '第 2 段 · 共 2 段' }}
        </span>
      </div>
      <div class="route-row">
        <span class="route-label">路线</span>
        <span class="route-value">{{ routeOrigin }} → {{ routeDestination }}</span>
      </div>
      <div v-if="selection.departure_date" class="route-date">
        出发日期 {{ selection.departure_date }}
      </div>
      <div class="mode-row">
        <label class="mode-label" for="transport-mode">交通方式</label>
        <select
          id="transport-mode"
          v-model="transportMode"
          class="mode-select"
          :disabled="!isPending || submitting"
        >
          <option
            v-for="opt in transportModeOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </option>
        </select>
      </div>
    </div>

    <div
      v-if="showPickerBanner"
      class="picker-banner"
    >
      <span class="picker-banner-icon" aria-hidden="true">☑</span>
      <span v-if="selection.needs_flight && selection.needs_hotel">
        请先选择{{ isTrainMode ? '车次' : isFlightMode ? '航班' : '交通' }}，再选择酒店
      </span>
      <span v-else-if="selection.needs_flight && isTransportBooking">
        请选择{{ isTrainMode ? '火车/高铁车次' : isFlightMode ? '航班' : '交通方式' }}
      </span>
      <span v-else-if="selection.needs_hotel">请选择酒店</span>
      <span v-else>请直接点击勾选 · 完成选择后确认预订</span>
    </div>

    <section
      v-if="isTransportBooking && isDriveMode"
      class="picker-section drive-section"
    >
      <div class="drive-card">
        <strong>自驾出行</strong>
        <p class="drive-desc">
          {{ legLabel }}从 {{ routeOrigin || '出发地' }} 至 {{ routeDestination || '目的地' }}，
          无需预订机票/车票，确认后将记录本段行程。
        </p>
      </div>
    </section>

    <section
      v-if="selection.needs_flight && isTrainMode && (selection.trains?.length ?? 0) > 0"
      class="picker-section"
    >
      <h4 class="section-title">{{ legLabel }} · 火车/高铁（{{ selection.trains?.length }} 个备选）</h4>
      <div class="option-list">
        <label
          v-for="(train, idx) in selection.trains"
          :key="train.train_no"
          class="option-card"
          :class="{ selected: selectedTrainNo === train.train_no, disabled: !isPending }"
        >
          <input
            type="radio"
            class="option-checkbox"
            name="train-option"
            :value="train.train_no"
            :checked="selectedTrainNo === train.train_no"
            :disabled="!isPending"
            @change="selectTrain(train)"
          />
          <span class="checkbox-box" aria-hidden="true">
            <span v-if="selectedTrainNo === train.train_no" class="check-mark">✓</span>
          </span>
          <div class="option-body" @click.prevent="selectTrain(train)">
            <div class="option-head">
              <span class="option-title">{{ train.train_no }}</span>
              <span v-if="idx === 0" class="tag-recommend">推荐</span>
              <span class="option-sub">{{ train.train_type }}</span>
              <span class="option-price">{{ train.price }} 元</span>
            </div>
            <div class="option-detail">
              {{ train.origin }} → {{ train.destination }}
            </div>
            <div class="option-detail muted">
              {{ formatTime(train.departure_time) }} 出发 ·
              {{ formatTime(train.arrival_time) }} 到达 · {{ train.seat_class }}
            </div>
          </div>
        </label>
      </div>
    </section>

    <section
      v-if="selection.needs_flight && isFlightMode && selection.flights.length"
      class="picker-section"
    >
      <h4 class="section-title">{{ legLabel }} · 航班（{{ selection.flights.length }} 个备选）</h4>
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

    <section
      v-if="selection.needs_hotel && selection.hotels.length"
      class="picker-section"
      :class="{ 'section-locked': !hotelSelectionEnabled }"
    >
      <h4 class="section-title">
        酒店选项（{{ selection.hotels.length }} 个备选）
        <span v-if="selection.needs_flight && !hotelSelectionEnabled" class="section-hint">
          请先完成上方交通选择
        </span>
      </h4>
      <div class="option-list">
        <label
          v-for="(hotel, idx) in selection.hotels"
          :key="hotel.name"
          class="option-card"
          :class="{
            selected: selectedHotelName === hotel.name,
            disabled: !isPending || !hotelSelectionEnabled,
          }"
        >
          <input
            type="radio"
            class="option-checkbox"
            name="hotel-option"
            :value="hotel.name"
            :checked="selectedHotelName === hotel.name"
            :disabled="!isPending || !hotelSelectionEnabled"
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
        {{ submitting ? '提交中…' : leg === 'return' ? '确认返程预订' : needsReturn ? '确认去程，继续选返程' : '确认预订' }}
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

.leg-card {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid #bfdbfe;
  border-left: 4px solid #2563eb;
  border-radius: var(--radius-sm);
  background: #eff6ff;
}

.leg-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.leg-badge {
  font-size: 12px;
  font-weight: 700;
  color: #1d4ed8;
  padding: 2px 8px;
  border-radius: 999px;
  background: #dbeafe;
}

.leg-step {
  font-size: 11px;
  color: #475569;
}

.route-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.route-label {
  font-size: 12px;
  font-weight: 600;
  color: #1d4ed8;
}

.route-value {
  font-size: 14px;
  font-weight: 600;
  color: #1e3a8a;
}

.route-date {
  margin-top: 4px;
  font-size: 12px;
  color: #334155;
}

.mode-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
}

.mode-label {
  font-size: 12px;
  font-weight: 600;
  color: #1d4ed8;
  white-space: nowrap;
}

.mode-select {
  flex: 1;
  max-width: 160px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid #93c5fd;
  border-radius: 6px;
  background: #fff;
  font-size: 13px;
  color: #1e3a8a;
}

.drive-section {
  margin-top: 0;
}

.drive-card {
  padding: 12px;
  border: 1px dashed #93c5fd;
  border-radius: var(--radius-sm);
  background: #fff;
}

.drive-card strong {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: #1e3a8a;
}

.drive-desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #475569;
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

.section-hint {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.picker-section.section-locked .option-card:not(.selected) {
  opacity: 0.55;
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
