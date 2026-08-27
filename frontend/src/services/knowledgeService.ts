import type { ApiResponse, PaginatedData } from '@/types'
import type { DocumentItem, QAItem } from '@/mocks/knowledge'
import { mockKnowledgeDocuments, mockKnowledgeQA, mockKnowledgeSearch } from '@/mocks/knowledge'
import api, { isMockMode } from './api'

export async function fetchKnowledgeQA(keyword?: string): Promise<ApiResponse<PaginatedData<QAItem>>> {
  if (isMockMode()) {
    await delay(150)
    return { code: 200, message: 'success', data: mockKnowledgeQA(keyword) }
  }
  const { data } = await api.get<ApiResponse<PaginatedData<QAItem>>>('/knowledge/qa', { params: { keyword } })
  return data
}

export async function fetchKnowledgeDocuments(): Promise<ApiResponse<PaginatedData<DocumentItem>>> {
  if (isMockMode()) {
    await delay(150)
    return { code: 200, message: 'success', data: mockKnowledgeDocuments() }
  }
  const { data } = await api.get<ApiResponse<PaginatedData<DocumentItem>>>('/knowledge/documents')
  return data
}

export async function searchKnowledge(q: string): Promise<
  ApiResponse<{ qa_results: QAItem[]; document_results: DocumentItem[] }>
> {
  if (isMockMode()) {
    await delay(200)
    return { code: 200, message: 'success', data: mockKnowledgeSearch(q) }
  }
  const { data } = await api.get('/knowledge/search', { params: { q } })
  return data
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export type { QAItem, DocumentItem }
