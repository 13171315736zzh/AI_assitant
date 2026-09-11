<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
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
import type { MessageSource, Session, WorkflowDrawerRequest, WorkflowPlanNode } from '@/types'
import {
  extractWorkflowPlan,
  findLatestMessageForNode,
  messageHasPendingInteractivePanel,
  openOaPageForNode,
  workflowPlanVisible,
} from '@/utils/workflowPlan'
import { filterDrawerItems } from '@/utils/taskOaStatus'

const chat = useChatStore()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const showTicket = ref(false)
const activeTaskId = ref<string | null>(null)
const pendingDrawer = ref<WorkflowDrawerRequest | null>(null)
const activeNodeId = ref<string | null>(null)
const dismissedNodeIds = ref<Set<string>>(new Set())
const drawerEpoch = ref(0)
const activeFormId = ref<string | null>(null)
const previewSource = ref<MessageSource | null>(null)
const deleteTarget = ref<Session | null>(null)
const deleting = ref(false)
const workflowRailExpanded = ref(false)
const userCollapsedRail = ref(false)
const messageListRef = ref<InstanceType<typeof MessageList> | null>(null)
const chatInputRef = ref<InstanceType<typeof ChatInput> | null>(null)

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
    const pendingNodeId = pendingDrawer.value?.nodeId
    if (!pendingNodeId || activeTaskId.value) return
    const node = plan?.nodes.find((item) => item.id === pendingNodeId)
    if (node?.task_id) {
      void openTask(node.task_id, pendingNodeId)
    }
  },
  { deep: true },
)

function toggleWorkflowRail() {
  workflowRailExpanded.value = !workflowRailExpanded.value
  userCollapsedRail.value = !workflowRailExpanded.value
}

function onGlobalKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && (activeTaskId.value || pendingDrawer.value || activeFormId.value)) {
    closePanels()
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onGlobalKeydown)
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

onUnmounted(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
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

const NODE_DRAWER_TITLE: Record<string, string> = {
  gn_meeting: '国能会议任务详情',
  room: '会议室预约任务详情',
  leave: '请假任务详情',
  travel: '差旅任务详情',
  workpackage: '工时任务详情',
  booking: '交通预订任务详情',
  hotel: '酒店预订任务详情',
  email: '邮件任务详情',
}

function drawerKey() {
  return [
    activeTaskId.value || pendingDrawer.value?.nodeId || 'none',
    activeNodeId.value || '',
    drawerEpoch.value,
  ].join(':')
}

function rememberDismissedNode(nodeId?: string | null) {
  if (!nodeId) return
  const next = new Set(dismissedNodeIds.value)
  next.add(nodeId)
  dismissedNodeIds.value = next
}

function clearDismissedNode(nodeId?: string | null) {
  if (!nodeId || !dismissedNodeIds.value.has(nodeId)) return
  const next = new Set(dismissedNodeIds.value)
  next.delete(nodeId)
  dismissedNodeIds.value = next
}

async function openTask(taskId: string, nodeId?: string | null) {
  if (!taskId) return
  const resolvedNodeId = nodeId
    || workflowPlan.value?.nodes.find((item) => item.task_id === taskId)?.id
    || null
  clearDismissedNode(resolvedNodeId)
  if (activeTaskId.value === taskId && !pendingDrawer.value && activeNodeId.value === resolvedNodeId) {
    return
  }
  activeFormId.value = null
  pendingDrawer.value = null
  activeTaskId.value = taskId
  activeNodeId.value = resolvedNodeId
  drawerEpoch.value += 1
}

function openWorkflowDrawer(request: WorkflowDrawerRequest) {
  const node = request.nodeId
    ? workflowPlan.value?.nodes.find((item) => item.id === request.nodeId)
    : undefined
  const taskId = request.taskId || node?.task_id || null
  if (request.force) {
    clearDismissedNode(request.nodeId || node?.id)
  } else if (!taskId && request.nodeId && dismissedNodeIds.value.has(request.nodeId)) {
    return
  }
  if (taskId) {
    void openTask(taskId, request.nodeId || node?.id)
    return
  }
  if (!request.nodeId && !request.items?.length) return
  const items = filterDrawerItems(
    request.items ?? pendingDrawer.value?.items ?? [],
    request.nodeId,
    request.title,
  )
  if (!activeTaskId.value && pendingDrawer.value?.nodeId === request.nodeId) {
    pendingDrawer.value = {
      ...pendingDrawer.value,
      title: request.title || pendingDrawer.value.title,
      items,
    }
    return
  }
  activeFormId.value = null
  activeTaskId.value = null
  activeNodeId.value = request.nodeId ?? null
  pendingDrawer.value = {
    nodeId: request.nodeId ?? '',
    title: request.title || NODE_DRAWER_TITLE[request.nodeId ?? ''] || '任务详情',
    items,
  }
  drawerEpoch.value += 1
}

function openForm(formId: string) {
  activeTaskId.value = null
  pendingDrawer.value = null
  activeNodeId.value = null
  activeFormId.value = formId
}

function closePanels() {
  rememberDismissedNode(activeNodeId.value || pendingDrawer.value?.nodeId)
  activeTaskId.value = null
  pendingDrawer.value = null
  activeNodeId.value = null
  activeFormId.value = null
  drawerEpoch.value += 1
}

async function confirmPendingFromDrawer() {
  const nodeId = activeNodeId.value || pendingDrawer.value?.nodeId
  if (!nodeId) return

  const planNode = workflowPlan.value?.nodes.find((item) => item.id === nodeId)
  if (planNode?.task_id) {
    await openTask(planNode.task_id, nodeId)
    if (!openOaPageForNode(planNode, planNode.task_id)) {
      alert('无法打开新窗口，请检查浏览器是否拦截弹窗。')
    }
    return
  }

  const target = findLatestMessageForNode(
    chat.displayMessages,
    planNode ?? { id: nodeId, label: nodeId, status: 'pending' },
  )
  if (!target || !messageHasPendingInteractivePanel(target, nodeId)) {
    alert('请先在对话中确认该事项信息')
    return
  }

  const roomSelection = target.metadata?.room_selection as { status?: string } | undefined
  if (nodeId === 'room' && roomSelection?.status === 'pending') {
    alert('请先在对话中选择会议室，再前往 OA 提交')
    return
  }

  if (nodeId === 'gn_meeting' || nodeId === 'room') {
    const draft = chat.getWorkflowCardDraft(target.id, 'meeting_plan_confirm') ?? {}
    await chat.confirmMeetingPlan({
      messageId: target.id,
      ...draft,
      confirm_node_id: nodeId,
    })
  } else if (nodeId === 'leave') {
    const draft = chat.getWorkflowCardDraft(target.id, 'leave_plan_confirm') ?? {}
    await chat.confirmLeavePlan({
      messageId: target.id,
      reason: String(draft.reason ?? ''),
      attachment_name: draft.attachment_name as string | undefined,
      leave_type: draft.leave_type as string | undefined,
      date_start: draft.date_start as string | undefined,
      date_end: draft.date_end as string | undefined,
      start_period: draft.start_period as string | undefined,
      end_period: draft.end_period as string | undefined,
    })
  } else if (nodeId === 'travel' || nodeId === 'email') {
    const draft = chat.getWorkflowCardDraft(target.id, 'travel_plan_confirm') ?? {}
    await chat.confirmTravelPlan({
      messageId: target.id,
      ...draft,
    })
  } else if (nodeId === 'workpackage') {
    const draft = chat.getWorkflowCardDraft(target.id, 'workpackage_plan_confirm') ?? {}
    await chat.confirmWorkpackagePlan({
      messageId: target.id,
      project: draft.project as string | undefined,
      all_days_eight_hours: draft.all_days_eight_hours as boolean | undefined,
      hours_per_day: draft.hours_per_day as number | undefined,
    })
  } else {
    alert('请先在对话中确认该事项信息')
    return
  }

  await nextTick()
  const nextNode = extractWorkflowPlan(chat.messages)?.nodes.find((item) => item.id === nodeId)
  if (nextNode?.task_id) {
    await openTask(nextNode.task_id, nodeId)
    if (!openOaPageForNode(nextNode, nextNode.task_id)) {
      alert('无法打开新窗口，请检查浏览器是否拦截弹窗。')
    }
    return
  }
  if (nodeId === 'room') {
    alert('请先在对话中选择会议室，再前往 OA 提交')
  }
}

function openSource(source: MessageSource) {
  previewSource.value = source
}

async function focusWorkflowNode(node: WorkflowPlanNode) {
  if (node.task_id) {
    await openTask(node.task_id)
  } else {
    const target = findLatestMessageForNode(chat.displayMessages, node)
    const items = (target?.metadata?.meeting_plan_confirm
      || target?.metadata?.leave_plan_confirm
      || target?.metadata?.travel_plan_confirm
      || target?.metadata?.workpackage_plan_confirm) as { items?: WorkflowDrawerRequest['items']; title?: string } | undefined
    openWorkflowDrawer({
      nodeId: node.id,
      title: NODE_DRAWER_TITLE[node.id] || `${node.label}任务详情`,
      items: filterDrawerItems(items?.items ?? [], node.id),
      force: true,
    })
  }

  const target = findLatestMessageForNode(chat.displayMessages, node)
  const hasPending = target
    ? messageHasPendingInteractivePanel(target, node.id)
    : false

  if (hasPending && target) {
    await messageListRef.value?.scrollToMessage(target.id, 'smooth', {
      highlightInteractive: true,
    })
    return
  }

  if (!node.task_id && (node.status === 'pending' || node.status === 'running')) {
    const assistantMsg = await chat.activateWorkflowNode(node.id)
    if (assistantMsg) {
      await nextTick()
      await messageListRef.value?.scrollToMessage(assistantMsg.id, 'smooth', {
        highlightInteractive: true,
      })
      return
    }
  }

  if (target) {
    await messageListRef.value?.scrollToMessage(target.id, 'smooth', {
      highlightInteractive: true,
      highlightOa: Boolean(node.task_id),
    })
    return
  }

  if (!node.task_id) {
    alert(`「${node.label}」暂无相关对话记录`)
  }
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
        :messages="chat.messages"
        @toggle="toggleWorkflowRail"
        @focus-node="focusWorkflowNode"
      />

      <MessageList
        ref="messageListRef"
        :messages="chat.displayMessages"
        :workflow-submitting="chat.workflowSubmitting"
        :quick-actions-disabled="chat.isActiveSessionEnded || chat.sending"
        :active-task-id="activeTaskId"
        @open-task="openTask"
        @open-drawer="openWorkflowDrawer"
        @open-source="openSource"
        @confirm-booking="chat.confirmBooking"
        @confirm-room="chat.confirmRoom"
        @confirm-workpackage="chat.confirmWorkpackage"
        @confirm-workpackage-plan="chat.confirmWorkpackagePlan"
        @confirm-travel-plan="chat.confirmTravelPlan"
        @confirm-meeting-plan="chat.confirmMeetingPlan"
        @confirm-leave-plan="chat.confirmLeavePlan"
        @confirm-info-collect-plan="chat.confirmInfoCollectPlan"
        @confirm-workflow-cancel="chat.confirmWorkflowCancel"
        @confirm-meeting-cancel-selection="chat.confirmMeetingCancelSelection"
        @update-card-draft="chat.setWorkflowCardDraft"
        @quick-start="(prompt) => chat.send(prompt, { useCardDraft: false })"
      />

      <ChatInput
        ref="chatInputRef"
        v-model="chat.activeInputDraft"
        :disabled="chat.isActiveSessionEnded"
        :sending="chat.sending"
        @send="chat.send"
      />
    </section>

    <TaskDetailPanel
      v-if="activeTaskId || pendingDrawer"
      :key="drawerKey()"
      :task-id="activeTaskId"
      :node-id="activeNodeId || pendingDrawer?.nodeId"
      :pending="pendingDrawer"
      @dismiss="closePanels"
      @open-form="openForm"
      @confirm-pending="confirmPendingFromDrawer"
      @bind-task="(taskId) => openTask(taskId, activeNodeId || pendingDrawer?.nodeId)"
      @cancel-requested="(messageId) => messageListRef?.scrollToMessage(messageId, 'smooth', { highlightInteractive: true })"
    />
    <div
      v-if="activeTaskId || pendingDrawer"
      class="drawer-spacer"
      aria-hidden="true"
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

.drawer-spacer {
  width: min(480px, 100%);
  flex-shrink: 0;
}
</style>
