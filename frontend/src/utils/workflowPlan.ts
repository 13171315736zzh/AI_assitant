import type { Message, WorkflowNodeStatus, WorkflowPlan, WorkflowPlanNode } from '@/types'

/** 与后端 workflow_plan._DISPLAY_ORDER 保持一致 */
export const WORKFLOW_NODE_DISPLAY_ORDER = [
  'gn_meeting',
  'email',
  'room',
  'travel',
  'booking',
  'hotel',
  'workpackage',
  'leave',
  'info_collect',
] as const

const NODE_DISPLAY_RANK = new Map<string, number>(
  WORKFLOW_NODE_DISPLAY_ORDER.map((id, index) => [id, index]),
)

const NODE_CONTENT_PATTERNS: Record<string, RegExp> = {
  gn_meeting: /国能会|国能会议|线上会议|视频会议/i,
  email: /写邮件|邮件|发信|发邮件|写信|email/i,
  room: /会议室|预约.*会议|订.*会议|预订会议|约.{0,12}会议|约.{0,8}会|帮我约/i,
  travel: /出差|差旅(?:申请|单)?|驻场|办公地点/i,
  booking: /订(?:机)?票|订车票|订机票|机票|航班|高铁|火车(?!站)/i,
  hotel: /酒店|住宿|订房|入住|住\s*[两二三四五六七八九十\d]+\s*天|住\s*\d+\s*晚/i,
  workpackage: /填工时|工时|工包|填报/i,
  leave: /请假|休假|补假/i,
  info_collect: /填信息|信息收集|信息采集|个人信息|完善资料|长期记忆/i,
}

const NODE_STATUS_RANK: Record<WorkflowNodeStatus, number> = {
  pending: 0,
  running: 1,
  submitted: 2,
  completed: 3,
  cancelled: 4,
}

function mergeNodeStatus(a: WorkflowNodeStatus, b: WorkflowNodeStatus): WorkflowNodeStatus {
  return NODE_STATUS_RANK[b] >= NODE_STATUS_RANK[a] ? b : a
}

function sortWorkflowNodes(nodes: WorkflowPlanNode[]): WorkflowPlanNode[] {
  return [...nodes].sort((a, b) => {
    const rankA = NODE_DISPLAY_RANK.get(a.id) ?? 999
    const rankB = NODE_DISPLAY_RANK.get(b.id) ?? 999
    return rankA - rankB
  })
}

function mergeWorkflowPlans(plans: WorkflowPlan[]): WorkflowPlan {
  const nodeMap = new Map<string, WorkflowPlanNode>()
  let activeNodeId: string | null = null

  for (const plan of plans) {
    if (plan.active_node_id) {
      activeNodeId = plan.active_node_id
    }
    for (const node of plan.nodes) {
      const existing = nodeMap.get(node.id)
      if (!existing) {
        nodeMap.set(node.id, { ...node })
        continue
      }
      nodeMap.set(node.id, {
        ...existing,
        status: mergeNodeStatus(existing.status, node.status),
        task_id: existing.task_id || node.task_id || null,
      })
    }
  }

  const orderedIds = sortWorkflowNodes(
    plans.flatMap((plan) => plan.nodes),
  ).map((node) => node.id)
  const uniqueIds = [...new Set(orderedIds)]
  const nodes = uniqueIds
    .map((id) => nodeMap.get(id))
    .filter((node): node is WorkflowPlanNode => Boolean(node))

  return {
    nodes: nodes.length ? nodes : sortWorkflowNodes(Array.from(nodeMap.values())),
    active_node_id: activeNodeId,
  }
}

/** 取消确认后立即将指定节点置灰（与后端 plan 合并，cancelled 优先）。 */
export function applyCancelledNodesToWorkflowPlan(
  messages: Message[],
  nodeIds: string[],
): Message[] {
  const plan = extractWorkflowPlan(messages)
  if (!plan?.nodes?.length || !nodeIds.length) return messages
  const cancelSet = new Set(nodeIds)
  const updatedPlan: WorkflowPlan = {
    ...plan,
    nodes: plan.nodes.map((node) => (
      cancelSet.has(node.id)
        ? { ...node, status: mergeNodeStatus(node.status, 'cancelled') }
        : node
    )),
  }
  return applyWorkflowPlanToMessages(messages, updatedPlan)
}

/** 将最新流程计划同步到本地消息，供右侧流程图即时更新。 */
export function applyWorkflowPlanToMessages(
  messages: Message[],
  plan: WorkflowPlan,
): Message[] {
  let touched = false
  const next = messages.map((msg) => {
    if (!msg.metadata?.workflow_plan) return msg
    touched = true
    return {
      ...msg,
      metadata: {
        ...msg.metadata,
        workflow_plan: plan,
      },
    }
  })
  if (touched) return next

  for (let index = next.length - 1; index >= 0; index -= 1) {
    const msg = next[index]
    if (msg.role !== 'assistant') continue
    const updated = [...next]
    updated[index] = {
      ...msg,
      metadata: {
        ...(msg.metadata ?? {}),
        workflow_plan: plan,
      },
    }
    return updated
  }
  return next
}

export function extractWorkflowPlan(messages: Message[]): WorkflowPlan | null {
  const plans: WorkflowPlan[] = []
  for (const msg of messages) {
    const raw = msg.metadata?.workflow_plan
    if (
      raw
      && typeof raw === 'object'
      && Array.isArray((raw as WorkflowPlan).nodes)
      && (raw as WorkflowPlan).nodes.length >= 2
    ) {
      plans.push(raw as WorkflowPlan)
    }
  }
  if (!plans.length) return null
  return mergeWorkflowPlans(plans)
}

export function workflowPlanVisible(plan: WorkflowPlan | null): boolean {
  return Boolean(plan && plan.nodes.length >= 2)
}

export function nodeStatusLabel(status: WorkflowNodeStatus): string {
  const map: Record<WorkflowNodeStatus, string> = {
    pending: '待开始',
    running: '进行中',
    submitted: '审批中',
    completed: '已完成',
    cancelled: '已取消',
  }
  return map[status]
}

export function nodeCanCancel(status: WorkflowNodeStatus): boolean {
  return status === 'running' || status === 'submitted'
}

export function nodeCanModify(status: WorkflowNodeStatus): boolean {
  return status === 'submitted' || status === 'completed'
}

const OA_PAGE_NODE_IDS = new Set([
  'travel',
  'booking',
  'hotel',
  'workpackage',
  'leave',
  'gn_meeting',
  'room',
])

export function nodeHasOaPage(nodeId: string): boolean {
  return OA_PAGE_NODE_IDS.has(nodeId)
}

export function openOaPageForNode(node: WorkflowPlanNode, taskId: string): boolean {
  if (!taskId) return false
  switch (node.id) {
    case 'travel':
      return Boolean(window.open(`/oa/travel/${encodeURIComponent(taskId)}`, '_blank', 'noopener,noreferrer'))
    case 'booking':
      return Boolean(window.open(`/oa/booking/transport/${encodeURIComponent(taskId)}`, '_blank', 'noopener,noreferrer'))
    case 'hotel':
      return Boolean(window.open(`/oa/booking/hotel/${encodeURIComponent(taskId)}`, '_blank', 'noopener,noreferrer'))
    case 'workpackage':
      return Boolean(window.open(`/oa/workpackage/${encodeURIComponent(taskId)}`, '_blank', 'noopener,noreferrer'))
    case 'leave':
      return Boolean(window.open(`/oa/leave/${encodeURIComponent(taskId)}`, '_blank', 'noopener,noreferrer'))
    case 'gn_meeting':
      return Boolean(window.open(`/oa/gn-meeting/${encodeURIComponent(taskId)}`, '_blank', 'noopener,noreferrer'))
    case 'room':
      return Boolean(window.open(`/oa/room-meeting/${encodeURIComponent(taskId)}`, '_blank', 'noopener,noreferrer'))
    default:
      return false
  }
}

function taskIdInMessage(msg: Message, taskId: string): boolean {
  const meta = msg.metadata ?? {}
  if (meta.task_id === taskId) return true
  if (meta.email_sent_result && meta.task_id === taskId) return true
  const related = meta.related_tasks as Array<{ task_id?: string }> | undefined
  return Array.isArray(related) && related.some((item) => item.task_id === taskId)
}

function messageMatchesWorkflowNode(
  msg: Message,
  nodeId: string,
  taskId?: string | null,
): boolean {
  if (msg.metadata?.is_welcome) return false
  if (taskId && taskIdInMessage(msg, taskId)) return true

  const meta = msg.metadata ?? {}
  const nextNode = meta.workflow_next_node as { node_id?: string | null } | undefined
  if (nextNode?.node_id === nodeId) return true

  switch (nodeId) {
    case 'email':
      if (hasWorkflowCancelMeta(msg, nodeId)) return true
      if (meta.email_compose) return true
      if (meta.email_sent_result) return true
      if (meta.category === 'email') return true
      if (Boolean((meta.travel_plan_confirm as { email_only?: boolean } | undefined)?.email_only)) {
        return true
      }
      if (msg.message_type === 'task' && String(meta.steps_desc ?? '').includes('邮件')) return true
      break
    case 'travel':
      if (hasWorkflowCancelMeta(msg, nodeId)) return true
      if (meta.travel_plan_confirm && !(meta.travel_plan_confirm as { email_only?: boolean }).email_only) {
        return true
      }
      if (msg.message_type === 'task' && /差旅|出差/.test(String(meta.steps_desc ?? meta.task_title ?? ''))) {
        return true
      }
      break
    case 'booking': {
      if (hasWorkflowCancelMeta(msg, nodeId)) return true
      const booking = meta.booking_selection as { needs_flight?: boolean; booking_kind?: string } | undefined
      if (booking?.needs_flight || booking?.booking_kind === 'transport') return true
      if (msg.message_type === 'task' && /交通|航班|机票|车票/.test(String(meta.steps_desc ?? ''))) return true
      break
    }
    case 'hotel': {
      if (hasWorkflowCancelMeta(msg, nodeId)) return true
      const booking = meta.booking_selection as { needs_hotel?: boolean; booking_kind?: string } | undefined
      if (booking?.needs_hotel || booking?.booking_kind === 'hotel') return true
      if (msg.message_type === 'task' && /酒店|住宿/.test(String(meta.steps_desc ?? ''))) return true
      break
    }
    case 'workpackage':
      if (hasWorkflowCancelMeta(msg, nodeId)) return true
      if (meta.workpackage_plan_confirm || meta.workpackage_confirm) return true
      if (msg.message_type === 'task' && /工时|工包/.test(String(meta.steps_desc ?? meta.task_title ?? ''))) {
        return true
      }
      break
    case 'leave':
      if (hasWorkflowCancelMeta(msg, nodeId)) return true
      if (meta.leave_plan_confirm) return true
      if (msg.message_type === 'task' && /请假/.test(String(meta.steps_desc ?? meta.task_title ?? ''))) return true
      break
    case 'room':
      if (hasWorkflowCancelMeta(msg, nodeId)) return true
      if (meta.room_selection || meta.room_booking_result) return true
      if ((meta.meeting_plan_confirm as { needs_room_booking?: boolean } | undefined)?.needs_room_booking) {
        return true
      }
      if (Array.isArray(meta.related_tasks) && meta.related_tasks.some(
        (item) => (item as { meeting_kind?: string }).meeting_kind === 'room',
      )) {
        return true
      }
      if (msg.message_type === 'task' && /会议室|会议预约/.test(String(meta.steps_desc ?? meta.task_title ?? ''))) {
        return true
      }
      break
    case 'gn_meeting':
      if (hasWorkflowCancelMeta(msg, nodeId)) return true
      if (meta.gn_meeting_result) return true
      if ((meta.meeting_plan_confirm as { needs_gn_meeting?: boolean } | undefined)?.needs_gn_meeting) {
        return true
      }
      if (Array.isArray(meta.related_tasks) && meta.related_tasks.some(
        (item) => (item as { meeting_kind?: string }).meeting_kind === 'gn',
      )) {
        return true
      }
      if (msg.message_type === 'task' && /国能会议|国能会/.test(String(meta.steps_desc ?? meta.task_title ?? ''))) {
        return true
      }
      break
    case 'info_collect':
      if (hasWorkflowCancelMeta(msg, nodeId)) return true
      if (meta.info_collect_plan_confirm) return true
      if (msg.message_type === 'task' && /信息收集|个人信息/.test(String(meta.steps_desc ?? ''))) return true
      break
    default:
      break
  }

  if (msg.role === 'user' && NODE_CONTENT_PATTERNS[nodeId]?.test(msg.content)) {
    return true
  }

  return false
}

/** 点击「下一办理节点」卡片时，等效于用户发送的激活话术。 */
export function nodeActivationPrompt(nodeId: string, label?: string | null): string {
  const prompts: Record<string, string> = {
    gn_meeting: '国能会议',
    email: '写邮件',
    room: '会议室',
    travel: '差旅单',
    booking: '订车票',
    hotel: '订酒店',
    workpackage: '填工时',
    leave: '请假',
    info_collect: '填信息',
  }
  return prompts[nodeId] ?? label ?? '开始办理'
}

function travelPlanMeta(msg: Message): { status?: string; email_only?: boolean } | null {
  const raw = msg.metadata?.travel_plan_confirm as { status?: string; email_only?: boolean } | undefined
  if (!raw || raw.email_only) return null
  return raw
}

function isPendingWorkflowCancelForNode(msg: Message, nodeId: string): boolean {
  const meta = msg.metadata ?? {}
  const cancel = meta.workflow_cancel_confirm as { status?: string; node_id?: string } | undefined
  if (cancel?.status === 'pending' && cancel.node_id === nodeId) {
    return true
  }
  if (nodeId === 'room') {
    const legacy = meta.room_cancel_confirm as { status?: string } | undefined
    return legacy?.status === 'pending'
  }
  return false
}

function hasWorkflowCancelMeta(msg: Message, nodeId: string): boolean {
  const meta = msg.metadata ?? {}
  const cancel = meta.workflow_cancel_confirm as { node_id?: string } | undefined
  if (cancel?.node_id === nodeId) return true
  return nodeId === 'room' && Boolean(meta.room_cancel_confirm)
}

/** 消息是否包含该节点可编辑的待确认面板。 */
export function messageHasPendingInteractivePanel(
  msg: Message,
  nodeId: string,
): boolean {
  const meta = msg.metadata ?? {}
  switch (nodeId) {
    case 'travel':
      return travelPlanMeta(msg)?.status === 'pending'
        || isPendingWorkflowCancelForNode(msg, nodeId)
    case 'email':
      return Boolean(
        (meta.travel_plan_confirm as { email_only?: boolean; status?: string } | undefined)
          ?.email_only
        && (meta.travel_plan_confirm as { status?: string }).status === 'pending',
      ) || isPendingWorkflowCancelForNode(msg, nodeId)
    case 'room':
      return isPendingWorkflowCancelForNode(msg, nodeId)
        || (meta.meeting_plan_confirm as { status?: string } | undefined)?.status === 'pending'
        || (meta.room_selection as { status?: string } | undefined)?.status === 'pending'
        || (
          (meta.meeting_cancel_selection as { status?: string } | undefined)?.status === 'pending'
        )
    case 'booking':
    case 'hotel':
      return (meta.booking_selection as { status?: string } | undefined)?.status === 'pending'
        || isPendingWorkflowCancelForNode(msg, nodeId)
    case 'workpackage':
      return Boolean(
        (meta.workpackage_plan_confirm as { status?: string } | undefined)?.status === 'pending'
        || (meta.workpackage_confirm as { status?: string } | undefined)?.status === 'pending',
      ) || isPendingWorkflowCancelForNode(msg, nodeId)
    case 'leave':
      return (meta.leave_plan_confirm as { status?: string } | undefined)?.status === 'pending'
        || isPendingWorkflowCancelForNode(msg, nodeId)
    case 'info_collect':
      return (meta.info_collect_plan_confirm as { status?: string } | undefined)?.status === 'pending'
        || isPendingWorkflowCancelForNode(msg, nodeId)
    case 'gn_meeting':
      return (meta.meeting_plan_confirm as { status?: string } | undefined)?.status === 'pending'
        || isPendingWorkflowCancelForNode(msg, nodeId)
        || (
          (meta.meeting_cancel_selection as { status?: string } | undefined)?.status === 'pending'
        )
    default:
      return false
  }
}

/** 从后往前查找与办理节点相关的最新一条消息。 */
export function findLatestMessageForNode(
  messages: Message[],
  node: WorkflowPlanNode,
): Message | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const msg = messages[index]
    if (messageHasPendingInteractivePanel(msg, node.id)) {
      return msg
    }
  }
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const msg = messages[index]
    if (messageMatchesWorkflowNode(msg, node.id, node.task_id)) {
      return msg
    }
  }
  return null
}
