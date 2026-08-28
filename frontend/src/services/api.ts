import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 10000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

export default api

type MockScope = 'auth' | 'sessions' | 'tasks' | 'forms' | 'knowledge' | 'admin' | 'settings'

/** 全局 Mock 关闭时全部走真实 API；否则可按模块单独关闭 Mock */
export const isMockMode = (scope?: MockScope): boolean => {
  if (import.meta.env.VITE_USE_MOCK !== 'true') return false
  if (!scope) return true
  const envKey = `VITE_MOCK_${scope.toUpperCase()}` as keyof ImportMetaEnv
  const override = import.meta.env[envKey]
  if (override === 'false') return false
  return true
}
