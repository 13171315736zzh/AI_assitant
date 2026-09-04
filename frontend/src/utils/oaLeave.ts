import type { Task } from '@/types'

export interface LeaveApplyResult {
  leave_type?: string
  date_start?: string
  date_end?: string
  start_period?: string
  end_period?: string
  reason?: string
  attachment_name?: string
  days?: number
}

export function isLeaveTask(task: Task): boolean {
  return task.steps.some((s) => s.tool === 'leave_apply')
}

export function findLeaveFormId(task: Task): string | null {
  const step = task.steps.find((s) => s.tool === 'leave_apply')
  const formId = step?.result?.form_id
  return typeof formId === 'string' ? formId : null
}

export function findLeaveApplyResult(task: Task): LeaveApplyResult {
  const step = task.steps.find((s) => s.tool === 'leave_apply')
  const result = step?.result
  if (!result || typeof result !== 'object') return {}
  return {
    leave_type: typeof result.leave_type === 'string' ? result.leave_type : undefined,
    date_start: typeof result.date_start === 'string' ? result.date_start : undefined,
    date_end: typeof result.date_end === 'string' ? result.date_end : undefined,
    start_period: typeof result.start_period === 'string' ? result.start_period : undefined,
    end_period: typeof result.end_period === 'string' ? result.end_period : undefined,
    reason: typeof result.reason === 'string' ? result.reason : undefined,
    attachment_name:
      typeof result.attachment_name === 'string' ? result.attachment_name : undefined,
    days: typeof result.days === 'number' ? result.days : undefined,
  }
}

export function buildOaLeaveApplyPath(taskId: string): string {
  return `/oa/leave/${encodeURIComponent(taskId)}`
}

export function openOaLeaveApply(taskId: string): Window | null {
  const path = buildOaLeaveApplyPath(taskId)
  const url = `${window.location.origin}${path}`
  return window.open(url, '_blank', 'noopener,noreferrer')
}
