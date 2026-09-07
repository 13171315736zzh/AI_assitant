<script setup lang="ts">
import { computed, ref } from 'vue'
import type { GnMeetingResultMeta } from '@/types'

const props = defineProps<{
  result: GnMeetingResultMeta
}>()

const copiedAll = ref(false)

const subject = computed(() => props.result.subject?.trim() || '国能会议')

function formatMeetingNo(no: string): string {
  const digits = no.replace(/\D/g, '')
  if (digits.length === 9) {
    return `${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6)}`
  }
  return no
}

function buildCopyAllText(): string {
  const lines = [
    `会议名称：${subject.value}`,
    `会议号：${props.result.meeting_no}`,
    `会议链接：${props.result.meeting_link}`,
    `会议密码：${props.result.meeting_password}`,
  ]
  return lines.join('\n')
}

async function copyAll() {
  const text = buildCopyAllText()
  try {
    await navigator.clipboard.writeText(text)
    copiedAll.value = true
    window.setTimeout(() => {
      copiedAll.value = false
    }, 2000)
  } catch {
    window.prompt('请手动复制以下会议信息', text)
  }
}
</script>

<template>
  <div class="result-card gn">
    <h4 class="result-title">国能会议已创建</h4>

    <div class="invite-card">
      <p class="invite-subject">{{ subject }}</p>

      <div v-if="result.meeting_no" class="invite-row highlight">
        <span class="invite-label">会议号</span>
        <span class="invite-value meeting-no">{{ formatMeetingNo(result.meeting_no) }}</span>
      </div>

      <div class="invite-row">
        <span class="invite-label">会议链接</span>
        <a
          :href="result.meeting_link"
          target="_blank"
          rel="noopener noreferrer"
          class="invite-value link"
        >
          {{ result.meeting_link }}
        </a>
      </div>

      <div class="invite-row">
        <span class="invite-label">会议密码</span>
        <span class="invite-value mono">{{ result.meeting_password }}</span>
      </div>

      <button type="button" class="copy-all-btn" @click="copyAll">
        {{ copiedAll ? '已复制全部信息' : '复制全部信息' }}
      </button>
    </div>
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

.result-card.gn {
  border-color: color-mix(in srgb, var(--primary) 35%, var(--border));
  background: color-mix(in srgb, var(--primary) 6%, var(--surface));
}

.result-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
}

.invite-card {
  padding: 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg);
}

.invite-subject {
  margin: 0 0 14px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.4;
}

.invite-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 0;
  border-top: 1px solid var(--border);
}

.invite-row.highlight {
  padding-top: 0;
  border-top: none;
  padding-bottom: 12px;
}

.invite-label {
  font-size: 11px;
  color: var(--text-muted);
}

.invite-value {
  font-size: 13px;
  color: var(--text);
  word-break: break-all;
  line-height: 1.5;
}

.invite-value.meeting-no {
  font-size: 22px;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: 0.12em;
  color: var(--text);
}

.invite-value.link {
  color: var(--primary);
  text-decoration: none;
}

.invite-value.link:hover {
  text-decoration: underline;
}

.invite-value.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.copy-all-btn {
  width: 100%;
  height: 40px;
  margin-top: 14px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
}

.copy-all-btn:hover {
  opacity: 0.92;
}
</style>
