<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { FormData } from '@/services/formService'
import { formFieldLabels } from '@/mocks/forms'
import { fetchForm, confirmForm, submitForm, fetchReceipt } from '@/services/formService'
import type { FormReceipt } from '@/mocks/forms'

const props = defineProps<{ formId: string }>()

const emit = defineEmits<{ close: [] }>()

const form = ref<FormData | null>(null)
const fields = ref<Record<string, string>>({})
const loading = ref(false)
const step = ref<'preview' | 'confirm' | 'receipt'>('preview')
const receipt = ref<FormReceipt | null>(null)

const fieldLabels = computed(() =>
  form.value ? formFieldLabels[form.value.form_type] ?? {} : {},
)

const stepIndex = computed(() => {
  if (step.value === 'preview') return 0
  if (step.value === 'confirm') return 1
  return 2
})

async function load() {
  loading.value = true
  try {
    const res = await fetchForm(props.formId)
    if (res.code === 200) {
      form.value = res.data
      fields.value = { ...res.data.fields }
      if (res.data.status === 'submitted') {
        step.value = 'receipt'
        const r = await fetchReceipt(props.formId)
        if (r.code === 200) receipt.value = r.data
      } else if (res.data.status === 'confirmed') {
        step.value = 'confirm'
      } else {
        step.value = 'preview'
      }
    }
  } finally {
    loading.value = false
  }
}

watch(() => props.formId, load, { immediate: true })

async function goConfirm() {
  const res = await confirmForm(props.formId)
  if (res.code === 200) step.value = 'confirm'
}

async function goSubmit() {
  const res = await submitForm(props.formId, fields.value)
  if (res.code === 200) {
    step.value = 'receipt'
    receipt.value = {
      receipt_id: res.data.receipt_id,
      status: res.data.status,
      summary: res.data.message,
      submitted_at: new Date().toISOString(),
    }
  }
}

function goBackEdit() {
  step.value = 'preview'
}
</script>

<template>
  <aside class="form-panel">
    <header class="panel-header">
      <h2>{{ form?.title ?? '业务表单' }}</h2>
      <button type="button" class="btn-close" aria-label="关闭" @click="emit('close')">×</button>
    </header>

    <div class="steps">
      <span :class="{ active: stepIndex >= 0 }">预览</span>
      <span class="sep">→</span>
      <span :class="{ active: stepIndex >= 1 }">确认</span>
      <span class="sep">→</span>
      <span :class="{ active: stepIndex >= 2 }">回执</span>
    </div>

    <div v-if="loading" class="loading">加载中…</div>

    <div v-else-if="form" class="panel-body">
      <!-- 预览 / 编辑 -->
      <template v-if="step === 'preview'">
        <div class="fields">
          <div v-for="(_value, key) in fields" :key="key" class="field">
            <label>{{ fieldLabels[key] ?? key }}</label>
            <input v-model="fields[key]" type="text" />
          </div>
        </div>
        <div v-if="form.form_type === 'email'" class="warn">
          发送邮件为不可逆操作，请确认收件人和内容无误
        </div>
      </template>

      <!-- 确认 -->
      <template v-else-if="step === 'confirm'">
        <p class="confirm-hint">请确认以下信息无误后提交</p>
        <div class="preview-card">
          <div v-for="(value, key) in fields" :key="key" class="preview-row">
            <span class="label">{{ fieldLabels[key] ?? key }}</span>
            <span>{{ value }}</span>
          </div>
        </div>
      </template>

      <!-- 回执 -->
      <template v-else>
        <div class="receipt-card">
          <div class="receipt-icon">✓</div>
          <h3>提交成功</h3>
          <p>回执号 {{ receipt?.receipt_id }}</p>
          <p class="summary">{{ receipt?.summary }}</p>
        </div>
      </template>
    </div>

    <footer v-if="form && !loading" class="panel-footer">
      <template v-if="step === 'preview'">
        <button type="button" class="btn-secondary" @click="emit('close')">取消</button>
        <button type="button" class="btn-primary" @click="goConfirm">提交确认</button>
      </template>
      <template v-else-if="step === 'confirm'">
        <button type="button" class="btn-secondary" @click="goBackEdit">返回修改</button>
        <button type="button" class="btn-primary" @click="goSubmit">
          {{ form.form_type === 'email' ? '确认发送' : '确认提交' }}
        </button>
      </template>
      <template v-else>
        <button type="button" class="btn-primary full" @click="emit('close')">关闭</button>
      </template>
    </footer>
  </aside>
</template>

<style scoped>
.form-panel {
  width: 560px;
  flex-shrink: 0;
  background: var(--surface);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.panel-header h2 {
  font-size: 18px;
  font-weight: 600;
}

.btn-close {
  border: none;
  background: none;
  font-size: 24px;
  color: var(--text-muted);
  cursor: pointer;
}

.steps {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  font-size: 13px;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
}

.steps .active {
  color: var(--primary);
  font-weight: 600;
}

.sep {
  color: var(--border);
}

.loading {
  padding: 32px;
  text-align: center;
  color: var(--text-muted);
}

.panel-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-size: 13px;
  color: var(--text-secondary);
}

.field input,
.field textarea {
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 14px;
}

.warn {
  margin-top: 16px;
  padding: 12px;
  background: #fdf2f2;
  border: 1px solid #f5c6c6;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--primary);
}

.confirm-hint {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 16px;
}

.preview-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-row {
  display: flex;
  gap: 12px;
  font-size: 14px;
}

.preview-row .label {
  width: 80px;
  flex-shrink: 0;
  color: var(--text-secondary);
}

.receipt-card {
  text-align: center;
  padding: 32px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.receipt-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #edfaf5;
  color: var(--success);
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.receipt-card h3 {
  font-size: 18px;
  color: var(--success);
}

.summary {
  font-size: 14px;
  color: var(--text-secondary);
}

.panel-footer {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
}

.panel-footer .btn-primary,
.panel-footer .btn-secondary {
  flex: 1;
}

.panel-footer .full {
  width: 100%;
}
</style>
