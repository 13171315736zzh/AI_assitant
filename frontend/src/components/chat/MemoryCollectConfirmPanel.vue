<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { GENDER_OPTIONS, normalizeGender } from '@/constants/gender'
import {
  normalizeEmployeeId,
  normalizeIdNumber,
  validateMemoryStructuredFields,
} from '@/constants/memoryFieldValidation'
import { TRAVEL_MODE_PREFERENCE_OPTIONS } from '@/constants/travelModePreference'
import type { InfoCollectPlanConfirmMeta } from '@/types'
import type { MemoryStructured } from '@/mocks/settings'

const props = defineProps<{
  confirm: InfoCollectPlanConfirmMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: { structured: MemoryStructured }]
  'update-draft': [payload: { structured: MemoryStructured }]
}>()

const structuredFields: Array<{
  key: keyof MemoryStructured
  label: string
  placeholder?: string
  options?: readonly string[]
}> = [
  { key: 'display_name', label: '姓名', placeholder: '如：张明' },
  { key: 'gender', label: '性别', options: GENDER_OPTIONS },
  { key: 'id_number', label: '身份证号', placeholder: '18 位身份证号' },
  { key: 'employee_id', label: '工号', placeholder: '字母或数字，最多 9 位' },
  { key: 'job_role', label: '岗位', placeholder: '如：产品经理 / 前端 / 后端' },
  { key: 'position', label: '岗位类型', options: ['管理岗', '非管理岗'] as const },
  { key: 'base_location', label: '常驻地（Base）', placeholder: '如：北京' },
  { key: 'department', label: '部门', placeholder: '如：智能矿山事业部' },
  { key: 'email', label: '邮箱', placeholder: 'name@company.com' },
  {
    key: 'travel_mode_preference',
    label: '交通偏好',
    options: TRAVEL_MODE_PREFERENCE_OPTIONS,
  },
]

function emptyStructured(): MemoryStructured {
  return {
    display_name: '',
    gender: '男',
    id_number: '',
    employee_id: '',
    job_role: '',
    position: '',
    base_location: '',
    department: '',
    email: '',
    travel_mode_preference: '',
    related_projects: [],
  }
}

function normalizeStructured(raw: Record<string, unknown> | undefined): MemoryStructured {
  const base = emptyStructured()
  if (!raw) return base
  return {
    ...base,
    display_name: String(raw.display_name ?? ''),
    gender: normalizeGender(String(raw.gender ?? '')),
    id_number: String(raw.id_number ?? ''),
    employee_id: String(raw.employee_id ?? ''),
    job_role: String(raw.job_role ?? ''),
    position: String(raw.position ?? ''),
    base_location: String(raw.base_location ?? ''),
    department: String(raw.department ?? ''),
    email: String(raw.email ?? ''),
    travel_mode_preference: String(raw.travel_mode_preference ?? ''),
    related_projects: Array.isArray(raw.related_projects)
      ? raw.related_projects.map((item) => String(item))
      : [],
  }
}

const structured = ref<MemoryStructured>(normalizeStructured(props.confirm.structured))

const projectsText = computed({
  get: () => structured.value.related_projects.join('、'),
  set: (value: string) => {
    structured.value.related_projects = value
      .split(/[,，、]/)
      .map((item) => item.trim())
      .filter(Boolean)
  },
})

watch(
  () => props.confirm,
  (value) => {
    structured.value = normalizeStructured(value.structured as Record<string, unknown> | undefined)
    fieldErrors.value = { ...(value.field_errors ?? {}) }
  },
  { deep: true },
)

watch(
  structured,
  (value) => {
    emit('update-draft', { structured: { ...value } })
  },
  { deep: true },
)

const fieldErrors = ref<Record<string, string>>({})

function validateFields(): boolean {
  const normalized = {
    ...structured.value,
    id_number: normalizeIdNumber(structured.value.id_number),
    employee_id: normalizeEmployeeId(structured.value.employee_id),
  }
  structured.value.id_number = normalized.id_number
  structured.value.employee_id = normalized.employee_id
  fieldErrors.value = validateMemoryStructuredFields(normalized)
  return Object.keys(fieldErrors.value).length === 0
}

function clearFieldError(key: string) {
  if (fieldErrors.value[key]) {
    const next = { ...fieldErrors.value }
    delete next[key]
    fieldErrors.value = next
  }
}

const hasAnyValue = computed(() => {
  const s = structured.value
  return Boolean(
    s.display_name.trim()
    || s.id_number.trim()
    || s.employee_id.trim()
    || s.job_role.trim()
    || s.position.trim()
    || s.base_location.trim()
    || s.department.trim()
    || s.email.trim()
    || s.travel_mode_preference.trim()
    || s.related_projects.length,
  )
})

const isPending = computed(() => props.confirm.status === 'pending')

const hasFieldErrors = computed(() => Object.keys(fieldErrors.value).length > 0)

const canConfirm = computed(
  () => isPending.value && !props.submitting && hasAnyValue.value && !hasFieldErrors.value,
)

function handleConfirm() {
  if (!canConfirm.value) return
  if (!validateFields()) return
  emit('confirm', {
    structured: {
      ...structured.value,
      gender: normalizeGender(structured.value.gender),
      id_number: normalizeIdNumber(structured.value.id_number),
      employee_id: normalizeEmployeeId(structured.value.employee_id),
    },
  })
}
</script>

<template>
  <div class="plan-confirm" :class="{ confirmed: !isPending }">
    <h4 class="section-title">{{ confirm.title }}</h4>
    <p class="hint">以下信息将写入长期记忆，办理业务时自动参考，无需重复填写。</p>

    <p v-if="isPending && hasFieldErrors" class="form-error-banner">
      请修正下方标红字段后再确认保存。
    </p>

    <div v-if="isPending" class="fields">
      <div
        v-for="field in structuredFields"
        :key="field.key"
        class="field-row"
        :class="{ 'has-error': fieldErrors[field.key] }"
      >
        <span class="field-key">{{ field.label }}</span>
        <div class="field-col">
          <select
            v-if="field.options"
            v-model="structured[field.key]"
            class="field-input field-select"
            :class="{ invalid: fieldErrors[field.key] }"
            :disabled="submitting"
            @change="clearFieldError(field.key)"
          >
            <option value="">请选择</option>
            <option v-for="opt in field.options" :key="opt" :value="opt">
              {{ opt }}
            </option>
          </select>
          <input
            v-else
            v-model="structured[field.key]"
            type="text"
            class="field-input"
            :class="{ invalid: fieldErrors[field.key] }"
            :placeholder="field.placeholder"
            :maxlength="field.key === 'id_number' ? 18 : field.key === 'employee_id' ? 9 : undefined"
            :disabled="submitting"
            @input="clearFieldError(field.key)"
          />
          <p v-if="fieldErrors[field.key]" class="field-error">{{ fieldErrors[field.key] }}</p>
        </div>
      </div>
      <div class="field-row">
        <span class="field-key">关联项目</span>
        <input
          v-model="projectsText"
          type="text"
          class="field-input"
          placeholder="多个项目用顿号或逗号分隔"
          :disabled="submitting"
        />
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
        :disabled="!canConfirm"
        @click="handleConfirm"
      >
        {{ submitting ? '保存中…' : '确认保存到长期记忆' }}
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
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 600;
}

.hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.form-error-banner {
  margin: 0 0 12px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, #e5484d 10%, var(--surface));
  border: 1px solid color-mix(in srgb, #e5484d 35%, var(--border));
  color: #c62828;
  font-size: 12px;
  line-height: 1.5;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.field-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.field-col {
  flex: 1;
  min-width: 0;
}

.field-error {
  margin: 4px 0 0;
  font-size: 12px;
  color: #d14343;
}

.field-input.invalid {
  border-color: #d14343;
}

.field-key {
  width: 108px;
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

.field-select {
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
  grid-template-columns: 108px 1fr;
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
