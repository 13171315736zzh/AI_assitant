import type { ApiResponse, LoginData, User } from '@/types'
import { mockLogin, mockLogout, mockMe } from '@/mocks/auth'
import api, { isMockMode } from './api'

export async function login(username: string, password: string): Promise<ApiResponse<LoginData>> {
  if (isMockMode('auth')) {
    await delay(300)
    return mockLogin(username, password)
  }
  const { data } = await api.post<ApiResponse<LoginData>>('/auth/login', { username, password })
  return data
}

export async function logout(): Promise<ApiResponse<null>> {
  if (isMockMode('auth')) {
    return mockLogout()
  }
  const { data } = await api.post<ApiResponse<null>>('/auth/logout')
  return data
}

export async function fetchMe(): Promise<ApiResponse<User>> {
  if (isMockMode('auth')) {
    const raw = localStorage.getItem('user')
    const user = raw ? (JSON.parse(raw) as User) : null
    if (!user) {
      return { code: 401, message: '未认证或 Token 已过期', data: null as unknown as User }
    }
    return mockMe(user.id)
  }
  const { data } = await api.get<ApiResponse<User>>('/auth/me')
  return data
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
