<script setup lang="ts">
import type { RoomBookingResultMeta } from '@/types'

defineProps<{
  result: RoomBookingResultMeta
}>()
</script>

<template>
  <div class="result-card room">
    <h4 class="result-title">会议室预约已完成</h4>
    <dl class="info-list">
      <div class="info-row">
        <dt>会议室</dt>
        <dd>{{ result.room_name }}</dd>
      </div>
      <div class="info-row">
        <dt>会议主题</dt>
        <dd>{{ result.subject }}</dd>
      </div>
      <div class="info-row">
        <dt>使用时间</dt>
        <dd>{{ result.time_label || `${result.start_time} — ${result.end_time}` }}</dd>
      </div>
      <div class="info-row">
        <dt>参会人员</dt>
        <dd>{{ result.attendees }}</dd>
      </div>
    </dl>
  </div>
</template>

<style scoped>
.result-card {
  margin-top: 12px;
  padding: 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
}

.result-card.room {
  border-color: color-mix(in srgb, #059669 35%, var(--border));
  background: color-mix(in srgb, #059669 5%, var(--surface));
}

.result-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
}

.info-list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-row {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 8px;
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
</style>
