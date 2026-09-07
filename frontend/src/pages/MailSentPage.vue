<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  buildMailComposePath,
  canRecallSentMail,
  loadSentMail,
  markSentMailRecalled,
  saveMailPrefill,
  type SentMailRecord,
} from '@/utils/emailMail'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const error = ref<string | null>(null)
const toast = ref<string | null>(null)
const mail = ref<SentMailRecord | null>(null)

const messageId = computed(() => String(route.params.messageId ?? ''))

const sentTimeLabel = computed(() => {
  if (!mail.value?.sent_at) return '—'
  return new Date(mail.value.sent_at).toLocaleString('zh-CN')
})

const recallAvailable = computed(() => {
  if (!mail.value || mail.value.recalled) return false
  return canRecallSentMail(mail.value.sent_at)
})

function showToast(message: string) {
  toast.value = message
  window.setTimeout(() => {
    toast.value = null
  }, 2600)
}

function load() {
  loading.value = true
  error.value = null
  const record = loadSentMail(messageId.value)
  if (!record) {
    error.value = '未找到已发送邮件记录'
    loading.value = false
    return
  }
  mail.value = record
  loading.value = false
}

function handleRecall() {
  if (!mail.value || !recallAvailable.value) return
  markSentMailRecalled(messageId.value)
  mail.value = { ...mail.value, recalled: true }
  showToast('邮件已撤回（演示）')
}

function handleEditAgain() {
  if (!mail.value) return
  const bodyText = mail.value.body
  const signature = mail.value.signature || ''
  let bodyOnly = bodyText
  if (signature && bodyText.endsWith(signature)) {
    bodyOnly = bodyText.slice(0, bodyText.length - signature.length).trim()
  }
  saveMailPrefill(mail.value.task_id, {
    task_id: mail.value.task_id,
    form_id: mail.value.form_id,
    recipient: mail.value.recipient,
    cc: mail.value.cc,
    subject: mail.value.subject,
    body: bodyOnly,
    signature,
  })
  router.push(buildMailComposePath(mail.value.task_id))
}

function backToChat() {
  window.close()
  router.push('/chat')
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
          <div class="brand-sub">演示环境 · 已发送</div>
        </div>
      </div>
    </header>

    <nav class="mail-nav">
      <span class="nav-item muted">写信</span>
      <span class="nav-item active">已发送</span>
      <span class="nav-item muted">草稿箱</span>
    </nav>

    <main class="mail-main">
      <div v-if="loading" class="state">正在加载…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else-if="mail">
        <div class="toolbar">
          <button
            type="button"
            class="btn-secondary"
            :disabled="!recallAvailable"
            @click="handleRecall"
          >
            {{ mail.recalled ? '已撤回' : '撤回' }}
          </button>
          <button type="button" class="btn-secondary" @click="handleEditAgain">
            再次编辑
          </button>
          <button type="button" class="btn-secondary" @click="backToChat">
            返回助手
          </button>
          <span v-if="recallAvailable" class="toolbar-hint">发送后 2 分钟内可撤回（演示）</span>
        </div>

        <article class="mail-view" :class="{ recalled: mail.recalled }">
          <header class="mail-head">
            <h1>{{ mail.subject || '（无主题）' }}</h1>
            <div v-if="mail.recalled" class="recalled-badge">已撤回</div>
          </header>

          <dl class="meta-list">
            <div class="meta-row">
              <dt>发件人</dt>
              <dd>{{ mail.from_name }} &lt;{{ mail.from_email }}&gt;</dd>
            </div>
            <div class="meta-row">
              <dt>收件人</dt>
              <dd>{{ mail.recipient || '—' }}</dd>
            </div>
            <div v-if="mail.cc" class="meta-row">
              <dt>抄　送</dt>
              <dd>{{ mail.cc }}</dd>
            </div>
            <div class="meta-row">
              <dt>时　间</dt>
              <dd>{{ sentTimeLabel }}</dd>
            </div>
          </dl>

          <div class="mail-body">{{ mail.body }}</div>
        </article>
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

.btn-secondary {
  height: 34px;
  padding: 0 16px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
}

.btn-secondary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.toolbar-hint {
  margin-left: auto;
  font-size: 12px;
  color: #999;
}

.mail-view {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 20px 24px 28px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.mail-view.recalled {
  opacity: 0.72;
}

.mail-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.mail-head h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.recalled-badge {
  padding: 2px 8px;
  border-radius: 4px;
  background: #eff6fc;
  color: #0078d4;
  font-size: 12px;
}

.meta-list {
  margin: 0 0 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.meta-row {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 8px;
  font-size: 13px;
  line-height: 1.8;
}

.meta-row dt {
  color: #888;
}

.meta-row dd {
  margin: 0;
  color: #333;
}

.mail-body {
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.8;
  color: #333;
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
