import type { Message, WorkflowNodeStatus, WorkflowPlan, WorkflowPlanNode } from '@/types'

const STATUS_RANK: Record<WorkflowNodeStatus, number> = {
  pending: 0,
  running: 1,
  submitted: 2,
  completed: 3,
}

function mergeNodeStatus(a: WorkflowNodeStatus, b: WorkflowNodeStatus): WorkflowNodeStatus {
  return STATUS_RANK[a] >= STATUS_RANK[b] ? a : b
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

  const nodes = plans[0]?.nodes
    .map((node) => nodeMap.get(node.id))
    .filter((node): node is WorkflowPlanNode => Boolean(node))

  return {
    nodes: nodes.length ? nodes : Array.from(nodeMap.values()),
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
