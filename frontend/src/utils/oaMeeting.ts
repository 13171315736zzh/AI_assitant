import type { Task } from '@/types'

export function isGnMeetingTask(task: Task): boolean {
  return task.steps.some((s) => s.tool === 'gn_meeting_book')
}

export function isRoomBookingTask(task: Task): boolean {
  return task.steps.some((s) => s.tool === 'meeting_book') && !isGnMeetingTask(task)
}

export function isMeetingTask(task: Task): boolean {
  return isGnMeetingTask(task) || isRoomBookingTask(task)
}

export function findGnMeetingFormId(task: Task): string | null {
  const step = task.steps.find((s) => s.tool === 'gn_meeting_book')
  const formId = step?.result?.form_id
  return typeof formId === 'string' ? formId : null
}

export function findMeetingFormId(task: Task): string | null {
  const step = task.steps.find((s) => s.tool === 'meeting_book')
  const formId = step?.result?.form_id
  return typeof formId === 'string' ? formId : null
}

export function findRoomSelection(task: Task): { room: string; time: string } | null {
  const step = task.steps.find((s) => s.tool === 'room_book')
  if (!step?.result) return null
  const room = step.result.room
  const time = step.params?.time ?? step.result.time
  if (typeof room !== 'string') return null
  return {
    room,
    time: typeof time === 'string' ? time : '',
  }
}

export function buildOaGnMeetingApplyPath(taskId: string): string {
  return `/oa/gn-meeting/${encodeURIComponent(taskId)}`
}

export function buildOaRoomMeetingApplyPath(taskId: string): string {
  return `/oa/room-meeting/${encodeURIComponent(taskId)}`
}

export function openOaGnMeetingApply(taskId: string): Window | null {
  const url = `${window.location.origin}${buildOaGnMeetingApplyPath(taskId)}`
  return window.open(url, '_blank', 'noopener,noreferrer')
}

export function openOaRoomMeetingApply(taskId: string): Window | null {
  const url = `${window.location.origin}${buildOaRoomMeetingApplyPath(taskId)}`
  return window.open(url, '_blank', 'noopener,noreferrer')
}

/** @deprecated use openOaGnMeetingApply or openOaRoomMeetingApply */
export function openOaMeetingApply(taskId: string): Window | null {
  return openOaRoomMeetingApply(taskId)
}

export function buildOaMeetingApplyPath(taskId: string): string {
  return buildOaRoomMeetingApplyPath(taskId)
}
