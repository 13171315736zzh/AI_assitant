import type { ApiResponse, PaginatedData } from '@/types'
import type {
  AdminConversation,
  AdminConversationDetail,
  AdminDocument,
  AdminQA,
  ConversationStats,
  SystemConfig,
} from '@/mocks/admin'
import {
  mockAdminDocumentsList,
  mockAdminQAList,
  mockConversationStats,
  mockConversationsList,
  mockGetConversationDetail,
  mockSearchTest,
  mockSystemConfig,
  mockUpdateSystemConfig,
} from '@/mocks/admin'
import api, { isMockMode } from './api'

export async function fetchAdminDocuments(): Promise<ApiResponse<PaginatedData<AdminDocument>>> {
  if (isMockMode()) {
    await delay(150)
    return { code: 200, message: 'success', data: mockAdminDocumentsList() }
  }
  const { data } = await api.get('/admin/documents')
  return data
}

export async function fetchAdminQA(keyword?: string): Promise<ApiResponse<PaginatedData<AdminQA>>> {
  if (isMockMode()) {
    await delay(150)
    return { code: 200, message: 'success', data: mockAdminQAList(keyword) }
  }
  const { data } = await api.get('/admin/qa', { params: { keyword } })
  return data
}

export async function searchTest(query: string): Promise<
  ApiResponse<{ results: Array<{ type: string; question: string; answer: string; similarity: number; source_clause: string }> }>
> {
  if (isMockMode()) {
    await delay(300)
    return { code: 200, message: 'success', data: mockSearchTest(query) }
  }
  const { data } = await api.post('/admin/search-test', { query })
  return data
}

export async function fetchConversationStats(): Promise<ApiResponse<ConversationStats>> {
  if (isMockMode()) {
    return { code: 200, message: 'success', data: mockConversationStats }
  }
  const { data } = await api.get('/admin/conversations/stats')
  return data
}

export async function fetchAdminConversations(
  keyword?: string,
  status?: string,
): Promise<ApiResponse<PaginatedData<AdminConversation>>> {
  if (isMockMode()) {
    await delay(200)
    return { code: 200, message: 'success', data: mockConversationsList(keyword, status) }
  }
  const { data } = await api.get('/admin/conversations', { params: { keyword, status } })
  return data
}

export async function fetchAdminConversationDetail(
  sessionId: string,
): Promise<ApiResponse<AdminConversationDetail>> {
  if (isMockMode()) {
    await delay(200)
    const detail = mockGetConversationDetail(sessionId)
    if (!detail) {
      return { code: 404, message: '会话不存在', data: null as unknown as AdminConversationDetail }
    }
    return { code: 200, message: 'success', data: detail }
  }
  const { data } = await api.get<ApiResponse<AdminConversationDetail>>(
    `/admin/conversations/${sessionId}`,
  )
  return data
}

export async function fetchSystemConfig(): Promise<ApiResponse<SystemConfig>> {
  if (isMockMode()) {
    await delay(150)
    return { code: 200, message: 'success', data: { ...mockSystemConfig } }
  }
  const { data } = await api.get('/admin/settings')
  return data
}

export async function updateSystemConfig(config: Partial<SystemConfig>): Promise<ApiResponse<SystemConfig>> {
  if (isMockMode()) {
    await delay(300)
    return { code: 200, message: 'success', data: mockUpdateSystemConfig(config) }
  }
  const { data } = await api.put('/admin/settings', config)
  return data
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export type { AdminDocument, AdminQA, AdminConversation, AdminConversationDetail, ConversationStats, SystemConfig }
