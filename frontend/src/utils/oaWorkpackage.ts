import type { Task, TimesheetEntry } from '@/types'

export function isWorkpackageTask(task: Task): boolean {
  return task.steps.some((s) => s.tool === 'workpackage_fill')
}

export function findWorkpackageFormId(task: Task): string | null {
  const step = task.steps.find((s) => s.tool === 'workpackage_fill')
  const formId = step?.result?.form_id
  return typeof formId === 'string' ? formId : null
}

export function findWorkpackageEntries(task: Task): TimesheetEntry[] {
  const step = task.steps.find((s) => s.tool === 'workpackage_fill')
  const raw = step?.result?.entries
  if (!Array.isArray(raw)) return []
  return raw.filter(
    (e): e is TimesheetEntry =>
      e != null && typeof e === 'object' && typeof (e as TimesheetEntry).day_date === 'string',
  )
}

export function findWorkpackageTotals(task: Task): { totalHours: number; totalPersonDays: number } {
  const step = task.steps.find((s) => s.tool === 'workpackage_fill')
  const result = step?.result
  const entries = findWorkpackageEntries(task)
  const totalHours =
    typeof result?.total_hours === 'number'
      ? result.total_hours
      : entries.reduce((sum, e) => sum + (e.hours ?? 0), 0)
  const totalPersonDays =
    typeof result?.total_person_days === 'number'
      ? result.total_person_days
      : entries.reduce((sum, e) => sum + (e.person_days ?? 0), 0)
  return { totalHours, totalPersonDays }
}

export function buildOaWorkpackageApplyPath(taskId: string): string {
  return `/oa/workpackage/${encodeURIComponent(taskId)}`
}

export function openOaWorkpackageApply(taskId: string): Window | null {
  const path = buildOaWorkpackageApplyPath(taskId)
  const url = `${window.location.origin}${path}`
  return window.open(url, '_blank', 'noopener,noreferrer')
}

export function formatPersonDays(value: number): string {
  if (value === Math.floor(value)) return `${Math.floor(value)} 人·天`
  return `${value} 人·天`
}
