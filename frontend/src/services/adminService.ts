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
  if (isMockMode('knowledge')) {
    await delay(150)
    return { code: 200, message: 'success', data: mockAdminDocumentsList() }
  }
  const { data } = await api.get('/admin/documents')
  return data
}

export async function fetchAdminQA(keyword?: string): Promise<ApiResponse<PaginatedData<AdminQA>>> {
  if (isMockMode('knowledge')) {
    await delay(150)
    return { code: 200, message: 'success', data: mockAdminQAList(keyword) }
  }
  const { data } = await api.get('/admin/qa', { params: { keyword } })
  return data
}

export async function searchTest(query: string): Promise<
  ApiResponse<{ results: Array<{ type: string; question: string; answer: string; similarity: number; source_clause: string }> }>
> {
  if (isMockMode('knowledge')) {
    await delay(300)
    return { code: 200, message: 'success', data: mockSearchTest(query) }
  }
  const { data } = await api.post('/admin/search-test', { query })
  return data
}

export async function uploadAdminDocument(file: File): Promise<
  ApiResponse<{ id: string; filename: string; status: string; progress: { stage: string; percent: number } }>
> {
  if (isMockMode('knowledge')) {
    await delay(400)
    return {
      code: 200,
      message: 'success',
      data: {
        id: `doc_${Date.now()}`,
        filename: file.name,
        status: 'uploading',
        progress: { stage: 'uploading', percent: 0 },
      },
    }
  }
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/admin/documents', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function deleteAdminDocument(documentId: string): Promise<ApiResponse<{ deleted: boolean }>> {
  if (isMockMode('knowledge')) {
    await delay(200)
    return { code: 200, message: 'success', data: { deleted: true } }
  }
  const { data } = await api.delete(`/admin/documents/${documentId}`)
  return data
}

export async function reindexAdminDocument(documentId: string): Promise<
  ApiResponse<{ id: string; status: string; progress: { stage: string; percent: number } }>
> {
  if (isMockMode('knowledge')) {
    await delay(300)
    return {
      code: 200,
      message: 'success',
      data: { id: documentId, status: 'parsing', progress: { stage: 'parsing', percent: 10 } },
    }
  }
  const { data } = await api.post(`/admin/documents/${documentId}/reindex`)
  return data
}

export async function fetchDocumentProgress(documentId: string): Promise<
  ApiResponse<{ id: string; status: string; progress: { stage: string; percent: number } }>
> {
  if (isMockMode('knowledge')) {
    return {
      code: 200,
      message: 'success',
      data: { id: documentId, status: 'ready', progress: { stage: 'ready', percent: 100 } },
    }
  }
  const { data } = await api.get(`/admin/documents/${documentId}/progress`)
  return data
}

export async function fetchConversationStats(): Promise<ApiResponse<ConversationStats>> {
  if (isMockMode('admin')) {
    return { code: 200, message: 'success', data: mockConversationStats }
  }
  const { data } = await api.get('/admin/conversations/stats')
  return data
}

export async function fetchAdminConversations(
  keyword?: string,
  status?: string,
): Promise<ApiResponse<PaginatedData<AdminConversation>>> {
  if (isMockMode('admin')) {
    await delay(200)
    return { code: 200, message: 'success', data: mockConversationsList(keyword, status) }
  }
  const { data } = await api.get('/admin/conversations', { params: { keyword, status } })
  return data
}

export async function fetchAdminConversationDetail(
  sessionId: string,
): Promise<ApiResponse<AdminConversationDetail>> {
  if (isMockMode('admin')) {
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
  if (isMockMode('admin')) {
    await delay(150)
    return { code: 200, message: 'success', data: { ...mockSystemConfig } }
  }
  const { data } = await api.get('/admin/settings')
  return data
}

export async function updateSystemConfig(config: Partial<SystemConfig>): Promise<ApiResponse<SystemConfig>> {
  if (isMockMode('admin')) {
    await delay(300)
    return { code: 200, message: 'success', data: mockUpdateSystemConfig(config) }
  }
  const { data } = await api.put('/admin/settings', config)
  return data
}

export async function exportConversations(
  keyword?: string,
  status?: string,
  sessionIds?: string[],
): Promise<ApiResponse<{ download_url: string }>> {
  if (isMockMode('admin')) {
    await delay(300)
    return {
      code: 200,
      message: 'success',
      data: { download_url: '/api/admin/conversations/export/file?token=mock' },
    }
  }
  const params: Record<string, string | undefined> = { keyword, status }
  if (sessionIds?.length) {
    params.session_ids = sessionIds.join(',')
  }
  const { data } = await api.get('/admin/conversations/export', { params })
  return data
}

function escapeCsvCell(value: string | number): string {
  const text = String(value)
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`
  }
  return text
}

/** 将选中的会话列表导出为 CSV Blob（前端直接生成，避免二次下载路径问题） */
export function buildConversationsCsvBlob(rows: AdminConversation[]): Blob {
  const header = ['会话ID', '用户', '工号', '标题', '状态', '消息数', '创建时间', '更新时间']
  const lines = [
    header.join(','),
    ...rows.map((c) =>
      [
        c.id,
        c.user.display_name,
        c.user.employee_id,
        c.title,
        c.status,
        c.message_count,
        c.created_at,
        c.updated_at,
      ]
        .map(escapeCsvCell)
        .join(','),
    ),
  ]
  return new Blob(['\ufeff', lines.join('\n')], { type: 'text/csv;charset=utf-8' })
}

export function downloadCsvBlob(blob: Blob, filename = 'conversations.csv') {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadExportFile(downloadUrl: string): Promise<Blob> {
  // downloadUrl 形如 /api/admin/conversations/export/file?token=xxx
  // api baseURL 为 /api，需使用相对路径 admin/...（不能有前导 /）
  let path = downloadUrl
  if (path.startsWith('/api/')) {
    path = path.slice(5)
  } else if (path.startsWith('/api')) {
    path = path.slice(4).replace(/^\//, '')
  } else if (path.startsWith('/')) {
    path = path.slice(1)
  }
  const { data } = await api.get(path, { responseType: 'blob' })
  if (data.type?.includes('json')) {
    const text = await data.text()
    const err = JSON.parse(text) as { message?: string }
    throw new Error(err.message || '导出失败')
  }
  return data
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export type { AdminDocument, AdminQA, AdminConversation, AdminConversationDetail, ConversationStats, SystemConfig }
