export const GENDER_OPTIONS = ['男', '女'] as const

export type Gender = (typeof GENDER_OPTIONS)[number]

/** 展示用：unknown / 空值统一为「男」 */
export function normalizeGender(value: string | undefined | null): string {
  const gender = (value ?? '').trim()
  if (gender === '男' || gender === '女') return gender
  return '男'
}
