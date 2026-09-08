<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { GENDER_OPTIONS, normalizeGender } from '@/constants/gender'
import {
  normalizeEmployeeId,
  normalizeIdNumber,
  validateMemoryStructuredFields,
} from '@/constants/memoryFieldValidation'
import { TRAVEL_MODE_PREFERENCE_OPTIONS } from '@/constants/travelModePreference'
import { filterExtensionMemoryItems } from '@/constants/coreMemoryFields'
import type { MemoryItem, MemoryStructured } from '@/services/settingsService'
import { invalidateMemoryProfileCache } from '@/composables/useMemoryProfile'
import { clearUserMemory, fetchMemory, updateMemory } from '@/services/settingsService'

const memoryEnabled = ref(true)
const structured = ref<MemoryStructured>(emptyStructured())
const memoryItems = ref<MemoryItem[]>([])
const fieldCount = ref(0)
const loading = ref(true)
const saving = ref(false)
const clearing = ref(false)
const fieldErrors = ref<Record<string, string>>({})

const displayMemoryItems = computed(() => filterExtensionMemoryItems(memoryItems.value))

function clearFieldError(key: string) {
  if (fieldErrors.value[key]) {
    const next = { ...fieldErrors.value }
    delete next[key]
    fieldErrors.value = next
  }
}

function validateBeforeSave(): boolean {
  structured.value.id_number = normalizeIdNumber(structured.value.id_number)
  structured.value.employee_id = normalizeEmployeeId(structured.value.employee_id)
  fieldErrors.value = validateMemoryStructuredFields(structured.value)
  return Object.keys(fieldErrors.value).length === 0
}

const projectsText = computed({
  get: () => structured.value.related_projects.join('、'),
  set: (value: string) => {
    structured.value.related_projects = value
      .split(/[,，、]/)
      .map((item) => item.trim())
      .filter(Boolean)
  },
})

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
  { key: 'position', label: '岗位类型', placeholder: '管理岗 / 非管理岗' },
  { key: 'base_location', label: '常驻地（Base）', placeholder: '如：北京' },
  { key: 'department', label: '部门', placeholder: '如：智能矿山事业部' },
  { key: 'email', label: '邮箱', placeholder: 'name@company.com' },
  {
    key: 'travel_mode_preference',
    label: '交通偏好',
    options: TRAVEL_MODE_PREFERENCE_OPTIONS,
  },
]

async function load() {
  loading.value = true
  try {
    const res = await fetchMemory()
    if (res.code === 200) {
      memoryEnabled.value = res.data.memory_enabled
      structured.value = {
        ...emptyStructured(),
        ...res.data.structured,
        gender: normalizeGender(res.data.structured?.gender),
        related_projects: [...(res.data.structured.related_projects ?? [])],
      }
      memoryItems.value = filterExtensionMemoryItems(
        res.data.memory_items.map((item) => ({ ...item })),
      )
      fieldCount.value = res.data.field_count ?? memoryItems.value.length
    }
  } finally {
    loading.value = false
  }
}

function addMemoryItem() {
  memoryItems.value.push({ key: '', value: '' })
}

function removeMemoryItem(index: number) {
  memoryItems.value.splice(index, 1)
}

async function save() {
  if (!validateBeforeSave()) return
  saving.value = true
  try {
    const res = await updateMemory({
      memory_enabled: memoryEnabled.value,
      structured: structured.value,
      memory_items: filterExtensionMemoryItems(
        memoryItems.value.filter((item) => item.key.trim() && item.value.trim()),
      ),
    })
    if (res.code === 200) {
      invalidateMemoryProfileCache()
      memoryEnabled.value = res.data.memory_enabled
      structured.value = {
        ...emptyStructured(),
        ...res.data.structured,
        gender: normalizeGender(res.data.structured?.gender),
        related_projects: [...(res.data.structured.related_projects ?? [])],
      }
      memoryItems.value = filterExtensionMemoryItems(
        res.data.memory_items.map((item) => ({ ...item })),
      )
      fieldCount.value = res.data.field_count ?? 0
      alert('长期记忆已保存')
    } else {
      alert(res.message || '保存失败')
    }
  } finally {
    saving.value = false
  }
}

async function handleClearMemory() {
  if (!confirm('确认清除所有长期记忆？此操作不可撤销。')) return
  clearing.value = true
  try {
    const res = await clearUserMemory()
    if (res.code === 200) {
      invalidateMemoryProfileCache()
      alert('长期记忆已清除')
      await load()
    } else {
      alert(res.message || '清除失败')
    }
  } finally {
    clearing.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-if="loading" class="loading">加载中…</div>
  <div v-else class="card">
    <div class="toggle-row">
      <span>启用长期记忆</span>
      <label class="switch">
        <input v-model="memoryEnabled" type="checkbox" />
        <span class="slider" />
      </label>
    </div>
    <p class="hint">
      开启后系统将从对话中自动提取并持久化您的个人信息与偏好（SQLite 存储，重启后端不会丢失）。
      当前约 {{ fieldCount }} 个记忆字段（上限 150）。
    </p>

    <template v-if="memoryEnabled">
      <div class="divider" />
      <h3>核心个人信息</h3>
      <p class="sub-hint">以下为结构化长期记忆，支持查看与手动编辑</p>

      <div class="fields">
        <div
          v-for="field in structuredFields"
          :key="field.key"
          class="field-row"
        >
          <span class="field-key">{{ field.label }}</span>
          <div class="field-col">
            <select
              v-if="field.options"
              v-model="structured[field.key]"
              class="field-input field-select"
              :class="{ invalid: fieldErrors[field.key] }"
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
          />
        </div>
      </div>

      <div class="divider" />
      <div class="section-head">
        <div>
          <h3>扩展记忆条目</h3>
          <p class="sub-hint">算法从对话中提取的其他重要信息（如常用联系人、沟通偏好等）</p>
        </div>
        <button type="button" class="btn-secondary" @click="addMemoryItem">+ 添加条目</button>
      </div>

      <div class="fields">
        <div v-for="(item, i) in displayMemoryItems" :key="i" class="field-row ext-row">
          <input v-model="item.key" type="text" class="field-input key-input" placeholder="字段名" />
          <input v-model="item.value" type="text" class="field-input" placeholder="字段值" />
          <button
            type="button"
            class="btn-remove"
            aria-label="删除"
            @click="removeMemoryItem(memoryItems.indexOf(item))"
          >×</button>
        </div>
        <p v-if="!displayMemoryItems.length" class="empty-hint">暂无扩展条目，对话后系统会自动提取。</p>
      </div>
    </template>

    <div class="footer">
      <button
        type="button"
        class="btn-danger"
        :disabled="clearing || saving"
        @click="handleClearMemory"
      >
        {{ clearing ? '清除中…' : '清除记忆' }}
      </button>
      <button type="button" class="btn-primary" :disabled="saving || clearing" @click="save">
        {{ saving ? '保存中…' : '保存修改' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.loading {
  color: var(--text-muted);
  font-size: 14px;
}

.card {
  width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 500;
}

.switch {
  position: relative;
  width: 44px;
  height: 24px;
  display: inline-block;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  inset: 0;
  background: var(--border);
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.slider::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  left: 4px;
  top: 4px;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.2s;
}

.switch input:checked + .slider {
  background: var(--primary);
}

.switch input:checked + .slider::before {
  transform: translateX(20px);
}

.hint,
.sub-hint,
.empty-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.divider {
  height: 1px;
  background: var(--border);
}

.card h3 {
  font-size: 16px;
  margin: 0;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
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

.ext-row {
  align-items: stretch;
}

.field-key {
  width: 120px;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.field-input {
  flex: 1;
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
}

.field-select {
  cursor: pointer;
}

.key-input {
  max-width: 180px;
}

.btn-secondary,
.btn-remove {
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.btn-secondary {
  height: 34px;
  padding: 0 12px;
  font-size: 12px;
  white-space: nowrap;
}

.btn-remove {
  width: 40px;
  height: 40px;
  font-size: 18px;
  line-height: 1;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

.btn-primary,
.btn-danger {
  height: 40px;
  padding: 0 20px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
}

.btn-primary {
  border: none;
  background: var(--primary);
  color: #fff;
}

.btn-primary:disabled,
.btn-danger:disabled {
  opacity: 0.6;
  cursor: default;
}

.btn-danger {
  border: 1px solid #f5c6c6;
  background: #fdf2f2;
  color: var(--primary);
}

.btn-danger:hover:not(:disabled) {
  background: #fce8e8;
}
</style>
