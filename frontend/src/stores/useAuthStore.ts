import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types'
import { login as loginApi, logout as logoutApi, fetchMe } from '@/services/authService'
import { useChatStore } from './useChatStore'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(loadUser())
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  function loadUser(): User | null {
    const raw = localStorage.getItem('user')
    if (!raw) return null
    try {
      return JSON.parse(raw) as User
    } catch {
      return null
    }
  }

  function persistAuth(accessToken: string, userData: User) {
    const prevId = user.value?.id
    token.value = accessToken
    user.value = userData
    localStorage.setItem('token', accessToken)
    localStorage.setItem('user', JSON.stringify(userData))
    if (prevId != null && prevId !== userData.id) {
      useChatStore().reset()
    }
  }

  function clearAuth() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    useChatStore().reset()
  }

  async function login(username: string, password: string) {
    loading.value = true
    error.value = null
    try {
      const res = await loginApi(username, password)
      if (res.code !== 200) {
        error.value = res.message
        return false
      }
      persistAuth(res.data.access_token, res.data.user)
      return true
    } catch {
      error.value = '登录失败，请稍后重试'
      return false
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      await logoutApi()
    } finally {
      clearAuth()
    }
  }

  async function restoreSession() {
    if (!token.value) return false
    const res = await fetchMe()
    if (res.code !== 200) {
      clearAuth()
      return false
    }
    user.value = res.data
    localStorage.setItem('user', JSON.stringify(res.data))
    return true
  }

  return {
    token,
    user,
    loading,
    error,
    isAuthenticated,
    isAdmin,
    login,
    logout,
    restoreSession,
    clearAuth,
  }
})
