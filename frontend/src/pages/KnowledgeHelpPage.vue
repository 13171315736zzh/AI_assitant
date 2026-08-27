<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import type { DocumentItem, QAItem } from '@/services/knowledgeService'
import { fetchKnowledgeDocuments, fetchKnowledgeQA, searchKnowledge } from '@/services/knowledgeService'

const keyword = ref('')
const qaList = ref<QAItem[]>([])
const documents = ref<DocumentItem[]>([])
const expandedId = ref<string | null>(null)
const activeCategory = ref('all')
const loading = ref(false)

const categories = [
  { id: 'all', label: '全部' },
  { id: 'policy', label: '制度文件' },
  { id: 'faq', label: '常见问题' },
  { id: 'guide', label: '流程指引' },
]

async function load() {
  loading.value = true
  try {
    const [qaRes, docRes] = await Promise.all([
      fetchKnowledgeQA(keyword.value || undefined),
      fetchKnowledgeDocuments(),
    ])
    if (qaRes.code === 200) qaList.value = qaRes.data.items
    if (docRes.code === 200) documents.value = docRes.data.items
  } finally {
    loading.value = false
  }
}

async function handleSearch() {
  if (!keyword.value.trim()) {
    await load()
    return
  }
  loading.value = true
  try {
    const res = await searchKnowledge(keyword.value)
    if (res.code === 200) {
      qaList.value = res.data.qa_results
      documents.value = res.data.document_results
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="app-shell help-page">
    <header class="top-header">
      <RouterLink to="/chat" class="back">← 返回对话</RouterLink>
      <div class="brand-line" />
    </header>

    <div class="help-body">
      <div class="search-bar">
        <input
          v-model="keyword"
          type="text"
          placeholder="搜索政策、报销标准…"
          @keyup.enter="handleSearch"
        />
        <button type="button" class="btn-primary" @click="handleSearch">搜索</button>
      </div>

      <div class="content-row">
        <aside class="category-nav">
          <button
            v-for="cat in categories"
            :key="cat.id"
            type="button"
            class="cat-item"
            :class="{ active: activeCategory === cat.id }"
            @click="activeCategory = cat.id"
          >
            {{ cat.label }}
          </button>
        </aside>

        <main class="main-content">
          <section class="section">
            <h2>常见问题</h2>
            <div v-if="loading" class="empty">加载中…</div>
            <div v-else class="qa-list">
              <div v-for="qa in qaList" :key="qa.id" class="qa-item">
                <button
                  type="button"
                  class="qa-question"
                  @click="expandedId = expandedId === qa.id ? null : qa.id"
                >
                  <span>{{ qa.question }}</span>
                  <span class="arrow">{{ expandedId === qa.id ? '▲' : '▼' }}</span>
                </button>
                <div v-if="expandedId === qa.id" class="qa-answer">
                  <p>{{ qa.answer }}</p>
                  <p class="source">来源：{{ qa.source_clause }} · {{ qa.document_name }}</p>
                </div>
              </div>
              <p v-if="!qaList.length" class="empty">暂无匹配结果</p>
            </div>
          </section>

          <section class="section">
            <h2>政策文档</h2>
            <div class="doc-list">
              <div v-for="doc in documents" :key="doc.id" class="doc-card">
                <div class="doc-info">
                  <span class="doc-name">{{ doc.filename }}</span>
                  <span class="doc-meta">{{ doc.file_type.toUpperCase() }} · 更新于 {{ doc.updated_at.slice(0, 10) }}</span>
                </div>
                <div class="doc-actions">
                  <button type="button" class="link-btn">在线查看</button>
                  <button type="button" class="link-btn">下载</button>
                </div>
              </div>
              <p v-if="!documents.length" class="empty">暂无文档</p>
            </div>
          </section>
        </main>
      </div>
    </div>
  </div>
</template>

<style scoped>
.help-page {
  flex-direction: column;
  background: var(--bg);
}

.top-header {
  background: var(--surface);
  padding: 16px 32px 0;
}

.back {
  font-size: 14px;
  color: var(--primary);
  display: inline-block;
  margin-bottom: 12px;
}

.brand-line {
  height: 2px;
  background: var(--gradient-brand);
}

.help-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px 32px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.search-bar {
  display: flex;
  gap: 12px;
  max-width: 560px;
}

.search-bar input {
  flex: 1;
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 14px;
}

.content-row {
  display: flex;
  gap: 24px;
  flex: 1;
  min-height: 0;
}

.category-nav {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cat-item {
  text-align: left;
  padding: 10px 16px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  font-size: 14px;
  color: var(--text-secondary);
  cursor: pointer;
}

.cat-item.active {
  background: #fdf2f2;
  color: var(--primary);
  font-weight: 600;
}

.main-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.section h2 {
  font-size: 18px;
  margin-bottom: 16px;
}

.qa-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.qa-item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.qa-question {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border: none;
  background: none;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
}

.qa-question:hover {
  background: var(--bg);
}

.qa-answer {
  padding: 0 16px 16px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.source {
  margin-top: 8px;
  font-size: 12px;
  color: var(--primary);
}

.doc-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.doc-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.doc-name {
  font-size: 14px;
  font-weight: 500;
  display: block;
}

.doc-meta {
  font-size: 12px;
  color: var(--text-muted);
}

.doc-actions {
  display: flex;
  gap: 12px;
}

.link-btn {
  border: none;
  background: none;
  color: var(--primary);
  font-size: 13px;
  cursor: pointer;
}

.empty {
  text-align: center;
  color: var(--text-muted);
  padding: 24px;
  font-size: 14px;
}
</style>
