export const TRAVEL_MODE_PREFERENCE_OPTIONS = [
  '飞机',
  '高铁',
  '自驾',
  '无偏好',
] as const

export type TravelModePreference = (typeof TRAVEL_MODE_PREFERENCE_OPTIONS)[number]
