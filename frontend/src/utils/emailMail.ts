import type { Task } from '@/types'

export interface EmailComposeFields {
  task_id: string
  session_id?: string
  form_id?: string
  recipient: string
  cc: string
  subject: string
  body: string
  signature: string
}

export interface SentMailRecord extends EmailComposeFields {
  message_id: string
  sent_at: string
  from_name: string
  from_email: string
  recalled?: boolean
}

const PREFILL_PREFIX = 'mail_prefill_'
const DRAFT_PREFIX = 'mail_draft_'
const SENT_PREFIX = 'mail_sent_'

export function buildMailComposePath(taskId: string): string {
  return `/mail/compose/${encodeURIComponent(taskId)}`
}

export function buildMailSentPath(messageId: string): string {
  return `/mail/sent/${encodeURIComponent(messageId)}`
}

export function saveMailPrefill(taskId: string, fields: EmailComposeFields): void {
  sessionStorage.setItem(`${PREFILL_PREFIX}${taskId}`, JSON.stringify(fields))
}

export function loadMailPrefill(taskId: string): EmailComposeFields | null {
  const raw = sessionStorage.getItem(`${PREFILL_PREFIX}${taskId}`)
  if (!raw) return null
  try {
    return JSON.parse(raw) as EmailComposeFields
  } catch {
    return null
  }
}

export function saveMailDraft(taskId: string, fields: EmailComposeFields): void {
  localStorage.setItem(`${DRAFT_PREFIX}${taskId}`, JSON.stringify({
    ...fields,
    saved_at: new Date().toISOString(),
  }))
}

export function loadMailDraft(taskId: string): EmailComposeFields | null {
  const raw = localStorage.getItem(`${DRAFT_PREFIX}${taskId}`)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as EmailComposeFields
    return parsed
  } catch {
    return null
  }
}

export function saveSentMail(record: SentMailRecord): void {
  localStorage.setItem(`${SENT_PREFIX}${record.message_id}`, JSON.stringify(record))
}

export function loadSentMail(messageId: string): SentMailRecord | null {
  const raw = localStorage.getItem(`${SENT_PREFIX}${messageId}`)
  if (!raw) return null
  try {
    return JSON.parse(raw) as SentMailRecord
  } catch {
    return null
  }
}

export function markSentMailRecalled(messageId: string): void {
  const record = loadSentMail(messageId)
  if (!record) return
  record.recalled = true
  saveSentMail(record)
}

export function canRecallSentMail(sentAt: string): boolean {
  const elapsed = Date.now() - new Date(sentAt).getTime()
  return elapsed <= 120_000
}

export function findEmailFormId(task: Task): string | null {
  const step = task.steps.find((s) => s.tool === 'email_notify')
  const formId = step?.result?.form_id
  return typeof formId === 'string' ? formId : null
}

export function isEmailTask(task: Task): boolean {
  return task.steps.some((s) => s.tool === 'email_notify')
    && !task.steps.some((s) => s.tool === 'travel_apply')
}

export function composeFullBody(body: string, signature: string): string {
  const core = body.trim()
  const sign = signature.trim()
  if (!sign) return core
  if (!core) return sign
  return `${core}\n\n${sign}`
}

export function openMailCompose(taskId: string): void {
  window.open(`${window.location.origin}${buildMailComposePath(taskId)}`, '_blank', 'noopener,noreferrer')
}
