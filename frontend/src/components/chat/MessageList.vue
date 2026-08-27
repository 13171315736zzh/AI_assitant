<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import type { Message } from '@/types'

const props = defineProps<{
  messages: Message[]
}>()

const emit = defineEmits<{
  openTask: [taskId: string]
}>()

const containerRef = ref<HTMLElement | null>(null)
const bottomRef = ref<HTMLElement | null>(null)

async function scrollToLatest(behavior: ScrollBehavior = 'smooth') {
  await nextTick()
  bottomRef.value?.scrollIntoView({ behavior, block: 'end' })
}

watch(
  () =>
    [
      props.messages.length,
      props.messages[props.messages.length - 1]?.id,
      props.messages[props.messages.length - 1]?.content,
    ] as const,
  async ([len, lastId], prev) => {
    if (!len || !lastId) return
    const prevLen = prev?.[0] ?? 0
    const behavior: ScrollBehavior = prevLen === 0 ? 'instant' : 'smooth'
    await scrollToLatest(behavior)
  },
  { flush: 'post' },
)

onMounted(() => {
  if (props.messages.length) scrollToLatest('instant')
})

function taskMeta(msg: Message) {
  const m = msg.metadata ?? {}
  return {
    title: (m.task_title as string) ?? '任务进行中',
    progress: (m.progress as string) ?? '',
    percent: (m.progress_percent as number) ?? 50,
    stepsDesc: (m.steps_desc as string) ?? '',
    taskId: (m.task_id as string) ?? '',
  }
}

function sources(msg: Message) {
  const list = msg.metadata?.sources as Array<{ filename: string; clause: string }> | undefined
  return list ?? []
}
</script>

<template>
  <div ref="containerRef" class="messages">
    <div
      v-for="msg in messages"
      :key="msg.id"
      class="message-row"
      :class="msg.role"
    >
      <div class="bubble" :class="[msg.role, { pending: msg.message_type === 'pending' }]">
        {{ msg.content }}

        <div
          v-if="msg.message_type === 'task'"
          class="task-card"
          @click="emit('openTask', taskMeta(msg).taskId)"
        >
          <div class="task-card-header">
            <span class="task-card-title">{{ taskMeta(msg).title }}</span>
            <span class="task-card-progress">{{ taskMeta(msg).progress }} 步骤</span>
          </div>
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: `${taskMeta(msg).percent}%` }"
            />
          </div>
          <div class="task-card-desc">{{ taskMeta(msg).stepsDesc }}</div>
        </div>

        <div v-if="sources(msg).length" class="source-block">
          <div class="source-label">引用来源</div>
          <div v-for="(src, i) in sources(msg)" :key="i" class="source-item">
            《{{ src.filename }}》{{ src.clause }}
          </div>
        </div>
      </div>
    </div>
    <div ref="bottomRef" class="scroll-anchor" aria-hidden="true" />
  </div>
</template>

<style scoped>
.messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message-row {
  display: flex;
  max-width: 78%;
}

.message-row.user {
  align-self: flex-end;
  justify-content: flex-end;
}

.message-row.assistant {
  align-self: flex-start;
}

.bubble {
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  line-height: 1.6;
  border: 1px solid var(--border);
}

.bubble.user {
  background: var(--user-bubble-bg);
  border-color: var(--user-bubble-border);
}

.bubble.assistant {
  background: var(--surface);
  white-space: pre-line;
}

.bubble.pending {
  color: var(--text-secondary);
  border-style: dashed;
  white-space: pre-line;
}

.task-card {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: border-color 0.15s;
}

.task-card:hover {
  border-color: var(--primary);
}

.task-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.task-card-title {
  font-size: 13px;
  font-weight: 600;
}

.task-card-progress {
  font-size: 12px;
  color: var(--accent);
  font-weight: 500;
}

.progress-bar {
  height: 2px;
  background: #e2e5e9;
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 2px;
  transition: width 0.3s;
}

.task-card-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

.source-block {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.source-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.source-item {
  font-size: 12px;
  color: var(--primary);
}

.scroll-anchor {
  height: 1px;
  flex-shrink: 0;
}
</style>
