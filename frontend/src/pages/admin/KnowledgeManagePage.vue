<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DocumentPreviewModal from '@/components/chat/DocumentPreviewModal.vue'
import type { MessageSource } from '@/types'
import type { AdminDocument, AdminQA } from '@/services/adminService'
import {
  deleteAdminDocument,
  fetchAdminDocuments,
  fetchAdminQA,
  fetchDocumentProgress,
  reindexAdminDocument,
  searchTest,
  uploadAdminDocument,
} from '@/services/adminService'

const activeTab = ref<'docs' | 'qa' | 'search'>('docs')
const documents = ref<AdminDocument[]>([])
const qaList = ref<AdminQA[]>([])
const qaKeyword = ref('')
const searchQuery = ref('')
const searchResults = ref<Array<{ question: string; answer: string; similarity: number; source_clause: string }>>([])
const loading = ref(false)
const previewSource = ref<MessageSource | null>(null)

const fileInput = ref<HTMLInputElement | null>(null)
const pollingDocIds = ref<Set<string>>(new Set())
const docProgressStage = ref<Record<string, string>>({})

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function applyDocumentProgress(
  docId: string,
  status: string,
  stage: string,
  percent: number,
) {
  docProgressStage.value = { ...docProgressStage.value, [docId]: stage }
  const idx = documents.value.findIndex((d) => d.id === docId)
  if (idx < 0) return
  documents.value[idx] = {
    ...documents.value[idx],
    status: status as AdminDocument['status'],
    progress_percent: status === 'ready' ? undefined : percent,
  }
}

async function refreshDocsSilent() {
  const res = await fetchAdminDocuments()
  if (res.code === 200) documents.value = res.data.items
}

async function pollDocument(docId: string) {
  if (pollingDocIds.value.has(docId)) return
  pollingDocIds.value = new Set([...pollingDocIds.value, docId])
  try {
    for (let i = 0; i < 400; i++) {
      const res = await fetchDocumentProgress(docId)
      if (res.code === 200 && res.data) {
        const { status, progress } = res.data
        applyDocumentProgress(docId, status, progress.stage, progress.percent)
        if (status === 'ready') {
          await refreshDocsSilent()
          await loadQA()
          alert('文档已入库，QA 已自动生成')
          return
        }
        if (status === 'failed') {
          await refreshDocsSilent()
          alert('文档处理失败，请重试或重新上传')
          return
        }
      }
      const stage = docProgressStage.value[docId] ?? ''
      await delay(stage.startsWith('ocr:') ? 1000 : 1500)
    }
    alert('文档处理超时，请稍后刷新页面查看状态')
  } finally {
    const next = new Set(pollingDocIds.value)
    next.delete(docId)
    pollingDocIds.value = next
  }
}

function pickFile() {
  fileInput.value?.click()
}

async function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  loading.value = true
  try {
    const res = await uploadAdminDocument(file)
    if (res.code === 200) {
      await loadDocs()
      void pollDocument(res.data.id)
    } else {
      alert(res.message || '上传失败')
    }
  } finally {
    loading.value = false
    input.value = ''
  }
}

async function removeDoc(docId: string) {
  if (!confirm('确定删除该文档及关联 QA？')) return
  loading.value = true
  try {
    const res = await deleteAdminDocument(docId)
    if (res.code === 200) {
      await loadDocs()
    } else {
      alert(res.message || '删除失败')
    }
  } finally {
    loading.value = false
  }
}

async function regenerateDoc(doc: AdminDocument) {
  loading.value = true
  try {
    const res = await reindexAdminDocument(doc.id)
    if (res.code === 200) {
      await loadDocs()
      void pollDocument(doc.id)
    } else {
      alert(res.message || '重新解析失败')
    }
  } finally {
    loading.value = false
  }
}

function previewDoc(doc: AdminDocument) {
  if (doc.file_type !== 'pdf') {
    alert('当前仅支持在线预览 PDF')
    return
  }
  previewSource.value = {
    document_id: doc.id,
    filename: doc.filename,
    clause: '',
  }
}

async function loadDocs() {
  loading.value = true
  try {
    const res = await fetchAdminDocuments()
    if (res.code === 200) documents.value = res.data.items
  } finally {
    loading.value = false
  }
}

async function loadQA() {
  loading.value = true
  try {
    const res = await fetchAdminQA(qaKeyword.value || undefined)
    if (res.code === 200) qaList.value = res.data.items
  } finally {
    loading.value = false
  }
}

async function runSearch() {
  if (!searchQuery.value.trim()) return
  loading.value = true
  try {
    const res = await searchTest(searchQuery.value)
    if (res.code === 200) searchResults.value = res.data.results
  } finally {
    loading.value = false
  }
}

function switchTab(tab: typeof activeTab.value) {
  activeTab.value = tab
  if (tab === 'docs') loadDocs()
  else if (tab === 'qa') loadQA()
}

onMounted(loadDocs)

function statusLabel(status: AdminDocument['status'] | string) {
  const map: Record<string, string> = {
    ready: '已入库',
    uploading: '上传中',
    parsing: '解析中',
    indexing: '索引中',
    ocr: 'OCR 识别中',
    qa_generating: 'QA 生成中',
    failed: '失败',
    no_text: '无法识别文本',
    ocr_done: 'OCR 完成',
  }
  return map[status] ?? status
}

function displayStatus(doc: AdminDocument) {
  const stage = docProgressStage.value[doc.id] ?? ''
  const ocrMatch = stage.match(/^ocr:(\d+)\/(\d+)$/)
  if (ocrMatch) {
    return `OCR 识别中 (${ocrMatch[1]}/${ocrMatch[2]})`
  }
  if (stage === 'ocr' || stage === 'ocr_done') return statusLabel('ocr')
  return statusLabel(doc.status)
}

function statusClass(status: AdminDocument['status']) {
  if (status === 'ready') return 'success'
  if (status === 'failed') return 'error'
  return 'warning'
}
</script>

<template>
  <div class="admin-page">
    <header class="page-header">
      <h1>知识库管理</h1>
    </header>

    <div class="tabs">
      <button
        type="button"
        class="tab"
        :class="{ active: activeTab === 'docs' }"
        @click="switchTab('docs')"
      >
        文档管理
      </button>
      <button
        type="button"
        class="tab"
        :class="{ active: activeTab === 'qa' }"
        @click="switchTab('qa')"
      >
        QA 列表
      </button>
      <button
        type="button"
        class="tab"
        :class="{ active: activeTab === 'search' }"
        @click="switchTab('search')"
      >
        检索测试
      </button>
    </div>

    <!-- 文档管理 -->
    <div v-if="activeTab === 'docs'" class="tab-content">
      <div class="upload-zone">
        <p>拖拽上传 PDF、Word 文件到此处</p>
        <p class="sub">支持 PDF、Word 格式，单文件不超过 50MB</p>
        <input ref="fileInput" type="file" accept=".pdf,.docx" hidden @change="handleFileChange" />
        <button type="button" class="btn-primary" @click="pickFile">选择文件</button>
      </div>

      <div class="table">
        <div class="table-head">
          <span>文件名</span>
          <span>类型</span>
          <span>状态</span>
          <span>上传人</span>
          <span>时间</span>
          <span>操作</span>
        </div>
        <div v-for="doc in documents" :key="doc.id" class="table-row">
          <span class="filename">{{ doc.filename }}</span>
          <span>{{ doc.file_type.toUpperCase() }}</span>
          <span>
            <span class="status-tag" :class="statusClass(doc.status)">
              {{ displayStatus(doc) }}
              <template v-if="doc.progress_percent != null && doc.status !== 'ready'">
                {{ doc.progress_percent }}%
              </template>
            </span>
          </span>
          <span>{{ doc.uploaded_by }}</span>
          <span>{{ doc.created_at.slice(0, 10) }}</span>
          <span class="actions">
            <button
              v-if="doc.status === 'ready' && doc.file_type === 'pdf'"
              type="button"
              class="link-btn"
              @click="previewDoc(doc)"
            >
              查看
            </button>
            <button
              v-if="doc.status === 'ready' || doc.status === 'failed'"
              type="button"
              class="link-btn"
              @click="regenerateDoc(doc)"
            >
              重新解析
            </button>
            <button type="button" class="link-btn danger" @click="removeDoc(doc.id)">删除</button>
          </span>
        </div>
      </div>
    </div>

    <!-- QA 列表 -->
    <div v-else-if="activeTab === 'qa'" class="tab-content">
      <div class="filter-bar">
        <input v-model="qaKeyword" type="text" placeholder="搜索问题…" @keyup.enter="loadQA" />
        <button type="button" class="btn-secondary" @click="loadQA">搜索</button>
      </div>
      <div class="table">
        <div class="table-head qa-head">
          <span>问题</span>
          <span>答案摘要</span>
          <span>来源条款</span>
        </div>
        <div v-for="qa in qaList" :key="qa.id" class="table-row qa-row">
          <span>{{ qa.question }}</span>
          <span>{{ qa.answer }}</span>
          <span>{{ qa.source_clause }}</span>
        </div>
      </div>
    </div>

    <!-- 检索测试 -->
    <div v-else class="tab-content">
      <div class="search-test">
        <input v-model="searchQuery" type="text" placeholder="输入测试 Query，如：鄂尔多斯住宿费标准" />
        <button type="button" class="btn-primary" @click="runSearch">检索</button>
      </div>
      <div v-if="searchResults.length" class="results">
        <div v-for="(r, i) in searchResults" :key="i" class="result-card">
          <div class="result-head">
            <span class="type">QA 命中</span>
            <span class="sim">相似度 {{ (r.similarity * 100).toFixed(0) }}%</span>
          </div>
          <p class="q">{{ r.question }}</p>
          <p class="a">{{ r.answer }}</p>
          <p class="src">{{ r.source_clause }}</p>
        </div>
      </div>
      <p v-else-if="!loading" class="empty">输入 Query 开始检索测试</p>
    </div>

    <DocumentPreviewModal :source="previewSource" @close="previewSource = null" />
  </div>
</template>

<style scoped>
.admin-page {
  padding: 24px 32px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.page-header h1 {
  font-size: 24px;
}

.tabs {
  display: flex;
  gap: 24px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
}

.tab {
  padding: 12px 0;
  border: none;
  background: none;
  font-size: 14px;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}

.tab.active {
  color: var(--primary);
  font-weight: 600;
  border-bottom-color: var(--primary);
}

.upload-zone {
  background: var(--surface);
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  padding: 32px;
  text-align: center;
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.upload-zone .sub {
  font-size: 12px;
  color: var(--text-muted);
}

.table {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.table-head,
.table-row {
  display: grid;
  grid-template-columns: 2fr 80px 120px 80px 100px 120px;
  padding: 12px 16px;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.qa-head,
.qa-row {
  grid-template-columns: 2fr 2fr 1fr;
}

.table-head {
  background: #fafbfc;
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 12px;
  border-bottom: 1px solid var(--border);
}

.table-row {
  border-bottom: 1px solid var(--border);
}

.table-row:last-child {
  border-bottom: none;
}

.filename {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.status-tag.success {
  background: #edfaf5;
  color: var(--success);
}

.status-tag.warning {
  background: #fff8e6;
  color: #92400e;
}

.status-tag.error {
  background: #fdf2f2;
  color: var(--primary);
}

.actions {
  display: flex;
  gap: 8px;
}

.link-btn {
  border: none;
  background: none;
  color: var(--primary);
  font-size: 13px;
  cursor: pointer;
}

.link-btn.danger {
  color: var(--text-muted);
}

.filter-bar,
.search-test {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 480px;
}

.filter-bar input,
.search-test input {
  flex: 1;
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 16px;
}

.result-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.type {
  font-size: 12px;
  color: var(--primary);
  font-weight: 600;
}

.sim {
  font-size: 12px;
  color: var(--success);
}

.q {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
}

.a {
  font-size: 13px;
  color: var(--text-secondary);
}

.src {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 8px;
}

.empty {
  text-align: center;
  color: var(--text-muted);
  padding: 32px;
}
</style>
