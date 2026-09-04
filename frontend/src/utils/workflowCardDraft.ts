import type { Message } from '@/types'

export const WORKFLOW_PLAN_CONFIRM_KEYS = [
  'info_collect_plan_confirm',
  'travel_plan_confirm',
  'workpackage_plan_confirm',
  'meeting_plan_confirm',
  'leave_plan_confirm',
] as const

export type WorkflowPlanConfirmKey = (typeof WORKFLOW_PLAN_CONFIRM_KEYS)[number]

export interface WorkflowCardDraft {
  messageId: string
  metaKey: WorkflowPlanConfirmKey
  payload: Record<string, unknown>
}

export function findPendingWorkflowCard(
  messages: Message[],
): { messageId: string; metaKey: WorkflowPlanConfirmKey } | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const msg = messages[i]
    if (msg.role !== 'assistant') continue
    for (const key of WORKFLOW_PLAN_CONFIRM_KEYS) {
      const meta = msg.metadata?.[key] as { status?: string } | undefined
      if (meta?.status === 'pending') {
        return { messageId: msg.id, metaKey: key }
      }
    }
  }
  return null
}

export function buildCardDraftQueryParam(draft: WorkflowCardDraft | null): string | undefined {
  if (!draft?.payload || !Object.keys(draft.payload).length) return undefined
  return JSON.stringify({
    message_id: draft.messageId,
    meta_key: draft.metaKey,
    payload: draft.payload,
  })
}
