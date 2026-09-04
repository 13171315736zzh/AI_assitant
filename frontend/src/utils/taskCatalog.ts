import type { Task, TaskStep } from '@/types'
import type { TaskCategory, TaskDisplayStatus, TaskSummary } from '@/types'

const CATEGORY_LABELS: Record<TaskCategory, string> = {
  travel: '差旅办事',
  meeting: '会议预约',
  gn_meeting: '国能会议',
  workpackage: '工时填报',
  leave: '请假申请',
  email: '邮件撰写',
  info_collect: '信息收集',
  other: '综合办事',
}

const TOOL_TAGS: Record<string, string> = {
  travel_apply: '差旅申请',
  flight_book: '机票预订',
  hotel_book: '酒店预订',
  email_notify: '邮件通知',
  meeting_book: '会议预约',
  gn_meeting_book: '国能会议',
  room_book: '会议室',
  workpackage_fill: '工时填报',
  leave_apply: '请假申请',
  info_collect_publish: '信息收集',
}

export function inferTaskCategory(steps: TaskStep[]): TaskCategory {
  const tools = new Set(steps.map((s) => s.tool))
  if (tools.has('info_collect_publish')) return 'info_collect'
  if (tools.has('leave_apply')) return 'leave'
  if (tools.has('workpackage_fill')) return 'workpackage'
  if (tools.has('gn_meeting_book')) return 'gn_meeting'
  if (tools.has('meeting_book') || tools.has('room_book')) return 'meeting'
  if (tools.has('travel_apply') || tools.has('flight_book') || tools.has('hotel_book')) {
    return 'travel'
  }
  if (tools.has('email_notify')) return 'email'
  return 'other'
}

export function inferTaskTags(steps: TaskStep[]): string[] {
  const tags: string[] = []
  for (const step of steps) {
    if (step.tool === 'user_confirm') continue
    const label = TOOL_TAGS[step.tool] ?? step.action
    if (label && !tags.includes(label)) tags.push(label)
  }
  return tags
}

export function countCompletedSteps(steps: TaskStep[]): number {
  return steps.filter((s) => s.status === 'completed').length
}

export function effectiveTaskStatus(task: Task): TaskDisplayStatus {
  if (task.status === 'cancelled') return 'cancelled'
  if (task.status === 'completed') return 'completed'
  if (task.status === 'failed') return 'failed'
  if (task.steps.length && task.steps.every((s) => s.status === 'completed')) {
    return 'completed'
  }
  return 'running'
}

export function categoryLabel(category: TaskCategory): string {
  return CATEGORY_LABELS[category] ?? '综合办事'
}

export function buildTaskSummary(task: Task): TaskSummary {
  const completed = countCompletedSteps(task.steps)
  const total = task.total_steps || task.steps.length
  const category = inferTaskCategory(task.steps)
  const status = effectiveTaskStatus(task)
  return {
    id: task.id,
    session_id: task.session_id,
    goal: task.goal,
    status,
    raw_status: task.status,
    category,
    category_label: categoryLabel(category),
    tags: inferTaskTags(task.steps),
    completed_steps: completed,
    total_steps: total,
    progress_percent: total ? Math.round((completed / total) * 100) : 0,
    current_step: task.current_step,
    replan_count: task.replan_count,
    created_at: task.created_at,
  }
}

export const CATEGORY_ICONS: Record<TaskCategory, string> = {
  travel: '✈️',
  meeting: '📅',
  gn_meeting: '🎥',
  workpackage: '📊',
  leave: '🏖️',
  email: '✉️',
  info_collect: '📝',
  other: '📋',
}

export const STATUS_LABELS: Record<TaskDisplayStatus, string> = {
  running: '进行中',
  completed: '已完成',
  cancelled: '已取消',
  failed: '失败',
}
