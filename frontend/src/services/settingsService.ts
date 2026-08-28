import type { ApiResponse } from '@/types'
import type {
  MemoryItem,
  MemorySettings,
  ProfileSettings,
  ThemeValue,
  VersionCheckResult,
  VersionInfo,
} from '@/mocks/settings'
import {
  mockCheckVersion,
  mockClearMemory,
  mockGetMemory,
  mockGetProfile,
  mockGetTheme,
  mockGetVersion,
  mockUpdateMemory,
  mockUpdateTheme,
} from '@/mocks/settings'
import api, { isMockMode } from './api'

export type { MemoryItem, MemorySettings, ProfileSettings, ThemeValue, VersionCheckResult, VersionInfo }

export async function fetchProfile(): Promise<ApiResponse<ProfileSettings>> {
  if (isMockMode('settings')) {
    await delay(150)
    return { code: 200, message: 'success', data: mockGetProfile() }
  }
  const { data } = await api.get<ApiResponse<ProfileSettings>>('/settings/profile')
  return data
}

export async function fetchTheme(): Promise<ApiResponse<{ theme: ThemeValue }>> {
  if (isMockMode('settings')) {
    await delay(100)
    return { code: 200, message: 'success', data: mockGetTheme() }
  }
  const { data } = await api.get<ApiResponse<{ theme: ThemeValue }>>('/settings/theme')
  return data
}

export async function updateTheme(theme: ThemeValue): Promise<ApiResponse<{ theme: ThemeValue }>> {
  if (isMockMode('settings')) {
    await delay(150)
    return { code: 200, message: 'success', data: mockUpdateTheme(theme) }
  }
  const { data } = await api.patch<ApiResponse<{ theme: ThemeValue }>>('/settings/theme', { theme })
  return data
}

export async function fetchVersion(): Promise<ApiResponse<VersionInfo>> {
  if (isMockMode('settings')) {
    await delay(150)
    return { code: 200, message: 'success', data: mockGetVersion() }
  }
  const { data } = await api.get<ApiResponse<VersionInfo>>('/settings/version')
  return data
}

export async function checkVersion(): Promise<ApiResponse<VersionCheckResult>> {
  if (isMockMode('settings')) {
    await delay(200)
    return { code: 200, message: 'success', data: mockCheckVersion() }
  }
  const { data } = await api.post<ApiResponse<VersionCheckResult>>('/settings/version/check')
  return data
}

export async function fetchMemory(): Promise<ApiResponse<MemorySettings>> {
  if (isMockMode('settings')) {
    await delay(150)
    return { code: 200, message: 'success', data: mockGetMemory() }
  }
  const { data } = await api.get<ApiResponse<MemorySettings>>('/settings/memory')
  return data
}

export async function updateMemory(payload: {
  memory_enabled?: boolean
  memory_items?: MemoryItem[]
}): Promise<ApiResponse<MemorySettings>> {
  if (isMockMode('settings')) {
    await delay(200)
    return { code: 200, message: 'success', data: mockUpdateMemory(payload) }
  }
  const { data } = await api.patch<ApiResponse<MemorySettings>>('/settings/memory', payload)
  return data
}

export async function clearUserMemory(): Promise<ApiResponse<{ cleared: boolean }>> {
  if (isMockMode('settings')) {
    await delay(200)
    return { code: 200, message: 'success', data: mockClearMemory() }
  }
  const { data } = await api.delete<ApiResponse<{ cleared: boolean }>>('/users/me/memory')
  return data
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
