import type { MessageSource } from '@/types'
import { mockDocuments } from '@/mocks/knowledge'
import api, { isMockMode } from './api'

const FILENAME_TO_DOC_ID: Record<string, string> = Object.fromEntries(
  mockDocuments.map((d) => [d.filename, d.id]),
)

export function resolveDocumentId(source: MessageSource): string | null {
  if (source.document_id) return source.document_id
  return FILENAME_TO_DOC_ID[source.filename] ?? null
}

export async function fetchDocumentBlob(documentId: string): Promise<Blob> {
  if (isMockMode('knowledge')) {
    const res = await fetch(`/documents/${documentId}.pdf`)
    if (!res.ok) throw new Error('download failed')
    return res.blob()
  }

  const token = localStorage.getItem('token')
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  const res = await fetch(`${base}/knowledge/documents/${encodeURIComponent(documentId)}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) {
    throw new Error('download failed')
  }
  return res.blob()
}

export async function fetchDocumentPreviewUrl(source: MessageSource): Promise<string> {
  const documentId = resolveDocumentId(source)
  if (!documentId) {
    throw new Error('document not found')
  }
  const blob = await fetchDocumentBlob(documentId)
  return URL.createObjectURL(blob)
}

export async function downloadDocumentFile(documentId: string, filename: string): Promise<void> {
  const blob = await fetchDocumentBlob(documentId)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export type { MessageSource }
