<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'
import { fetchTask, submitEmailSent } from '@/services/taskService'
import { buildOaNotifyPayload, notifyAssistantOaUpdate } from '@/utils/oaDemo'
import { fetchForm } from '@/services/formService'
import {
  buildMailSentPath,
  composeFullBody,
  findEmailFormId,
  loadMailDraft,
  loadMailPrefill,
  saveMailDraft,
  saveSentMail,
  type EmailComposeFields,
  type SentMailRecord,
} from '@/utils/emailMail'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const loading = ref(true)
const error = ref<string | null>(null)
const toast = ref<string | null>(null)
const saving = ref(false)
const sending = ref(false)

const taskId = computed(() => String(route.params.taskId ?? ''))
const formId = ref<string | null>(null)
const sessionId = ref<string | null>(null)

const recipient = ref('')
const cc = ref('')
const subject = ref('')
const body = ref('')
const signature = ref('')

const fromName = computed(() => auth.user?.display_name ?? '用户')
const fromEmail = computed(() => {
  const name = (auth.user?.display_name ?? 'user').toLowerCase()
  return `${name}@ceic.com`
})

function showToast(message: string) {
  toast.value = message
  window.setTimeout(() => {
    toast.value = null
  }, 2600)
}

function applyFields(fields: Partial<EmailComposeFields>) {
  recipient.value = fields.recipient ?? recipient.value
  cc.value = fields.cc ?? cc.value
  subject.value = fields.subject ?? subject.value
  body.value = fields.body ?? body.value
  signature.value = fields.signature ?? signature.value
}

function splitBodyAndSignature(fullBody: string, fallbackSignature: string): { body: string; signature: string } {
  const text = fullBody.trim()
  if (!text) return { body: '', signature: fallbackSignature }
  const lines = text.split('\n')
  const lastLine = lines[lines.length - 1]?.trim() ?? ''
  if (fallbackSignature && lastLine === fallbackSignature.trim()) {
    return {
      body: lines.slice(0, -1).join('\n').trim(),
      signature: fallbackSignature,
    }
  }
  return { body: text, signature: fallbackSignature }
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const prefill = loadMailPrefill(taskId.value)
    const draft = loadMailDraft(taskId.value)
    if (prefill) {
      formId.value = prefill.form_id ?? null
      sessionId.value = prefill.session_id ?? null
      applyFields(prefill)
    }
    if (draft) {
      applyFields(draft)
    }

    const taskRes = await fetchTask(taskId.value)
    if (taskRes.code !== 200 || !taskRes.data) {
      if (!prefill && !draft) {
        error.value = taskRes.message || '任务不存在'
      }
      return
    }
    sessionId.value = taskRes.data.session_id

    const emailFormId = findEmailFormId(taskRes.data)
    if (emailFormId) {
      formId.value = emailFormId
      const formRes = await fetchForm(emailFormId)
      if (formRes.code === 200 && formRes.data) {
        const fields = formRes.data.fields
        const prefillSign = prefill?.signature ?? signature.value
        const split = splitBodyAndSignature(fields.body ?? '', prefillSign)
        applyFields({
          recipient: fields.to ?? recipient.value,
          cc: fields.cc ?? cc.value,
          subject: fields.subject ?? subject.value,
          body: split.body || body.value,
          signature: split.signature || prefillSign,
        })
      }
    }
  } catch {
    if (!recipient.value && !subject.value) {
      error.value = '加载失败，请返回助手重试'
    }
  } finally {
    loading.value = false
  }
}

function currentFields(): EmailComposeFields {
  return {
    task_id: taskId.value,
    session_id: sessionId.value ?? undefined,
    form_id: formId.value ?? undefined,
    recipient: recipient.value.trim(),
    cc: cc.value.trim(),
    subject: subject.value.trim(),
    body: body.value.trim(),
    signature: signature.value.trim(),
  }
}

function handleSaveDraft() {
  if (saving.value) return
  saving.value = true
  saveMailDraft(taskId.value, currentFields())
  showToast('草稿已保存')
  saving.value = false
}

async function handleSend() {
  if (sending.value) return
  if (!recipient.value.trim()) {
    showToast('请填写收件人')
    return
  }
  if (!subject.value.trim()) {
    showToast('请填写邮件标题')
    return
  }
  sending.value = true
  const messageId = `mail_${Date.now()}`
  const fields = currentFields()
  const record: SentMailRecord = {
    ...fields,
    message_id: messageId,
    sent_at: new Date().toISOString(),
    from_name: fromName.value,
    from_email: fromEmail.value,
    body: composeFullBody(body.value, signature.value),
  }

  try {
    const res = await submitEmailSent(taskId.value, {
      recipient: fields.recipient,
      subject: fields.subject,
      message_id: messageId,
    })
    if (res.code !== 200) {
      showToast(res.message || '同步发送状态失败')
      sending.value = false
      return
    }
    saveSentMail(record)
    const sid = res.data.session_id || sessionId.value
    if (sid && res.data) {
      notifyAssistantOaUpdate(buildOaNotifyPayload(res.data, taskId.value, 'completed'))
    }
    showToast('邮件发送成功')
    window.setTimeout(() => {
      router.push(buildMailSentPath(messageId))
    }, 500)
  } catch {
    showToast('发送失败，请稍后重试')
    sending.value = false
  }
}

function closePage() {
  window.close()
}

onMounted(load)
</script>

<template>
  <div class="mail-shell">
    <header class="mail-topbar">
      <div class="brand">
        <span class="logo outlook-logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none">
            <path
              d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v11A2.5 2.5 0 0 1 17.5 20h-11A2.5 2.5 0 0 1 4 17.5v-11Z"
              fill="#fff"
              fill-opacity="0.95"
            />
            <path
              d="M6.5 7.5 12 11.2l5.5-3.7"
              stroke="#0078D4"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path
              d="M6.5 16.5V8.8L12 12.5l5.5-3.7v7.4"
              stroke="#0078D4"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </span>
        <div>
          <div class="brand-title">Outlook</div>
          <div class="brand-sub">演示环境 · 在线撰写</div>
        </div>
      </div>
      <div class="topbar-user">
        <span>{{ fromName }}</span>
        <span class="email">{{ fromEmail }}</span>
      </div>
    </header>

    <nav class="mail-nav">
      <span class="nav-item active">写信</span>
      <span class="nav-item muted">收信</span>
      <span class="nav-item muted">通讯录</span>
      <span class="nav-item muted">草稿箱</span>
    </nav>

    <main class="mail-main">
      <div v-if="loading" class="state">正在加载邮件内容…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else>
        <div class="toolbar">
          <button type="button" class="btn-primary" :disabled="sending" @click="handleSend">
            {{ sending ? '发送中…' : '发送' }}
          </button>
          <button type="button" class="btn-secondary" :disabled="saving" @click="handleSaveDraft">
            存草稿
          </button>
          <button type="button" class="btn-secondary" @click="closePage">关闭</button>
          <span class="toolbar-hint">数据已从智能办公助手确认卡片同步 · 发送后将通知助手</span>
        </div>

        <section class="compose-card">
          <div class="field-row">
            <label class="field-label">收件人</label>
            <input v-model="recipient" type="text" class="field-input" placeholder="收件人邮箱或姓名">
          </div>
          <div class="field-row">
            <label class="field-label">抄　送</label>
            <input v-model="cc" type="text" class="field-input" placeholder="抄送人，多人用分号分隔">
          </div>
          <div class="field-row">
            <label class="field-label">主　题</label>
            <input v-model="subject" type="text" class="field-input" placeholder="邮件主题">
          </div>

          <div class="editor-wrap">
            <textarea
              v-model="body"
              class="editor"
              placeholder="请输入正文内容…"
            />
          </div>

          <div class="field-row signature-row">
            <label class="field-label">落　款</label>
            <input v-model="signature" type="text" class="field-input" placeholder="部门姓名">
          </div>
        </section>
      </template>
    </main>

    <Transition name="toast">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.mail-shell {
  min-height: 100vh;
  background: #f5f6f8;
  color: #333;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.mail-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  background: linear-gradient(90deg, #0078d4 0%, #005a9e 100%);
  color: #fff;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  width: 42px;
  height: 42px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
}

.outlook-logo svg {
  display: block;
}

.brand-title {
  font-size: 18px;
  font-weight: 700;
}

.brand-sub {
  font-size: 12px;
  opacity: 0.85;
}

.topbar-user {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-size: 13px;
}

.email {
  opacity: 0.85;
  font-size: 12px;
}

.mail-nav {
  display: flex;
  gap: 20px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.nav-item {
  padding: 12px 2px;
  font-size: 14px;
  cursor: default;
}

.nav-item.active {
  color: #0078d4;
  font-weight: 600;
  border-bottom: 2px solid #0078d4;
}

.nav-item.muted {
  color: #999;
}

.mail-main {
  max-width: 980px;
  margin: 0 auto;
  padding: 20px 24px 40px;
}

.state {
  padding: 48px 0;
  text-align: center;
  color: #666;
}

.state.error {
  color: #0078d4;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.btn-primary,
.btn-secondary {
  height: 34px;
  padding: 0 16px;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
}

.btn-primary {
  border: none;
  background: #0078d4;
  color: #fff;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  border: 1px solid #d9d9d9;
  background: #fff;
  color: #333;
}

.toolbar-hint {
  margin-left: auto;
  font-size: 12px;
  color: #999;
}

.compose-card {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.field-row {
  display: grid;
  grid-template-columns: 72px 1fr;
  align-items: center;
  border-bottom: 1px solid #f0f0f0;
}

.field-label {
  padding: 0 16px;
  font-size: 13px;
  color: #888;
}

.field-input {
  width: 100%;
  height: 44px;
  border: none;
  outline: none;
  font-size: 14px;
  padding: 0 12px 0 0;
  background: transparent;
}

.editor-wrap {
  min-height: 320px;
  border-bottom: 1px solid #f0f0f0;
}

.editor {
  width: 100%;
  min-height: 320px;
  border: none;
  outline: none;
  resize: vertical;
  padding: 16px;
  font-size: 14px;
  line-height: 1.7;
  font-family: inherit;
}

.signature-row .field-input {
  height: 48px;
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 32px;
  transform: translateX(-50%);
  padding: 10px 18px;
  background: rgba(0, 0, 0, 0.78);
  color: #fff;
  border-radius: 6px;
  font-size: 13px;
  z-index: 100;
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
}
</style>
