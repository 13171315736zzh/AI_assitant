import type {
  BookingSelectionMeta,
  EmailComposeMeta,
  EmailPlanConfirmMeta,
  MeetingPlanConfirmMeta,
  Message,
  RoomSelectionMeta,
  TravelPlanConfirmMeta,
  WorkflowPlan,
  WorkflowPlanNode,
} from '@/types'
import { nodeStatusLabel } from '@/utils/workflowPlan'

type TaskMeta = Record<string, unknown>

function detailLine(key: string, value: unknown): string {
  const text = String(value ?? '').trim()
  return `     ${key}：${text || '—'}`
}

function formatDateDisplay(value: unknown): string {
  const text = String(value ?? '').trim()
  if (!text) return '—'
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text
  return formatDatetimeDisplay(text)
}

function formatDatetimeDisplay(value: unknown): string {
  const text = String(value ?? '').trim()
  if (!text) return '—'
  const parsed = Date.parse(text)
  if (Number.isNaN(parsed)) return text.length > 16 ? text.slice(0, 16) : text
  const date = new Date(parsed)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function summarizeEmailBody(body: unknown, maxLen = 96): string {
  const raw = String(body ?? '').trim()
  if (!raw) return '—'
  let text = raw.replace(/\s+/g, ' ')
  for (const marker of ['此致', '敬礼', 'Best regards', 'Regards', '顺祝']) {
    const idx = text.indexOf(marker)
    if (idx > 24) {
      text = text.slice(0, idx).trim()
      break
    }
  }
  if (text.length <= maxLen) return text
  return `${text.slice(0, maxLen - 1).trim()}…`
}

function splitDepartTime(departureTime: string | undefined): { date: string; time: string } {
  const text = String(departureTime ?? '').trim()
  if (!text) return { date: '—', time: '' }
  const [date, time] = text.split(/\s+/)
  return { date: date || '—', time: time || '' }
}

function buildTaskMetaIndex(messages: Message[]): Record<string, TaskMeta> {
  const taskMeta: Record<string, TaskMeta> = {}
  for (const msg of messages) {
    const meta = msg.metadata ?? {}
    const tid = meta.task_id
    if (!tid || typeof tid !== 'string') continue
    const merged = { ...(taskMeta[tid] ?? {}), ...meta }
    taskMeta[tid] = merged
  }
  return taskMeta
}

function findMetaForNode(nodeId: string, taskMeta: Record<string, TaskMeta>): TaskMeta {
  const resultKeys: Record<string, string> = {
    gn_meeting: 'gn_meeting_result',
    email: 'email_sent_result',
    room: 'room_booking_result',
    travel: 'travel_apply_result',
    booking: 'transport_booking_result',
    hotel: 'hotel_booking_result',
    workpackage: 'workpackage_result',
    leave: 'leave_result',
  }
  const key = resultKeys[nodeId]
  if (!key) return {}
  for (const meta of Object.values(taskMeta)) {
    if (meta[key]) return meta
  }
  return {}
}

function enrichMetaFromMessages(node: WorkflowPlanNode, messages: Message[], base: TaskMeta): TaskMeta {
  const meta: TaskMeta = { ...base }

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const raw = messages[index].metadata ?? {}

    if (node.id === 'gn_meeting' && !meta.gn_meeting_result) {
      const gn = raw.gn_meeting_result
      if (gn && typeof gn === 'object') {
        meta.gn_meeting_result = gn
        continue
      }
      const meeting = raw.meeting_plan_confirm as MeetingPlanConfirmMeta | undefined
      if (meeting?.subject) {
        meta.gn_meeting_result = { subject: meeting.subject }
      }
    }

    if (node.id === 'email' && !meta.email_sent_result) {
      const sent = raw.email_sent_result
      if (sent && typeof sent === 'object') {
        meta.email_sent_result = sent
        continue
      }
      const compose = raw.email_compose as EmailComposeMeta | undefined
      if (compose?.subject || compose?.body) {
        meta.email_sent_result = {
          subject: compose.subject,
          sent_at: '',
          body_summary: summarizeEmailBody(compose.body),
        }
        continue
      }
      const emailPlan = raw.travel_plan_confirm as EmailPlanConfirmMeta | undefined
      if (emailPlan?.email_only) {
        meta.email_sent_result = {
          subject: emailPlan.subject,
          sent_at: '',
          body_summary: summarizeEmailBody(emailPlan.body),
        }
      }
    }

    if (node.id === 'room' && !meta.room_booking_result) {
      const room = raw.room_booking_result
      if (room && typeof room === 'object') {
        meta.room_booking_result = room
        continue
      }
      const selection = raw.room_selection as RoomSelectionMeta | undefined
      if (selection?.subject || selection?.requested_room) {
        meta.room_booking_result = {
          room_name: selection.requested_room,
          subject: selection.subject,
          start_time: selection.start_time ?? selection.time_label,
          end_time: selection.end_time ?? '—',
          attendees: '—',
        }
        continue
      }
      const meeting = raw.meeting_plan_confirm as MeetingPlanConfirmMeta | undefined
      if (meeting?.needs_room_booking) {
        meta.room_booking_result = {
          room_name: meeting.selected_room ?? meeting.room_hint ?? '—',
          subject: meeting.subject ?? '—',
          start_time: meeting.start_hint ?? meeting.time_hint ?? '—',
          end_time: meeting.end_hint ?? '—',
          attendees: meeting.attendees ?? meeting.attendees_hint ?? '—',
        }
      }
    }

    if (node.id === 'travel' && !meta.travel_apply_result) {
      const travel = raw.travel_apply_result
      if (travel && typeof travel === 'object') {
        meta.travel_apply_result = travel
        continue
      }
      const confirm = raw.travel_plan_confirm as TravelPlanConfirmMeta | undefined
      if (confirm && !('email_only' in confirm && confirm.email_only)) {
        meta.travel_apply_result = {
          receipt_id: '—',
          departure_date: confirm.start_date,
          return_date: confirm.end_date,
        }
      }
    }

    if (node.id === 'booking' && !meta.transport_booking_result) {
      const transport = raw.transport_booking_result
      if (transport && typeof transport === 'object') {
        meta.transport_booking_result = transport
        continue
      }
      const booking = raw.booking_selection as BookingSelectionMeta | undefined
      if (booking && (booking.booking_kind === 'transport' || booking.needs_flight)) {
        const isTrain = booking.transport_type === 'train'
        const picked = isTrain ? booking.trains?.[0] : booking.flights?.[0]
        const confirm = raw.travel_plan_confirm as TravelPlanConfirmMeta | undefined
        const mode = transportModeLabel(confirm?.transport_mode, booking.transport_type)
        const origin = booking.origin || picked?.origin || confirm?.origin
        const destination = booking.destination || picked?.destination || confirm?.destination
        if (picked) {
          const { date, time } = splitDepartTime(picked.departure_time)
          meta.transport_booking_result = {
            transport_mode: mode,
            origin,
            destination,
            flight_no: 'train_no' in picked ? picked.train_no : picked.flight_no,
            departure_date: date,
            departure_time: time,
          }
        } else if (origin || destination || mode !== '—') {
          meta.transport_booking_result = {
            transport_mode: mode,
            origin: origin ?? '—',
            destination: destination ?? '—',
            flight_no: '—',
            departure_date: confirm?.start_date ?? '—',
            departure_time: '—',
          }
        }
      }
    }

    if (node.id === 'hotel' && !meta.hotel_booking_result) {
      const hotel = raw.hotel_booking_result
      if (hotel && typeof hotel === 'object') {
        meta.hotel_booking_result = hotel
        continue
      }
      const booking = raw.booking_selection as BookingSelectionMeta | undefined
      if (booking && (booking.booking_kind === 'hotel' || booking.needs_hotel)) {
        const picked = booking.hotels?.[0]
        if (picked) {
          meta.hotel_booking_result = {
            hotel_name: picked.name,
            room_type: picked.room_type,
            amount: picked.price_per_night,
            check_in: picked.check_in,
            check_out: picked.check_out,
          }
        }
      }
    }
  }

  return meta
}

function transportModeLabel(mode: unknown, transportType?: string): string {
  const text = String(mode ?? '').trim()
  if (text) {
    const mapping: Record<string, string> = { 飞机: '机票', 火车: '高铁', 自驾: '自驾' }
    return mapping[text] ?? text
  }
  if (transportType === 'train') return '高铁'
  if (transportType === 'flight') return '机票'
  return '—'
}

function formatNodeKeyInfoLines(nodeId: string, meta: TaskMeta): string[] {
  if (nodeId === 'gn_meeting') {
    const gn = meta.gn_meeting_result as Record<string, unknown> | undefined
    if (!gn) return []
    return [
      detailLine('主题', gn.subject ?? meta.task_title),
      detailLine('会议链接', gn.meeting_link),
      detailLine('会议密码', gn.meeting_password),
    ]
  }

  if (nodeId === 'email') {
    const em = meta.email_sent_result as Record<string, unknown> | undefined
    if (!em) return []
    return [
      detailLine('邮件标题', em.subject),
      detailLine('发送时间', em.sent_at ? formatDatetimeDisplay(em.sent_at) : '—'),
      detailLine('主要内容梗概', em.body_summary ?? summarizeEmailBody(em.body)),
    ]
  }

  if (nodeId === 'room') {
    const room = meta.room_booking_result as Record<string, unknown> | undefined
    if (!room) return []
    return [
      detailLine('会议室', room.room_name),
      detailLine('主题', room.subject),
      detailLine('时间', `${room.start_time ?? '—'} — ${room.end_time ?? '—'}`),
      detailLine('参会人', room.attendees),
    ]
  }

  if (nodeId === 'travel') {
    const tr = meta.travel_apply_result as Record<string, unknown> | undefined
    if (!tr) return []
    return [
      detailLine('差旅单号', tr.receipt_id),
      detailLine('开始时间', formatDateDisplay(tr.departure_date)),
      detailLine('结束时间', formatDateDisplay(tr.return_date)),
    ]
  }

  if (nodeId === 'booking') {
    const tb = meta.transport_booking_result as Record<string, unknown> | undefined
    if (!tb) return []
    const depDate = formatDateDisplay(tb.departure_date)
    const depTime = String(tb.departure_time ?? '').trim()
    const departAt = depTime && depTime !== '—' ? `${depDate} ${depTime}`.trim() : depDate
    return [
      detailLine('交通方式', tb.transport_mode),
      detailLine('出发地', tb.origin),
      detailLine('目的地', tb.destination),
      detailLine('班次', tb.flight_no),
      detailLine('发车时间', departAt),
    ]
  }

  if (nodeId === 'hotel') {
    const hb = meta.hotel_booking_result as Record<string, unknown> | undefined
    if (!hb) return []
    const amount = String(hb.amount ?? '').trim()
    const amountLabel = amount && amount !== '—' ? `${amount} 元/晚` : '—'
    return [
      detailLine('酒店名称', hb.hotel_name),
      detailLine('房型', hb.room_type),
      detailLine('单价', amountLabel),
      detailLine('入住日期', formatDateDisplay(hb.check_in)),
      detailLine('离店日期', formatDateDisplay(hb.check_out)),
    ]
  }

  if (nodeId === 'workpackage') {
    const wp = meta.workpackage_result as Record<string, unknown> | undefined
    if (!wp) return []
    return [
      detailLine('项目', wp.project),
      detailLine('填报周期', wp.period),
      detailLine('工时', wp.hours ? `${wp.hours} 小时` : '—'),
      detailLine('工作内容', wp.content),
      detailLine('回执单号', wp.receipt_id),
    ]
  }

  if (nodeId === 'leave') {
    const lv = meta.leave_result as Record<string, unknown> | undefined
    if (!lv) return []
    return [
      detailLine('请假类型', lv.leave_type),
      detailLine('开始日期', lv.date_start),
      detailLine('结束日期', lv.date_end),
      detailLine('天数', lv.days),
      detailLine('事由', lv.reason),
      detailLine('回执单号', lv.receipt_id),
    ]
  }

  if (nodeId === 'info_collect') {
    return [detailLine('状态', '已发布')]
  }

  return []
}

function nodeDisplayLabel(node: WorkflowPlanNode): string {
  if (node.id === 'gn_meeting') return '国能会'
  return node.label
}

export function buildWorkflowProgressSummary(plan: WorkflowPlan, messages: Message[]): string {
  const taskMeta = buildTaskMetaIndex(messages)
  const startedNodes = plan.nodes.filter((node) => node.status !== 'pending')
  if (!startedNodes.length) {
    return '【办理详情】\n  （暂无已开始节点）'
  }

  const lines = ['【办理详情】']
  startedNodes.forEach((node, index) => {
    const taskId = node.task_id ?? ''
    let meta = taskId ? { ...(taskMeta[taskId] ?? {}) } : {}
    if (!Object.keys(meta).length) {
      meta = findMetaForNode(node.id, taskMeta)
    }
    meta = enrichMetaFromMessages(node, messages, meta)

    lines.push(`  ${index + 1}. ${nodeDisplayLabel(node)}`)
    lines.push(detailLine('状态', nodeStatusLabel(node.status)))
    lines.push(...formatNodeKeyInfoLines(node.id, meta))
    lines.push('')
  })

  while (lines.length && lines[lines.length - 1] === '') {
    lines.pop()
  }
  return lines.join('\n')
}
