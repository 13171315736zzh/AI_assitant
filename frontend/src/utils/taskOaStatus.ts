import type { Message, Task } from '@/types'
import { detectOaPhase } from '@/utils/oaDemo'
import { isGnMeetingTask, isRoomBookingTask } from '@/utils/oaMeeting'

export type OaHandleStatus = 'unsubmitted' | 'reviewing' | 'completed' | 'rejected'

export const OA_HANDLE_STATUS_LABEL: Record<OaHandleStatus, string> = {
  unsubmitted: '未提交',
  reviewing: '审核中',
  completed: '已完成',
  rejected: '被驳回',
}

export function detectOaHandleStatus(task: Task | null): OaHandleStatus {
  if (!task) return 'unsubmitted'
  if (task.status === 'cancelled' || task.status === 'failed') return 'rejected'
  if (task.status === 'completed') return 'completed'
  const phase = detectOaPhase(task)
  if (phase === 'approved') return 'completed'
  if (phase === 'submitted') return 'reviewing'
  return 'unsubmitted'
}

export interface TaskOutcomeItem {
  label: string
  value: string
}

export interface TaskOutcomeExtras {
  gnMeeting?: {
    meeting_no: string
    meeting_link: string
    meeting_password: string
    subject?: string
  } | null
  roomBooking?: {
    room_name: string
    subject: string
    start_time: string
    end_time: string
    time_label: string
    attendees: string
  } | null
  items: TaskOutcomeItem[]
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? value as Record<string, unknown> : null
}

function str(value: unknown): string {
  if (value === null || value === undefined) return ''
  const text = String(value).trim()
  return text && text !== '—' ? text : ''
}

function pushItem(items: TaskOutcomeItem[], label: string, value: unknown) {
  const text = str(value)
  if (!text) return
  if (items.some((item) => item.label === label && item.value === text)) return
  items.push({ label, value: text })
}

function messageMatchesTask(msg: Message, taskId: string): boolean {
  const meta = msg.metadata ?? {}
  if (meta.task_id === taskId) return true
  const completed = asRecord(meta.workflow_completed_node)
  if (completed?.task_id === taskId) return true
  const related = meta.related_tasks
  if (Array.isArray(related)) {
    return related.some((item) => asRecord(item)?.task_id === taskId)
  }
  return false
}

export const GN_EXCLUDED_LABELS = new Set(['会议室', '会议室偏好', '人数要求'])

export function isGnDrawerNode(nodeId?: string | null, title?: string | null): boolean {
  if (nodeId === 'gn_meeting') return true
  return Boolean(title && title.includes('国能'))
}

export function filterDrawerItems(
  items: TaskOutcomeItem[],
  nodeId?: string | null,
  title?: string | null,
): TaskOutcomeItem[] {
  if (!isGnDrawerNode(nodeId, title)) return items
  return items.filter((item) => !GN_EXCLUDED_LABELS.has(item.label))
}

function upsertItem(items: TaskOutcomeItem[], label: string, value: unknown) {
  const text = str(value)
  if (!text) return
  const index = items.findIndex((item) => item.label === label)
  if (index >= 0) {
    items[index] = { label, value: text }
    return
  }
  items.push({ label, value: text })
}

function valueFromItems(items: TaskOutcomeItem[], label: string): string {
  return items.find((item) => item.label === label)?.value ?? ''
}

function draftTimeLabel(draft: Record<string, unknown>): string {
  const dateHint = str(draft.date_hint)
  const startHint = str(draft.start_hint)
  const endHint = str(draft.end_hint)
  if (!dateHint || !startHint) return ''
  return `${dateHint} ${startHint}${endHint ? ` — ${endHint}` : ''}`
}

export function mergeLiveDrawerItems(
  nodeId: string | null | undefined,
  baseItems: TaskOutcomeItem[],
  draft: Record<string, unknown> | null | undefined,
  title?: string | null,
): TaskOutcomeItem[] {
  if (isGnDrawerNode(nodeId, title)) {
    const items: TaskOutcomeItem[] = []
    const subject = str(draft?.subject || draft?.meeting_topic || draft?.meeting_name)
      || valueFromItems(baseItems, '会议主题')
    const attendees = str(draft?.attendees) || valueFromItems(baseItems, '参会人员')
    const time = (draft ? draftTimeLabel(draft) : '')
      || valueFromItems(baseItems, '时间')
      || valueFromItems(baseItems, '会议时间')
    upsertItem(items, '会议主题', subject)
    upsertItem(items, '会议形式', '国能会议（线上）')
    upsertItem(items, '时间', time)
    upsertItem(items, '参会人员', attendees)
    return items
  }

  const items = filterDrawerItems(baseItems, nodeId, title).map((item) => ({ ...item }))
  if (!draft) return items

  const subject = draft.subject || draft.meeting_topic || draft.meeting_name
  upsertItem(items, '会议主题', subject)
  upsertItem(items, '参会人员', draft.attendees)
  upsertItem(items, '时间', draftTimeLabel(draft))

  upsertItem(items, '请假类型', draft.leave_type)
  upsertItem(items, '开始日期', draft.date_start)
  upsertItem(items, '结束日期', draft.date_end)
  upsertItem(items, '请假事由', draft.reason)
  upsertItem(items, '出发地', draft.origin)
  upsertItem(items, '目的地', draft.destination)
  upsertItem(items, '出差事由', draft.purpose)
  upsertItem(items, '关联项目', draft.project)

  if (nodeId === 'room') {
    upsertItem(items, '会议室', draft.room || draft.selected_room || draft.room_display)
    upsertItem(items, '会议室偏好', draft.room_preference)
  }

  return items
}

export function collectTaskOutcome(task: Task | null, messages: Message[]): TaskOutcomeExtras {
  const items: TaskOutcomeItem[] = []
  let gnMeeting: TaskOutcomeExtras['gnMeeting'] = null
  let roomBooking: TaskOutcomeExtras['roomBooking'] = null
  const isGn = Boolean(task && isGnMeetingTask(task))
  const isRoom = Boolean(task && isRoomBookingTask(task))

  if (task) {
    for (const step of task.steps) {
      const params = step.params ?? {}
      const result = step.result ?? {}
      pushItem(items, '会议主题', params.subject ?? result.subject)
      if (!isGn) {
        pushItem(items, '会议室', params.room ?? result.room ?? result.room_name)
      }
      pushItem(items, '会议时间', params.time ?? result.time_label)
      pushItem(items, '参会人员', params.attendees ?? result.attendees)
      if (str(result.meeting_link) && !isRoom) {
        gnMeeting = {
          meeting_no: str(result.meeting_no),
          meeting_link: str(result.meeting_link),
          meeting_password: str(result.meeting_password),
          subject: str(result.subject) || str(params.subject) || undefined,
        }
      }
    }
  }

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const msg = messages[index]
    if (!task?.id || !messageMatchesTask(msg, task.id)) continue
    const meta = msg.metadata ?? {}
    const gn = asRecord(meta.gn_meeting_result)
    if (gn && str(gn.meeting_link) && !gnMeeting && !isRoom) {
      gnMeeting = {
        meeting_no: str(gn.meeting_no),
        meeting_link: str(gn.meeting_link),
        meeting_password: str(gn.meeting_password),
        subject: str(gn.subject) || undefined,
      }
    }
    const room = asRecord(meta.room_booking_result)
    if (room && str(room.room_name) && !roomBooking && !isGn) {
      roomBooking = {
        room_name: str(room.room_name),
        subject: str(room.subject),
        start_time: str(room.start_time),
        end_time: str(room.end_time),
        time_label: str(room.time_label),
        attendees: str(room.attendees),
      }
    }
    const completed = asRecord(meta.workflow_completed_node)
    const completedItems = completed?.items
    if (Array.isArray(completedItems)) {
      for (const item of completedItems) {
        const row = asRecord(item)
        if (row) pushItem(items, str(row.label), row.value)
      }
    }
    const confirmed = meta.confirmed_items
    if (Array.isArray(confirmed)) {
      for (const item of confirmed) {
        const row = asRecord(item)
        if (row) pushItem(items, str(row.label), row.value)
      }
    }
    const resultMaps = [
      asRecord(meta.leave_result),
      asRecord(meta.travel_apply_result),
      asRecord(meta.workpackage_result),
      asRecord(meta.transport_booking_result),
      asRecord(meta.hotel_booking_result),
    ]
    const resultLabels: Record<string, string> = {
      leave_type: '请假类型',
      date_start: '开始日期',
      date_end: '结束日期',
      days: '请假天数',
      reason: '请假事由',
      destination: '目的地',
      departure_date: '出发日期',
      return_date: '返回日期',
      project: '关联项目',
      transport: '交通方式',
      description: '出差说明',
      period: '填报周期',
      hours: '工时',
      content: '工作内容',
      transport_mode: '交通方式',
      origin: '出发地',
      passenger_name: '乘客',
      departure_time: '出发时间',
      flight_no: '车次/航班',
      guest_name: '入住人',
      hotel_name: '酒店',
      room_type: '房型',
      check_in: '入住日期',
      check_out: '离店日期',
      amount: '金额',
      receipt_id: '回执单号',
      subject: '会议主题',
    }
    for (const result of resultMaps) {
      if (!result) continue
      for (const [key, label] of Object.entries(resultLabels)) {
        pushItem(items, label, result[key])
      }
    }
  }

  if (gnMeeting?.subject) {
    pushItem(items, '会议主题', gnMeeting.subject)
  }
  if (roomBooking && !isGn) {
    pushItem(items, '会议室', roomBooking.room_name)
    pushItem(items, '会议主题', roomBooking.subject)
    pushItem(items, '使用时间', roomBooking.time_label || `${roomBooking.start_time} — ${roomBooking.end_time}`)
    pushItem(items, '参会人员', roomBooking.attendees)
  }

  const nodeId = isGn ? 'gn_meeting' : isRoom ? 'room' : null
  return { gnMeeting, roomBooking, items: filterDrawerItems(items, nodeId) }
}
