<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TimesheetEntry, WorkpackageConfirmMeta } from '@/types'

const props = defineProps<{
  confirm: WorkpackageConfirmMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: { entries: TimesheetEntry[] }]
}>()

const localEntries = ref<TimesheetEntry[]>([])

watch(
  () => props.confirm.entries,
  (entries) => {
    localEntries.value = entries.map((entry) => ({
      ...entry,
      hours: entry.hours ?? props.confirm.hours_per_day ?? 8,
      selected: entry.selected ?? true,
    }))
  },
  { immediate: true },
)

const isPending = computed(() => props.confirm.status === 'pending')
const selectedCount = computed(
  () => localEntries.value.filter((entry) => entry.selected).length,
)
const totalHours = computed(() =>
  localEntries.value
    .filter((entry) => entry.selected)
    .reduce((sum, entry) => sum + entry.hours, 0),
)

function toggleEntry(index: number) {
  if (!isPending.value) return
  const entry = localEntries.value[index]
  if (!entry) return
  entry.selected = !entry.selected
}

function handleConfirm() {
  if (!isPending.value || props.submitting || selectedCount.value === 0) return
  emit('confirm', { entries: localEntries.value })
}
</script>

<template>
  <div class="wp-confirm" :class="{ confirmed: !isPending }">
    <section v-if="confirm.skipped_days?.length" class="skipped-section">
      <h4 class="section-title">已跳过（假期/非工作日）</h4>
      <ul class="skipped-list">
        <li v-for="(item, i) in confirm.skipped_days" :key="i">
          {{ item.day_label || item.day_date }} · {{ item.reason }}
        </li>
      </ul>
    </section>

    <section v-if="confirm.conflicts.length" class="conflict-section">
      <h4 class="section-title">冲突提示</h4>
      <ul class="conflict-list">
        <li v-for="(c, i) in confirm.conflicts" :key="i">
          <strong>{{ c.day_label }}</strong>{{ c.period }}已使用
          <strong>{{ c.existing_project }}</strong> 完成 {{ c.hours ?? 4 }} 小时填报
        </li>
      </ul>
    </section>

    <section class="plan-section">
      <h4 class="section-title">
        填报计划（{{ confirm.project }} · {{ confirm.period_label }}）
      </h4>
      <p class="plan-hint">每日默认 {{ confirm.hours_per_day ?? 8 }} 小时，请勾选需要填报的日期：</p>
      <div v-if="localEntries.length" class="entry-list">
        <button
          v-for="(entry, i) in localEntries"
          :key="`${entry.day_date}-${entry.period}`"
          type="button"
          class="entry-row"
          :class="{ selected: entry.selected, disabled: !isPending }"
          :disabled="!isPending"
          @click="toggleEntry(i)"
        >
          <span class="checkbox-box" aria-hidden="true">
            <span v-if="entry.selected" class="check-mark">✓</span>
          </span>
          <span class="entry-day">{{ entry.day_label }}</span>
          <span class="entry-date">{{ entry.day_date }}</span>
          <span class="entry-period">{{ entry.period }}</span>
          <span class="entry-hours">{{ entry.hours }} 小时</span>
        </button>
      </div>
      <p v-else class="empty-plan">暂无可分配明细。</p>
    </section>

    <div v-if="isPending" class="confirm-footer">
      <p class="confirm-hint">
        已选 <strong>{{ selectedCount }}</strong> 天，合计
        <strong>{{ totalHours }}</strong> 小时
        <template v-if="confirm.total_hours">（计划 {{ confirm.total_hours }} 小时）</template>
        ，确认后将生成填报表单。
      </p>
      <button
        type="button"
        class="btn-confirm"
        :disabled="submitting || selectedCount === 0"
        @click="handleConfirm"
      >
        {{ submitting ? '提交中…' : '确认填报' }}
      </button>
    </div>
    <p v-else class="confirmed-hint">填报计划已确认，正在继续办理。</p>
  </div>
</template>

<style scoped>
.wp-confirm {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.conflict-section {
  margin-bottom: 14px;
  padding: 10px 12px;
  background: #fff8f0;
  border: 1px solid #f0dcc8;
  border-radius: var(--radius-sm);
}

.skipped-section {
  margin-bottom: 14px;
  padding: 10px 12px;
  background: #f5f8ff;
  border: 1px solid #d8e0f0;
  border-radius: var(--radius-sm);
}

.skipped-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-secondary);
}

.section-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
}

.plan-hint {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--text-secondary);
}

.conflict-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-secondary);
}

.plan-section {
  margin-bottom: 12px;
}

.empty-plan {
  margin: 0;
  padding: 10px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--surface);
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
}

.entry-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.entry-row {
  display: grid;
  grid-template-columns: 24px 40px 1fr 56px 72px;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.entry-row.selected {
  border-color: var(--primary);
  background: color-mix(in srgb, var(--primary) 8%, var(--surface));
}

.entry-row.disabled {
  cursor: default;
}

.checkbox-box {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: 1.5px solid var(--border);
  border-radius: 4px;
}

.entry-row.selected .checkbox-box {
  border-color: var(--primary);
  background: var(--primary);
}

.check-mark {
  color: #fff;
  font-size: 12px;
  line-height: 1;
}

.entry-day {
  font-weight: 600;
}

.entry-date {
  color: var(--text-secondary);
}

.entry-period {
  color: var(--text-secondary);
}

.entry-hours {
  text-align: right;
  color: var(--primary);
  font-weight: 500;
}

.confirm-footer {
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.confirm-hint {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
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
