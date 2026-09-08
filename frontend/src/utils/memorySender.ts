import type { MemoryStructured } from '@/services/settingsService'

const GENERIC_ACCOUNT_NAMES = new Set(['', '管理员', '员工', '用户', 'admin', 'user'])

export function isGenericAccountLabel(value: string | undefined | null): boolean {
  return GENERIC_ACCOUNT_NAMES.has((value ?? '').trim().toLowerCase())
}

export function resolveMemorySender(structured: Partial<MemoryStructured> | undefined): {
  fromName: string
  fromEmail: string
  employeeId: string
  department: string
  baseLocation: string
} {
  const name = (structured?.display_name ?? '').trim()
  const email = (structured?.email ?? '').trim()
  return {
    fromName: name && !isGenericAccountLabel(name) ? name : '',
    fromEmail: email.includes('@') ? email : '',
    employeeId: (structured?.employee_id ?? '').trim(),
    department: (structured?.department ?? '').trim(),
    baseLocation: (structured?.base_location ?? '').trim(),
  }
}

export function resolveMemoryDisplayName(
  structured: Partial<MemoryStructured> | undefined,
  accountName?: string | null,
  fallback = '员工',
): string {
  const sender = resolveMemorySender(structured)
  if (sender.fromName) return sender.fromName
  const account = (accountName ?? '').trim()
  if (account && !isGenericAccountLabel(account)) return account
  return fallback
}
