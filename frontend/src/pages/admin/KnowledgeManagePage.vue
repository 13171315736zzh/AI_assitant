<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { AdminDocument, AdminQA } from '@/services/adminService'
import {
  fetchAdminDocuments,
  fetchAdminQA,
  searchTest,
} from '@/services/adminService'

const activeTab = ref<'docs' | 'qa' | 'search'>('docs')
const documents = ref<AdminDocument[]>([])
const qaList = ref<AdminQA[]>([])
const qaKeyword = ref('')
const searchQuery = ref('')
const searchResults = ref<Array<{ question: string; answer: string; similarity: number; source_clause: string }>>([])
const loading = ref(false)

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

function statusLabel(status: AdminDocument['status']) {
  const map = {
    ready: '已入库',
    uploading: '上传中',
    parsing: '解析中',
    indexing: '索引中',
    failed: '失败',
  }
  return map[status]
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
        <button type="button" class="btn-primary">选择文件</button>
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
              {{ statusLabel(doc.status) }}
              <template v-if="doc.progress_percent"> {{ doc.progress_percent }}%</template>
            </span>
          </span>
          <span>{{ doc.uploaded_by }}</span>
          <span>{{ doc.created_at.slice(0, 10) }}</span>
          <span class="actions">
            <button type="button" class="link-btn">查看</button>
            <button type="button" class="link-btn danger">删除</button>
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
