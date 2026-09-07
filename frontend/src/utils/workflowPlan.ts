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

const STATUS_RANK: Record<WorkflowNodeStatus, number> = {
  pending: 0,
  running: 1,
  submitted: 2,
  completed: 3,
}

function mergeNodeStatus(a: WorkflowNodeStatus, b: WorkflowNodeStatus): WorkflowNodeStatus {
  return STATUS_RANK[a] >= STATUS_RANK[b] ? a : b
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
  }
  return map[status]
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
      if (meta.email_compose) return true
      if (meta.email_sent_result) return true
      if (meta.category === 'email') return true
      if (Boolean((meta.travel_plan_confirm as { email_only?: boolean } | undefined)?.email_only)) {
        return true
      }
      if (msg.message_type === 'task' && String(meta.steps_desc ?? '').includes('邮件')) return true
      break
    case 'travel':
      if (meta.travel_plan_confirm && !(meta.travel_plan_confirm as { email_only?: boolean }).email_only) {
        return true
      }
      if (msg.message_type === 'task' && /差旅|出差/.test(String(meta.steps_desc ?? meta.task_title ?? ''))) {
        return true
      }
      break
    case 'booking': {
      const booking = meta.booking_selection as { needs_flight?: boolean; booking_kind?: string } | undefined
      if (booking?.needs_flight || booking?.booking_kind === 'transport') return true
      if (msg.message_type === 'task' && /交通|航班|机票|车票/.test(String(meta.steps_desc ?? ''))) return true
      break
    }
    case 'hotel': {
      const booking = meta.booking_selection as { needs_hotel?: boolean; booking_kind?: string } | undefined
      if (booking?.needs_hotel || booking?.booking_kind === 'hotel') return true
      if (msg.message_type === 'task' && /酒店|住宿/.test(String(meta.steps_desc ?? ''))) return true
      break
    }
    case 'workpackage':
      if (meta.workpackage_plan_confirm || meta.workpackage_confirm) return true
      if (msg.message_type === 'task' && /工时|工包/.test(String(meta.steps_desc ?? meta.task_title ?? ''))) {
        return true
      }
      break
    case 'leave':
      if (meta.leave_plan_confirm) return true
      if (msg.message_type === 'task' && /请假/.test(String(meta.steps_desc ?? meta.task_title ?? ''))) return true
      break
    case 'room':
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

/** 从后往前查找与办理节点相关的最新一条消息。 */
export function findLatestMessageForNode(
  messages: Message[],
  node: WorkflowPlanNode,
): Message | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const msg = messages[index]
    if (messageMatchesWorkflowNode(msg, node.id, node.task_id)) {
      return msg
    }
  }
  return null
}
