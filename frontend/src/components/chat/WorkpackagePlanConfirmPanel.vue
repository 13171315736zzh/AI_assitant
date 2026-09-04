<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { WorkpackagePlanConfirmMeta } from '@/types'

const props = defineProps<{
  confirm: WorkpackagePlanConfirmMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: {
    project?: string
    all_days_eight_hours?: boolean
    hours_per_day?: number
  }]
  'update-draft': [payload: {
    project?: string
    all_days_eight_hours?: boolean | null
    hours_per_day?: number | null
  }]
}>()

const selectedProject = ref<string | null>(props.confirm.selected_project ?? null)
const projectInput = ref(props.confirm.selected_project ?? '')
const allDaysEightHours = ref<boolean | null>(
  props.confirm.hours_confirmed ? (props.confirm.all_days_eight_hours ?? true) : null,
)
const selectedHours = ref<number | null>(
  props.confirm.hours_confirmed && props.confirm.all_days_eight_hours === false
    ? (props.confirm.hours_per_day ?? null)
    : null,
)

watch(
  () => props.confirm.selected_project,
  (value) => {
    selectedProject.value = value ?? null
    if (value) projectInput.value = value
  },
)

watch(
  () => props.confirm.hours_confirmed,
  (confirmed) => {
    if (confirmed) {
      allDaysEightHours.value = props.confirm.all_days_eight_hours ?? true
      if (props.confirm.all_days_eight_hours === false) {
        selectedHours.value = props.confirm.hours_per_day ?? null
      }
    }
  },
)

const isPending = computed(() => props.confirm.status === 'pending')
const projectOptions = computed(() => props.confirm.project_options ?? [])
const needsProjectPick = computed(
  () => isPending.value && projectOptions.value.length > 1 && !props.confirm.selected_project,
)
const needsHoursConfirm = computed(
  () => isPending.value && !props.confirm.hours_confirmed,
)
const hourPresets = computed(() => props.confirm.hour_presets ?? [
  { label: '4 小时/天', value: 4 },
  { label: '6 小时/天', value: 6 },
  { label: '10 小时/天', value: 10 },
])
const hoursQuestion = computed(
  () => props.confirm.hours_question ?? '请确认上述日期中每天填报8小时（没有请假）',
)

const canConfirm = computed(() => {
  if (!isPending.value || props.submitting) return false
  const project = projectInput.value.trim()
    || selectedProject.value
    || props.confirm.selected_project
  if (needsProjectPick.value && !project) return false
  if ((props.confirm.requires_project || projectOptions.value.length === 0) && !project) {
    return false
  }
  if (needsHoursConfirm.value) {
    if (allDaysEightHours.value === null) return false
    if (allDaysEightHours.value === false && selectedHours.value == null) return false
  }
  return true
})

function selectProject(project: string) {
  if (!isPending.value) return
  selectedProject.value = project
  projectInput.value = project
}

function onProjectInput() {
  if (!isPending.value) return
  const value = projectInput.value.trim()
  if (value && projectOptions.value.length && !projectOptions.value.includes(value)) {
    selectedProject.value = null
  } else if (value && projectOptions.value.includes(value)) {
    selectedProject.value = value
  }
}

function selectEightHours(yes: boolean) {
  if (!isPending.value) return
  allDaysEightHours.value = yes
  if (yes) {
    selectedHours.value = null
  }
}

function selectHourPreset(value: number) {
  if (!isPending.value) return
  selectedHours.value = value
}

function handleConfirm() {
  if (!canConfirm.value) return
  const payload: {
    project?: string
    all_days_eight_hours?: boolean
    hours_per_day?: number
  } = {
    project: projectInput.value.trim()
      || selectedProject.value
      || props.confirm.selected_project
      || undefined,
  }
  if (needsHoursConfirm.value || allDaysEightHours.value !== null) {
    payload.all_days_eight_hours = allDaysEightHours.value ?? true
    if (payload.all_days_eight_hours === false) {
      payload.hours_per_day = selectedHours.value ?? undefined
    }
  }
  emit('confirm', payload)
}

function emitDraft() {
  if (!isPending.value) return
  emit('update-draft', {
    project: projectInput.value.trim()
      || selectedProject.value
      || props.confirm.selected_project
      || undefined,
    all_days_eight_hours: allDaysEightHours.value,
    hours_per_day: selectedHours.value,
  })
}

watch([selectedProject, projectInput, allDaysEightHours, selectedHours], emitDraft, { immediate: true })
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

    <dl v-if="isPending" class="info-list inferred">
      <div
        v-for="(item, i) in confirm.items.filter((row) => row.label !== '项目')"
        :key="i"
        class="info-row"
      >
        <dt>{{ item.label }}</dt>
        <dd>{{ item.value }}</dd>
      </div>
    </dl>

    <div v-if="isPending" class="fields">
      <div class="field-row">
        <span class="field-key">项目</span>
        <input
          v-model="projectInput"
          type="text"
          class="field-input"
          placeholder="输入项目名称，或从下方点选"
          :disabled="submitting"
          @input="onProjectInput"
        />
      </div>
    </div>

    <section v-if="needsProjectPick" class="project-section">
      <div class="picker-banner">
        <span class="picker-banner-icon" aria-hidden="true">☑</span>
        <span>请选择本次填报的项目</span>
      </div>
      <div class="option-list">
        <button
          v-for="project in projectOptions"
          :key="project"
          type="button"
          class="option-card"
          :class="{ selected: selectedProject === project }"
          @click="selectProject(project)"
        >
          <span class="checkbox-box" aria-hidden="true">
            <span v-if="selectedProject === project" class="check-mark">✓</span>
          </span>
          <span class="option-title">{{ project }}</span>
        </button>
      </div>
    </section>

    <section v-if="needsHoursConfirm" class="hours-section">
      <div class="picker-banner">
        <span class="picker-banner-icon" aria-hidden="true">⏱</span>
        <span>{{ hoursQuestion }}</span>
      </div>
      <div class="hours-choice">
        <button
          type="button"
          class="choice-btn"
          :class="{ selected: allDaysEightHours === true }"
          @click="selectEightHours(true)"
        >
          是
        </button>
        <button
          type="button"
          class="choice-btn"
          :class="{ selected: allDaysEightHours === false }"
          @click="selectEightHours(false)"
        >
          否
        </button>
      </div>
      <div v-if="allDaysEightHours === false" class="hour-presets">
        <span class="preset-label">请选择每日工时：</span>
        <div class="preset-list">
          <button
            v-for="preset in hourPresets"
            :key="preset.value"
            type="button"
            class="preset-chip"
            :class="{ selected: selectedHours === preset.value }"
            @click="selectHourPreset(preset.value)"
          >
            {{ preset.label }}
          </button>
        </div>
      </div>
    </section>

    <div v-if="isPending" class="confirm-footer">
      <button
        type="button"
        class="btn-confirm"
        :disabled="!canConfirm"
        @click="handleConfirm"
      >
        {{ submitting ? '处理中…' : '确认开始办理' }}
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

.inferred {
  margin-bottom: 10px;
}

.info-list {
  margin: 0 0 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
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

.field-key {
  width: 88px;
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-secondary);
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

.project-section,
.hours-section {
  margin-bottom: 12px;
}

.picker-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding: 8px 10px;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--surface);
  border-radius: var(--radius-sm);
}

.option-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-card {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  text-align: left;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.option-card.selected {
  border-color: var(--primary);
  background: color-mix(in srgb, var(--primary) 8%, var(--surface));
}

.checkbox-box {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: 1.5px solid var(--border);
  border-radius: 4px;
  flex-shrink: 0;
}

.option-card.selected .checkbox-box {
  border-color: var(--primary);
  background: var(--primary);
}

.check-mark {
  color: #fff;
  font-size: 12px;
  line-height: 1;
}

.option-title {
  font-size: 13px;
  font-weight: 500;
}

.hours-choice {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 8px;
}

.choice-btn {
  padding: 10px 12px;
  font-size: 13px;
  text-align: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.choice-btn.selected {
  border-color: var(--primary);
  background: color-mix(in srgb, var(--primary) 8%, var(--surface));
  color: var(--primary);
  font-weight: 500;
}

.hour-presets {
  padding: 8px 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.preset-label {
  display: block;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.preset-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preset-chip {
  padding: 6px 12px;
  font-size: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  cursor: pointer;
}

.preset-chip.selected {
  border-color: var(--primary);
  background: color-mix(in srgb, var(--primary) 10%, var(--bg));
  color: var(--primary);
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
