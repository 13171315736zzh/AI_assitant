<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useChatStore } from '@/stores/useChatStore'
import SessionSidebar from '@/components/chat/SessionSidebar.vue'
import ChatTopbar from '@/components/chat/ChatTopbar.vue'
import MessageList from '@/components/chat/MessageList.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import TicketModal from '@/components/chat/TicketModal.vue'
import TaskDetailPanel from '@/components/chat/TaskDetailPanel.vue'
import BusinessFormPanel from '@/components/chat/BusinessFormPanel.vue'

const chat = useChatStore()
const showTicket = ref(false)
const activeTaskId = ref<string | null>(null)
const activeFormId = ref<string | null>(null)

onMounted(() => {
  chat.loadSessions()
})

async function handleEndSession() {
  if (!chat.activeSession || chat.activeSession.status === 'ended') {
    alert('当前没有进行中的会话')
    return
  }
  if (confirm('确认结束当前会话？结束后将无法继续发送消息。')) {
    await chat.endCurrentSession()
  }
}

async function handleClearMemory() {
  if (confirm('确认清除所有长期记忆？此操作不可撤销。')) {
    await chat.clearUserMemory()
  }
}

function openTask(taskId: string) {
  if (!taskId) return
  activeFormId.value = null
  activeTaskId.value = taskId
}

function openForm(formId: string) {
  activeTaskId.value = null
  activeFormId.value = formId
}

function closePanels() {
  activeTaskId.value = null
  activeFormId.value = null
}
</script>

<template>
  <div class="app-shell chat-page">
    <SessionSidebar
      :sessions="chat.sessions"
      :active-id="chat.activeSessionId"
      :loading="chat.loading"
      @select="chat.loadMessages"
      @new-session="chat.newSession"
      @end-session="handleEndSession"
    />

    <section class="main">
      <ChatTopbar
        @ticket="showTicket = true"
        @clear-memory="handleClearMemory"
      />

      <MessageList
        :messages="chat.messages"
        @open-task="openTask"
      />

      <ChatInput
        :disabled="chat.isActiveSessionEnded"
        :sending="chat.sending"
        @send="chat.send"
      />
    </section>

    <TaskDetailPanel
      v-if="activeTaskId"
      :task-id="activeTaskId"
      @close="closePanels"
      @open-form="openForm"
    />

    <BusinessFormPanel
      v-if="activeFormId"
      :form-id="activeFormId"
      @close="closePanels"
    />

    <TicketModal v-if="showTicket" @close="showTicket = false" />
  </div>
</template>

<style scoped>
.chat-page {
  flex-direction: row;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}
</style>
