import type { PaginatedData } from '@/types'

export interface QAItem {
  id: string
  question: string
  answer: string
  source_clause: string
  document_name: string
}

export interface DocumentItem {
  id: string
  filename: string
  file_type: string
  updated_at: string
}

export const mockQAItems: QAItem[] = [
  {
    id: 'qa_001',
    question: '鄂尔多斯住宿费标准是多少？',
    answer: '其他人员不超过300元/天',
    source_clause: '差旅管理办法·第十二条',
    document_name: '国家能源集团差旅管理办法2024修订版.pdf',
  },
  {
    id: 'qa_002',
    question: '出差伙食补助标准是多少？',
    answer: '国内出差伙食补助费标准为100元/天',
    source_clause: '差旅管理办法·第十五条',
    document_name: '国家能源集团差旅管理办法2024修订版.pdf',
  },
  {
    id: 'qa_003',
    question: '差旅报销需要哪些材料？',
    answer: '需提供差旅申请单、交通票据、住宿发票及费用明细表',
    source_clause: '报销实施细则·第三章',
    document_name: '差旅报销实施细则.docx',
  },
]

export const mockDocuments: DocumentItem[] = [
  {
    id: 'doc_001',
    filename: '国家能源集团差旅管理办法2024修订版.pdf',
    file_type: 'pdf',
    updated_at: '2026-03-01T00:00:00+08:00',
  },
  {
    id: 'doc_002',
    filename: '差旅报销实施细则.docx',
    file_type: 'docx',
    updated_at: '2026-03-15T00:00:00+08:00',
  },
]

export function mockKnowledgeQA(keyword?: string): PaginatedData<QAItem> {
  let items = mockQAItems
  if (keyword) {
    const q = keyword.toLowerCase()
    items = items.filter(
      (i) => i.question.includes(q) || i.answer.includes(q),
    )
  }
  return { items, total: items.length, page: 1, page_size: 20 }
}

export function mockKnowledgeDocuments(): PaginatedData<DocumentItem> {
  return { items: mockDocuments, total: mockDocuments.length, page: 1, page_size: 20 }
}

export function mockKnowledgeSearch(q: string) {
  const lower = q.toLowerCase()
  return {
    qa_results: mockQAItems.filter(
      (i) => i.question.includes(lower) || i.answer.includes(lower),
    ),
    document_results: mockDocuments.filter((d) => d.filename.includes(lower)),
  }
}
