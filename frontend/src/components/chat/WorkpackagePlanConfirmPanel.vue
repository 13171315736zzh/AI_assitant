<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { WorkpackagePlanConfirmMeta } from '@/types'

const props = defineProps<{
  confirm: WorkpackagePlanConfirmMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: { project?: string }]
}>()

const selectedProject = ref<string | null>(props.confirm.selected_project)

watch(
  () => props.confirm.selected_project,
  (value) => {
    selectedProject.value = value
  },
)

const isPending = computed(() => props.confirm.status === 'pending')
const projectOptions = computed(() => props.confirm.project_options ?? [])
const needsProjectPick = computed(
  () => isPending.value && projectOptions.value.length > 1 && !props.confirm.selected_project,
)
const canConfirm = computed(() => {
  if (!isPending.value || props.submitting) return false
  const project = selectedProject.value ?? props.confirm.selected_project
  if (needsProjectPick.value && !project) return false
  if ((props.confirm.requires_project || projectOptions.value.length === 0) && !project) {
    return false
  }
  return true
})

function selectProject(project: string) {
  if (!isPending.value) return
  selectedProject.value = project
}

function handleConfirm() {
  if (!canConfirm.value) return
  emit('confirm', {
    project: selectedProject.value ?? props.confirm.selected_project ?? undefined,
  })
}
</script>

<template>
  <div class="plan-confirm" :class="{ confirmed: !isPending }">
    <h4 class="section-title">{{ confirm.title }}</h4>
    <dl class="info-list">
      <div v-for="(item, i) in confirm.items" :key="i" class="info-row">
        <dt>{{ item.label }}</dt>
        <dd>{{ item.value }}</dd>
      </div>
    </dl>

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

.project-section {
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
