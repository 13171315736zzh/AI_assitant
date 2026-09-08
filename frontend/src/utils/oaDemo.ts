import type { Message, Task } from '@/types'

export const OA_TASK_EVENT = 'assistant:oa-task-update'
const OA_BROADCAST_CHANNEL = 'assistant:oa-task-update'

export type OaPhase = 'draft' | 'submitted' | 'approved'

export interface OaApprovalNode {
  role: string
  name: string
  status: 'done' | 'pending'
  time: string
}

export interface OaDemoPayload {
  sessionId: string
  taskId: string
  action: 'submitted' | 'completed'
  assistantMessage?: Message | null
  task?: Task | null
}

export interface OaTaskActionData {
  session_id: string
  task: Task
  assistant_message?: Message | null
}

export function buildOaNotifyPayload(
  data: OaTaskActionData,
  taskId: string,
  action: OaDemoPayload['action'],
): OaDemoPayload {
  return {
    sessionId: data.session_id,
    taskId,
    action,
    assistantMessage: data.assistant_message ?? null,
    task: data.task,
  }
}

export function detectOaPhase(task: Task | null): OaPhase {
  if (!task) return 'draft'
  if (task.status === 'completed') return 'approved'
  const confirm = task.steps.find((s) => s.tool === 'user_confirm')
  const result = confirm?.result as Record<string, unknown> | null | undefined
  if (result?.oa_submitted || result?.oa_approved) return 'submitted'
  return 'draft'
}

function postOaTaskEvent(message: { type: string } & OaDemoPayload) {
  if (typeof BroadcastChannel !== 'undefined') {
    const channel = new BroadcastChannel(OA_BROADCAST_CHANNEL)
    channel.postMessage(message)
    channel.close()
  }
  if (window.opener && !window.opener.closed) {
    window.opener.postMessage(message, window.location.origin)
  }
  window.postMessage(message, window.location.origin)
}

export function notifyAssistantOaUpdate(payload: OaDemoPayload) {
  postOaTaskEvent({ type: OA_TASK_EVENT, ...payload })
}

export function subscribeOaTaskUpdates(onUpdate: (payload: OaDemoPayload) => void): () => void {
  function dispatch(raw: unknown) {
    const data = raw as { type?: string } & Partial<OaDemoPayload>
    if (data?.type !== OA_TASK_EVENT || !data.sessionId || !data.taskId || !data.action) {
      return
    }
    onUpdate({
      sessionId: data.sessionId,
      taskId: data.taskId,
      action: data.action,
      assistantMessage: data.assistantMessage ?? null,
      task: data.task ?? null,
    })
  }

  function handleMessage(event: MessageEvent) {
    if (event.origin !== window.location.origin) return
    dispatch(event.data)
  }

  window.addEventListener('message', handleMessage)

  let channel: BroadcastChannel | null = null
  if (typeof BroadcastChannel !== 'undefined') {
    channel = new BroadcastChannel(OA_BROADCAST_CHANNEL)
    channel.onmessage = (event) => dispatch(event.data)
  }

  return () => {
    window.removeEventListener('message', handleMessage)
    channel?.close()
  }
}

export function buildWorkpackageApprovalChain(
  applicantName: string,
  phase: OaPhase,
): OaApprovalNode[] {
  const nodes: OaApprovalNode[] = [
    { role: '填报人', name: applicantName, status: 'done', time: '刚刚' },
    { role: '项目经理', name: '张经理', status: 'pending', time: '—' },
    { role: '部门负责人', name: '李总监', status: 'pending', time: '—' },
    { role: '工时审核岗', name: '项目管理办公室', status: 'pending', time: '—' },
  ]
  if (phase === 'submitted') return nodes
  if (phase === 'approved') {
    return nodes.map((node, idx) =>
      idx === 0 ? node : { ...node, status: 'done', time: '刚刚' },
    )
  }
  return nodes
}

export function buildLeaveApprovalChain(
  applicantName: string,
  phase: OaPhase,
): OaApprovalNode[] {
  const nodes: OaApprovalNode[] = [
    { role: '申请人', name: applicantName, status: 'done', time: '刚刚' },
    { role: '直属主管', name: '王主管', status: 'pending', time: '—' },
    { role: '部门负责人', name: '李总监', status: 'pending', time: '—' },
    { role: '人事审核', name: '人力资源部', status: 'pending', time: '—' },
  ]
  if (phase === 'submitted') return nodes
  if (phase === 'approved') {
    return nodes.map((node, idx) =>
      idx === 0 ? node : { ...node, status: 'done', time: '刚刚' },
    )
  }
  return nodes
}

export function buildTravelApprovalChain(
  applicantName: string,
  phase: OaPhase,
): OaApprovalNode[] {
  const nodes: OaApprovalNode[] = [
    { role: '申请人', name: applicantName, status: 'done', time: '刚刚' },
    { role: '部门负责人', name: '李总监', status: 'pending', time: '—' },
    { role: '分管领导', name: '赵副总', status: 'pending', time: '—' },
    { role: '行政审批', name: '差旅管理岗', status: 'pending', time: '—' },
  ]
  if (phase === 'submitted') return nodes
  if (phase === 'approved') {
    return nodes.map((node, idx) =>
      idx === 0 ? node : { ...node, status: 'done', time: '刚刚' },
    )
  }
  return nodes
}

export function buildMeetingApprovalChain(
  applicantName: string,
  phase: OaPhase,
  options?: { gnMeeting?: boolean },
): OaApprovalNode[] {
  const gnMeeting = Boolean(options?.gnMeeting)
  const nodes: OaApprovalNode[] = gnMeeting
    ? [
        { role: '发起人', name: applicantName, status: 'done', time: '刚刚' },
        { role: '会议组织岗', name: '行政办公室', status: 'pending', time: '—' },
        { role: '部门负责人', name: '李总监', status: 'pending', time: '—' },
        { role: 'IT 支持岗', name: '信息化中心', status: 'pending', time: '—' },
      ]
    : [
        { role: '预约人', name: applicantName, status: 'done', time: '刚刚' },
        { role: '行政审核', name: '行政办公室', status: 'pending', time: '—' },
        { role: '会议室管理岗', name: '后勤服务中心', status: 'pending', time: '—' },
      ]
  if (phase === 'submitted') return nodes
  if (phase === 'approved') {
    return nodes.map((node, idx) =>
      idx === 0 ? node : { ...node, status: 'done', time: '刚刚' },
    )
  }
  return nodes
}

export function primaryButtonLabel(phase: OaPhase, submitting: boolean): string {
  if (submitting) return '处理中…'
  if (phase === 'draft') return '提交审批'
  if (phase === 'submitted') return '已提交审批'
  return '审批已完成'
}

export function isPrimaryButtonDisabled(phase: OaPhase, submitting: boolean): boolean {
  if (submitting) return true
  return phase === 'approved'
}

export function isPrimaryButtonSubmittedStyle(phase: OaPhase): boolean {
  return phase === 'submitted' || phase === 'approved'
}

export function gnMeetingStatusBadge(phase: OaPhase): { label: string; class: string } {
  if (phase === 'approved') return { label: '已创建', class: 'approved' }
  return { label: '待创建', class: 'draft' }
}

export function gnMeetingPrimaryButtonLabel(phase: OaPhase, submitting: boolean): string {
  if (submitting) return '处理中…'
  if (phase === 'approved') return '已创建'
  return '创建'
}

export function isGnMeetingPrimaryButtonDisabled(phase: OaPhase, submitting: boolean): boolean {
  if (submitting) return true
  return phase === 'approved'
}

export function transportBookingStatusBadge(phase: OaPhase): { label: string; class: string } {
  return bookingStatusBadge(phase)
}

export function transportBookingPrimaryButtonLabel(phase: OaPhase, submitting: boolean): string {
  return bookingPrimaryButtonLabel(phase, submitting)
}

export function isTransportBookingPrimaryButtonDisabled(phase: OaPhase, submitting: boolean): boolean {
  return isBookingPrimaryButtonDisabled(phase, submitting)
}

export function bookingStatusBadge(phase: OaPhase): { label: string; class: string } {
  if (phase === 'approved') return { label: '已预定', class: 'approved' }
  return { label: '待预定', class: 'draft' }
}

export function bookingPrimaryButtonLabel(phase: OaPhase, submitting: boolean): string {
  if (submitting) return '处理中…'
  if (phase === 'approved') return '已预定'
  return '预定'
}

export function isBookingPrimaryButtonDisabled(phase: OaPhase, submitting: boolean): boolean {
  if (submitting) return true
  return phase === 'approved'
}
