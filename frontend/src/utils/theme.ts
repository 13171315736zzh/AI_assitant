import type { ThemeValue } from '@/services/settingsService'

const STORAGE_KEY = 'app-theme'

export function getStoredTheme(): ThemeValue {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark' || stored === 'system') {
    return stored
  }
  return 'light'
}

export function applyTheme(theme: ThemeValue): void {
  localStorage.setItem(STORAGE_KEY, theme)
  const root = document.documentElement
  root.dataset.theme = theme

  if (theme === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    root.dataset.resolvedTheme = prefersDark ? 'dark' : 'light'
    return
  }

  root.dataset.resolvedTheme = theme
}

export function initTheme(): void {
  applyTheme(getStoredTheme())
}

export const themeLabels: Record<ThemeValue, string> = {
  light: '浅色',
  dark: '深色',
  system: '跟随系统',
}
