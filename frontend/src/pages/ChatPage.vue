<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/useAuthStore'
import { useChatStore } from '@/stores/useChatStore'
import SessionSidebar from '@/components/chat/SessionSidebar.vue'
import ChatTopbar from '@/components/chat/ChatTopbar.vue'
import MessageList from '@/components/chat/MessageList.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import TicketModal from '@/components/chat/TicketModal.vue'
import TaskDetailPanel from '@/components/chat/TaskDetailPanel.vue'
import DocumentPreviewModal from '@/components/chat/DocumentPreviewModal.vue'
import BusinessFormPanel from '@/components/chat/BusinessFormPanel.vue'
import ConfirmDialog from '@/components/chat/ConfirmDialog.vue'
import WorkflowPlanRail from '@/components/chat/WorkflowPlanRail.vue'
import type { MessageSource, Session, WorkflowPlanNode } from '@/types'
import { extractWorkflowPlan, findLatestMessageForNode, nodeActivationPrompt, workflowPlanVisible } from '@/utils/workflowPlan'

const chat = useChatStore()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const showTicket = ref(false)
const activeTaskId = ref<string | null>(null)
const activeFormId = ref<string | null>(null)
const previewSource = ref<MessageSource | null>(null)
const deleteTarget = ref<Session | null>(null)
const deleting = ref(false)
const workflowRailExpanded = ref(false)
const userCollapsedRail = ref(false)
const messageListRef = ref<InstanceType<typeof MessageList> | null>(null)

const workflowPlan = computed(() => extractWorkflowPlan(chat.messages))
const showWorkflowRail = computed(() => workflowPlanVisible(workflowPlan.value))

watch(
  () => chat.activeSessionId,
  () => {
    workflowRailExpanded.value = false
    userCollapsedRail.value = false
  },
)

watch(
  workflowPlan,
  (plan) => {
    if (!workflowPlanVisible(plan)) {
      workflowRailExpanded.value = false
      return
    }
    if (!userCollapsedRail.value) {
      workflowRailExpanded.value = true
    }
  },
  { deep: true },
)

function toggleWorkflowRail() {
  workflowRailExpanded.value = !workflowRailExpanded.value
  userCollapsedRail.value = !workflowRailExpanded.value
}

onMounted(async () => {
  await chat.loadSessions()
  const sessionQuery = route.query.session
  const taskQuery = route.query.task
  if (typeof sessionQuery === 'string' && sessionQuery) {
    await chat.loadMessages(sessionQuery)
    if (typeof taskQuery === 'string' && taskQuery) {
      activeTaskId.value = taskQuery
    }
    router.replace({ name: 'chat' })
  }
})

watch(
  () => auth.user?.id,
  (userId, prevId) => {
    if (userId && userId !== prevId) {
      chat.reset()
      chat.loadSessions()
    }
  },
)

async function handleEndSession() {
  if (!chat.activeSession || chat.activeSession.status === 'ended') {
    alert('当前没有进行中的会话')
    return
  }
  if (confirm('确认结束当前会话？结束后将无法继续发送消息。')) {
    await chat.endCurrentSession()
  }
}

function requestDeleteSession(sessionId: string) {
  deleteTarget.value = chat.sessions.find((s) => s.id === sessionId) ?? null
}

function cancelDeleteSession() {
  deleteTarget.value = null
}

async function confirmDeleteSession() {
  if (!deleteTarget.value || deleting.value) return
  deleting.value = true
  try {
    await chat.removeSession(deleteTarget.value.id)
    deleteTarget.value = null
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : '删除失败，请稍后重试'
    alert(message)
  } finally {
    deleting.value = false
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

function openSource(source: MessageSource) {
  previewSource.value = source
}

async function focusWorkflowNode(node: WorkflowPlanNode) {
  const target = findLatestMessageForNode(chat.displayMessages, node)
  if (target) {
    const ok = await messageListRef.value?.scrollToMessage(target.id)
    if (!ok) {
      alert(`暂未找到「${node.label}」相关对话`)
    }
    return
  }

  if (node.status === 'completed') {
    alert(`「${node.label}」已完成，暂未找到相关对话记录`)
    return
  }

  if (chat.isActiveSessionEnded || chat.sending) {
    return
  }

  await chat.send(nodeActivationPrompt(node.id, node.label))
}
</script>

<template>
  <div class="app-shell chat-page">
    <SessionSidebar
      :sessions="chat.sessions"
      :active-id="chat.activeSessionId"
      :loading="chat.loading"
      :deleting-session-id="chat.deletingSessionId"
      @select="chat.loadMessages"
      @new-session="chat.newSession"
      @end-session="handleEndSession"
      @delete-session="requestDeleteSession"
    />

    <section class="main">
      <ChatTopbar @ticket="showTicket = true" />

      <WorkflowPlanRail
        v-if="showWorkflowRail && workflowPlan"
        :plan="workflowPlan"
        :expanded="workflowRailExpanded"
        @toggle="toggleWorkflowRail"
        @focus-node="focusWorkflowNode"
      />

      <MessageList
        ref="messageListRef"
        :messages="chat.displayMessages"
        :workflow-submitting="chat.workflowSubmitting"
        :quick-actions-disabled="chat.isActiveSessionEnded || chat.sending"
        @open-task="openTask"
        @open-source="openSource"
        @confirm-booking="chat.confirmBooking"
        @confirm-room="chat.confirmRoom"
        @confirm-workpackage="chat.confirmWorkpackage"
        @confirm-workpackage-plan="chat.confirmWorkpackagePlan"
        @confirm-travel-plan="chat.confirmTravelPlan"
        @confirm-meeting-plan="chat.confirmMeetingPlan"
        @confirm-leave-plan="chat.confirmLeavePlan"
        @confirm-info-collect-plan="chat.confirmInfoCollectPlan"
        @update-card-draft="chat.setWorkflowCardDraft"
        @quick-start="chat.send"
      />

      <ChatInput
        v-model="chat.activeInputDraft"
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

    <TicketModal
      v-if="showTicket"
      :session-id="chat.activeSession?.id ?? null"
      @close="showTicket = false"
    />

    <DocumentPreviewModal
      :source="previewSource"
      @close="previewSource = null"
    />

    <ConfirmDialog
      v-if="deleteTarget"
      title="删除对话"
      :message="`确定要永久删除「${deleteTarget.title}」吗？删除后对话记录将无法恢复。`"
      confirm-text="确定删除"
      cancel-text="取消"
      danger
      :loading="deleting"
      @confirm="confirmDeleteSession"
      @cancel="cancelDeleteSession"
    />
  </div>
</template>

<style scoped>
.chat-page {
  flex-direction: row;
}

.main {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}
</style>
