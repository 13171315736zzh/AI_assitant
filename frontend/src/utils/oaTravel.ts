import type { FlightOption, HotelOption, Task, TaskStep } from '@/types'

export function findTravelFormId(task: Task): string | null {
  const step = task.steps.find((s) => s.tool === 'travel_apply')
  const formId = step?.result?.form_id
  return typeof formId === 'string' ? formId : null
}

export function findFlightSelection(task: Task): FlightOption | null {
  return extractBookingSelection<FlightOption>(task, 'flight_book')
}

export function findHotelSelection(task: Task): HotelOption | null {
  return extractBookingSelection<HotelOption>(task, 'hotel_book')
}

function extractBookingSelection<T>(task: Task, tool: string): T | null {
  const step = task.steps.find((s) => s.tool === tool)
  const selected = step?.result?.selected
  if (!selected || typeof selected !== 'object') return null
  return selected as T
}

export function isTravelTask(task: Task): boolean {
  return task.steps.some((s) => s.tool === 'travel_apply')
}

export function buildOaTravelApplyPath(taskId: string): string {
  return `/oa/travel/${encodeURIComponent(taskId)}`
}

export function openOaTravelApply(taskId: string): Window | null {
  const path = buildOaTravelApplyPath(taskId)
  const url = `${window.location.origin}${path}`
  return window.open(url, '_blank', 'noopener,noreferrer')
}

export function formatOaDate(value: string | undefined): string {
  if (!value) return '—'
  const d = value.slice(0, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return value
  const [y, m, day] = d.split('-')
  return `${y}年${Number(m)}月${Number(day)}日`
}

export function stepSummary(step: TaskStep | undefined): string {
  if (!step) return '—'
  const map = {
    completed: '已完成',
    running: '处理中',
    pending: '待处理',
    failed: '失败',
  }
  return map[step.status]
}
