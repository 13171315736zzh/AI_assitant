import type { Task } from '@/types'

export type BookingKind = 'transport' | 'hotel'

export function isTransportBookTask(task: Task): boolean {
  return task.steps.some((s) => s.tool === 'flight_book') && !task.steps.some((s) => s.tool === 'travel_apply')
}

export function isHotelBookTask(task: Task): boolean {
  return task.steps.some((s) => s.tool === 'hotel_book') && !task.steps.some((s) => s.tool === 'travel_apply')
}

export function findBookingFormId(task: Task, tool: 'flight_book' | 'hotel_book'): string | null {
  const step = task.steps.find((s) => s.tool === tool)
  const formId = step?.result?.form_id
  return typeof formId === 'string' ? formId : null
}

export function buildOaTransportBookPath(taskId: string): string {
  return `/oa/transport/${encodeURIComponent(taskId)}`
}

export function buildOaHotelBookPath(taskId: string): string {
  return `/oa/hotel/${encodeURIComponent(taskId)}`
}

export function openOaTransportBook(taskId: string): Window | null {
  const url = `${window.location.origin}${buildOaTransportBookPath(taskId)}`
  return window.open(url, '_blank', 'noopener,noreferrer')
}

export function openOaHotelBook(taskId: string): Window | null {
  const url = `${window.location.origin}${buildOaHotelBookPath(taskId)}`
  return window.open(url, '_blank', 'noopener,noreferrer')
}

export function openOaBookingByKind(taskId: string, kind: BookingKind): Window | null {
  return kind === 'transport' ? openOaTransportBook(taskId) : openOaHotelBook(taskId)
}
