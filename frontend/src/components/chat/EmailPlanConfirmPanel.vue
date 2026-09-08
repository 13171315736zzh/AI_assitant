<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { EmailPlanConfirmMeta } from '@/types'

const props = defineProps<{
  confirm: EmailPlanConfirmMeta
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [payload: {
    recipient?: string
    cc?: string
    subject?: string
    body?: string
    signature?: string
  }]
  'update-draft': [payload: Record<string, unknown>]
}>()

const recipient = ref(props.confirm.recipient ?? '')
const cc = ref(props.confirm.cc ?? '')
const subject = ref(props.confirm.subject ?? '')
const body = ref(props.confirm.body ?? '')
const signature = ref(props.confirm.signature ?? '')

watch(
  () => props.confirm,
  (value) => {
    recipient.value = value.recipient ?? ''
    cc.value = value.cc ?? ''
    subject.value = value.subject ?? ''
    body.value = value.body ?? ''
    signature.value = value.signature ?? ''
  },
  { deep: true, immediate: true },
)

const isPending = computed(() => props.confirm.status === 'pending')

const canConfirm = computed(() => {
  if (!isPending.value || props.submitting) return false
  return Boolean(recipient.value.trim() && subject.value.trim() && body.value.trim())
})

function buildDraftPayload() {
  return {
    recipient: recipient.value.trim(),
    cc: cc.value.trim(),
    subject: subject.value.trim(),
    body: body.value.trim(),
    signature: signature.value.trim(),
  }
}

function syncDraft() {
  if (!isPending.value) return
  emit('update-draft', buildDraftPayload())
}

watch([recipient, cc, subject, body, signature], syncDraft, { deep: true, immediate: true })

function handleConfirm() {
  if (!canConfirm.value) return
  emit('confirm', buildDraftPayload())
}
</script>

<template>
  <div class="plan-confirm" :class="{ confirmed: !isPending }">
    <h4 class="section-title">{{ confirm.title }}</h4>

    <dl v-if="isPending" class="info-list">
      <div class="info-row">
        <dt>收件人</dt>
        <dd>
          <input
            v-model="recipient"
            type="text"
            class="field-input"
            placeholder="姓名或邮箱"
            :disabled="submitting"
          />
        </dd>
      </div>

      <div class="info-row">
        <dt>抄送人</dt>
        <dd>
          <input
            v-model="cc"
            type="text"
            class="field-input"
            placeholder="可选，多人用顿号/逗号分隔"
            :disabled="submitting"
          />
        </dd>
      </div>

      <div class="info-row">
        <dt>标题</dt>
        <dd>
          <input
            v-model="subject"
            type="text"
            class="field-input"
            placeholder="邮件标题"
            :disabled="submitting"
          />
        </dd>
      </div>

      <div class="info-row info-row-top">
        <dt>正文</dt>
        <dd>
          <textarea
            v-model="body"
            class="field-textarea"
            rows="5"
            placeholder="邮件正文内容"
            :disabled="submitting"
          />
        </dd>
      </div>

      <div class="info-row">
        <dt>落款</dt>
        <dd>
          <input
            v-model="signature"
            type="text"
            class="field-input"
            placeholder="部门姓名"
            :disabled="submitting"
          />
        </dd>
      </div>
    </dl>

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
        {{ submitting ? '处理中…' : (confirm.confirm_label ?? '确认并开始写邮件') }}
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

.info-row-top {
  align-items: start;
}

.info-row-top dt {
  padding-top: 8px;
}

.info-row dt {
  color: var(--text-secondary);
}

.info-row dd {
  margin: 0;
  min-width: 0;
}

.field-input {
  width: 100%;
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
}

.field-textarea {
  width: 100%;
  min-height: 88px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
  font-family: inherit;
  resize: vertical;
  line-height: 1.5;
}

.field-input:disabled,
.field-textarea:disabled {
  opacity: 0.55;
  cursor: not-allowed;
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
