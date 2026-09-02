import type { ApiResponse, MessageSource, PaginatedData } from '@/types'
import { mockDocuments } from '@/mocks/knowledge'
import api, { isMockMode } from './api'

const FILENAME_TO_DOC_ID: Record<string, string> = Object.fromEntries(
  mockDocuments.map((d) => [d.filename, d.id]),
)

interface DocumentListItem {
  id: string
  filename: string
  file_type: string
}

let cachedDocuments: DocumentListItem[] | null = null

async function loadReadyDocuments(): Promise<DocumentListItem[]> {
  if (cachedDocuments) return cachedDocuments
  if (isMockMode('knowledge')) {
    cachedDocuments = mockDocuments.map((d) => ({
      id: d.id,
      filename: d.filename,
      file_type: d.file_type,
    }))
    return cachedDocuments
  }
  const { data } = await api.get<ApiResponse<PaginatedData<DocumentListItem>>>('/knowledge/documents', {
    params: { page_size: 100 },
  })
  cachedDocuments = data.data.items
  return cachedDocuments
}

function filenameKeywords(filename: string): string[] {
  const name = filename.replace(/\.(pdf|docx)$/i, '')
  const keys: string[] = []
  for (const token of ['差旅', '报销', '管理办法', '实施细则', '办公']) {
    if (name.includes(token)) keys.push(token)
  }
  if (!keys.length && name.length >= 4) keys.push(name.slice(0, 8))
  return keys
}

export async function resolveDocumentId(source: MessageSource): Promise<string | null> {
  const docs = await loadReadyDocuments()
  if (source.document_id && docs.some((d) => d.id === source.document_id)) {
    return source.document_id
  }
  const exact = docs.find((d) => d.filename === source.filename)
  if (exact) return exact.id
  const mockId = FILENAME_TO_DOC_ID[source.filename]
  if (mockId) return mockId
  for (const keyword of filenameKeywords(source.filename)) {
    const fuzzy = docs.find((d) => d.filename.includes(keyword) && d.file_type === 'pdf')
    if (fuzzy) return fuzzy.id
  }
  const fallback = docs.find((d) => d.file_type === 'pdf')
  return fallback?.id ?? null
}

export async function fetchDocumentBlob(documentId: string, filename?: string): Promise<Blob> {
  if (isMockMode('knowledge')) {
    const res = await fetch(`/documents/${documentId}.pdf`)
    if (!res.ok) throw new Error('download failed')
    const blob = await res.blob()
    return blob.type === 'application/pdf' ? blob : new Blob([blob], { type: 'application/pdf' })
  }

  const token = localStorage.getItem('token')
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  const query = filename ? `?filename=${encodeURIComponent(filename)}` : ''
  const res = await fetch(
    `${base}/knowledge/documents/${encodeURIComponent(documentId)}/download${query}`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  )
  if (!res.ok) {
    throw new Error('download failed')
  }
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    throw new Error('download failed')
  }
  const blob = await res.blob()
  if (blob.type === 'application/pdf') return blob
  return new Blob([blob], { type: 'application/pdf' })
}

export async function fetchDocumentPreviewUrl(source: MessageSource): Promise<string> {
  const documentId = await resolveDocumentId(source)
  if (!documentId) {
    throw new Error('document not found')
  }
  const blob = await fetchDocumentBlob(documentId, source.filename)
  return URL.createObjectURL(blob)
}

export async function downloadDocumentFile(documentId: string, filename: string): Promise<void> {
  const blob = await fetchDocumentBlob(documentId, filename)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export type { MessageSource }
