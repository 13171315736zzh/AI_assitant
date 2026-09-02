<script setup lang="ts">
import { onMounted, ref, type ComponentPublicInstance } from 'vue'
import type { ProjectMapping } from '@/services/adminService'
import {
  createProjectMapping,
  deleteProjectMapping,
  downloadProjectMappingExport,
  downloadProjectMappingTemplate,
  fetchProjectMappings,
  importProjectMappings,
  updateProjectMapping,
} from '@/services/adminService'

const DRAFT_ID_PREFIX = 'draft:'

type EditableField =
  | 'project_name'
  | 'aliases'
  | 'city'
  | 'district'
  | 'address'
  | 'policy_city'
  | 'remark'

const EDITABLE_FIELDS: EditableField[] = [
  'project_name',
  'aliases',
  'city',
  'district',
  'address',
  'policy_city',
  'remark',
]

const FIELD_LABELS: Record<EditableField, string> = {
  project_name: '项目名称',
  aliases: '别名',
  city: '所在城市',
  district: '区县',
  address: '详细地址',
  policy_city: '标准城市',
  remark: '备注',
}

const items = ref<ProjectMapping[]>([])
const keyword = ref('')
const loading = ref(false)
const importing = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const replaceOnImport = ref(false)

const editing = ref<{ id: string; field: EditableField } | null>(null)
const editValue = ref('')
const savingKey = ref<string | null>(null)
const editInput = ref<HTMLInputElement | null>(null)
const adding = ref(false)

function isDraftRow(row: ProjectMapping) {
  return row.id.startsWith(DRAFT_ID_PREFIX)
}

function createDraftRow(): ProjectMapping {
  return {
    id: `${DRAFT_ID_PREFIX}${Date.now()}`,
    project_name: '',
    aliases: '',
    city: '',
    district: '',
    address: '',
    policy_city: '',
    remark: '',
    updated_by: '',
    updated_at: '',
  }
}

function cellKey(id: string, field: EditableField) {
  return `${id}:${field}`
}

function isEditing(id: string, field: EditableField) {
  return editing.value?.id === id && editing.value.field === field
}

function isSaving(id: string, field: EditableField) {
  return savingKey.value === cellKey(id, field)
}

function displayValue(value: string) {
  return value?.trim() ? value : '—'
}

async function load() {
  loading.value = true
  try {
    const res = await fetchProjectMappings(keyword.value.trim() || undefined)
    if (res.code === 200) items.value = res.data.items
  } finally {
    loading.value = false
  }
}

onMounted(load)

function pickFile() {
  fileInput.value?.click()
}

async function handleImport(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importing.value = true
  try {
    const res = await importProjectMappings(file, replaceOnImport.value)
    if (res.code === 200) {
      const r = res.data
      const errHint = r.errors.length ? `\n\n部分行失败：\n${r.errors.slice(0, 3).join('\n')}` : ''
      alert(`导入完成：新增 ${r.imported} 条，更新 ${r.updated} 条，跳过 ${r.skipped} 条${errHint}`)
      await load()
    } else {
      alert(res.message || '导入失败')
    }
  } finally {
    importing.value = false
    input.value = ''
  }
}

async function handleDownloadTemplate() {
  await downloadProjectMappingTemplate()
}

async function handleExport() {
  await downloadProjectMappingExport()
}

async function handleDelete(id: string, name: string) {
  if (id.startsWith(DRAFT_ID_PREFIX)) {
    items.value = items.value.filter((item) => item.id !== id)
    if (editing.value?.id === id) cancelEdit()
    return
  }
  if (!confirm(`确认删除「${name}」映射？`)) return
  const res = await deleteProjectMapping(id)
  if (res.code === 200) await load()
  else alert(res.message || '删除失败')
}

async function handleAddRow() {
  if (adding.value || savingKey.value) return
  if (editing.value) {
    const prevRow = items.value.find((item) => item.id === editing.value!.id)
    if (prevRow) await commitEdit(prevRow)
  }

  const existingDraft = items.value.find(isDraftRow)
  if (existingDraft) {
    void startEdit(existingDraft, 'project_name')
    return
  }

  const draft = createDraftRow()
  items.value.unshift(draft)
  await startEdit(draft, 'project_name')
}

async function persistDraftRow(row: ProjectMapping) {
  if (!row.project_name.trim()) return

  adding.value = true
  savingKey.value = `draft:${row.id}`
  try {
    const res = await createProjectMapping({
      project_name: row.project_name.trim(),
      aliases: row.aliases?.trim() ?? '',
      city: row.city?.trim() ?? '',
      district: row.district?.trim() ?? '',
      address: row.address?.trim() ?? '',
      policy_city: row.policy_city?.trim() ?? '',
      remark: row.remark?.trim() ?? '',
    })
    if (res.code === 200) {
      const idx = items.value.findIndex((item) => item.id === row.id)
      if (idx >= 0) items.value[idx] = res.data
    } else {
      alert(res.message || '创建失败')
    }
  } catch (err: unknown) {
    const message =
      (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
      '创建失败，请稍后重试'
    alert(message)
  } finally {
    adding.value = false
    if (savingKey.value === `draft:${row.id}`) savingKey.value = null
  }
}

async function startEdit(row: ProjectMapping, field: EditableField) {
  if (savingKey.value) return
  if (editing.value) {
    const prevRow = items.value.find((item) => item.id === editing.value!.id)
    if (prevRow) await commitEdit(prevRow)
    else cancelEdit()
  }
  if (savingKey.value) return
  editing.value = { id: row.id, field }
  editValue.value = row[field] ?? ''
}

function focusEditInput(el: Element | ComponentPublicInstance | null) {
  if (!el || !(el instanceof HTMLInputElement)) return
  editInput.value = el
  el.focus()
  el.select()
}

function cancelEdit() {
  if (editing.value) {
    const row = items.value.find((item) => item.id === editing.value!.id)
    if (
      row &&
      isDraftRow(row) &&
      !row.project_name.trim() &&
      editing.value.field === 'project_name' &&
      !editValue.value.trim()
    ) {
      items.value = items.value.filter((item) => item.id !== row.id)
    }
  }
  editing.value = null
  editValue.value = ''
}

async function commitEdit(row: ProjectMapping) {
  if (!editing.value || editing.value.id !== row.id) return

  const field = editing.value.field
  const trimmed = editValue.value.trim()
  const original = (row[field] ?? '').trim()

  if (field === 'project_name' && !trimmed) {
    alert('项目名称不能为空')
    editInput.value?.focus()
    return
  }

  if (trimmed === original) {
    cancelEdit()
    return
  }

  if (isDraftRow(row)) {
    row[field] = trimmed
    cancelEdit()
    if (row.project_name.trim()) {
      await persistDraftRow(row)
    }
    return
  }

  const key = cellKey(row.id, field)
  savingKey.value = key
  try {
    const res = await updateProjectMapping(row.id, { [field]: trimmed })
    if (res.code === 200) {
      const idx = items.value.findIndex((item) => item.id === row.id)
      if (idx >= 0) items.value[idx] = res.data
      cancelEdit()
    } else {
      alert(res.message || '保存失败')
    }
  } catch (err: unknown) {
    const message =
      (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
      '保存失败，请稍后重试'
    alert(message)
  } finally {
    if (savingKey.value === key) savingKey.value = null
  }
}

function handleEditKeydown(event: KeyboardEvent, row: ProjectMapping) {
  if (event.key === 'Enter') {
    event.preventDefault()
    void commitEdit(row)
  } else if (event.key === 'Escape') {
    event.preventDefault()
    cancelEdit()
  }
}

function handleCellClick(row: ProjectMapping, field: EditableField) {
  if (isEditing(row.id, field)) return
  void startEdit(row, field)
}
</script>

<template>
  <div class="admin-page">
    <header class="page-header">
      <div>
        <h1>项目城市映射</h1>
        <p class="subtitle">
          维护项目名称与出差地点对应关系，对话中将自动解析（如「燕宝能源」→ 呼伦贝尔市海拉尔区燕宝能源大厦）
        </p>
      </div>
      <div class="header-actions">
        <button type="button" class="btn-secondary" @click="handleDownloadTemplate">下载模板</button>
        <button type="button" class="btn-secondary" @click="handleExport">导出 Excel</button>
        <label class="replace-check">
          <input v-model="replaceOnImport" type="checkbox" />
          导入时覆盖全部
        </label>
        <button type="button" class="btn-primary" :disabled="importing" @click="pickFile">
          {{ importing ? '导入中…' : '上传 Excel' }}
        </button>
        <input
          ref="fileInput"
          type="file"
          accept=".xlsx,.xlsm"
          class="hidden-input"
          @change="handleImport"
        />
      </div>
    </header>

    <div class="toolbar">
      <input
        v-model="keyword"
        type="search"
        class="search-input"
        placeholder="搜索项目名称、别名、城市…"
        @keyup.enter="load"
      />
      <button type="button" class="btn-secondary" @click="load">搜索</button>
    </div>

    <div class="table-toolbar">
      <button type="button" class="btn-secondary" :disabled="adding" @click="handleAddRow">
        {{ adding ? '创建中…' : '+ 新增' }}
      </button>
      <p class="edit-hint">点击表格单元格可直接编辑，Enter 保存，Esc 取消</p>
    </div>

    <div v-if="loading" class="loading">加载中…</div>

    <div v-else class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>项目名称</th>
            <th>别名</th>
            <th>所在城市</th>
            <th>区县</th>
            <th>详细地址</th>
            <th>标准城市</th>
            <th>备注</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td colspan="8" class="empty">暂无数据，请下载模板填写后上传</td>
          </tr>
          <tr v-for="row in items" :key="row.id" :class="{ 'draft-row': isDraftRow(row) }">
            <td
              v-for="field in EDITABLE_FIELDS"
              :key="field"
              class="editable-cell"
              :class="{
                editing: isEditing(row.id, field),
                saving: isSaving(row.id, field),
                name: field === 'project_name',
              }"
              :title="`点击编辑${FIELD_LABELS[field]}`"
              @click="handleCellClick(row, field)"
            >
              <input
                v-if="isEditing(row.id, field)"
                :ref="focusEditInput"
                v-model="editValue"
                class="cell-input"
                :placeholder="FIELD_LABELS[field]"
                @blur="commitEdit(row)"
                @keydown="handleEditKeydown($event, row)"
                @click.stop
              />
              <span v-else class="cell-text">{{ displayValue(row[field]) }}</span>
            </td>
            <td class="actions-cell">
              <button
                type="button"
                class="link-danger"
                @click="handleDelete(row.id, row.project_name || '新项目')"
              >
                {{ isDraftRow(row) ? '取消' : '删除' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <section class="hint-box">
      <h3>Excel 表头说明</h3>
      <ul>
        <li><strong>项目名称</strong>：必填，如「燕宝能源」</li>
        <li><strong>项目别名</strong>：逗号分隔，如「雁宝,燕宝可视化二期」</li>
        <li><strong>所在城市 / 区县 / 详细地址</strong>：完整地点描述</li>
        <li><strong>标准城市</strong>：差旅政策匹配用，如「海拉尔」</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.admin-page {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.page-header h1 {
  margin: 0 0 6px;
  font-size: 22px;
}

.subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  max-width: 560px;
  line-height: 1.6;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.replace-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.hidden-input {
  display: none;
}

.toolbar {
  display: flex;
  gap: 10px;
}

.table-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.edit-hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.search-input {
  flex: 1;
  max-width: 360px;
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th,
.data-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  text-align: left;
}

.data-table th {
  background: var(--bg);
  font-weight: 600;
  white-space: nowrap;
}

.draft-row {
  background: rgba(246, 171, 0, 0.06);
}

.draft-row .editable-cell.editing {
  background: rgba(246, 171, 0, 0.12);
}

.editable-cell {
  cursor: pointer;
  transition: background 0.12s;
  min-width: 80px;
  max-width: 220px;
}

.editable-cell:hover {
  background: rgba(193, 25, 32, 0.04);
}

.editable-cell.editing {
  padding: 6px 8px;
  background: rgba(193, 25, 32, 0.06);
}

.editable-cell.saving {
  opacity: 0.6;
}

.editable-cell.name .cell-text {
  font-weight: 600;
}

.cell-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell-input {
  width: 100%;
  min-width: 72px;
  height: 28px;
  padding: 0 8px;
  border: 1px solid var(--primary);
  border-radius: 4px;
  font-size: 13px;
  color: var(--text);
  background: var(--surface);
  outline: none;
  box-shadow: 0 0 0 2px rgba(193, 25, 32, 0.12);
}

.actions-cell {
  white-space: nowrap;
}

.empty {
  text-align: center;
  color: var(--text-muted);
  padding: 32px !important;
}

.link-danger {
  border: none;
  background: none;
  color: var(--primary);
  cursor: pointer;
  font-size: 13px;
}

.loading {
  padding: 32px;
  text-align: center;
  color: var(--text-muted);
}

.hint-box {
  padding: 14px 16px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.hint-box h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.hint-box ul {
  margin: 0;
  padding-left: 20px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.btn-primary,
.btn-secondary {
  height: 36px;
  padding: 0 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
}

.btn-primary {
  border: none;
  background: var(--primary);
  color: #fff;
}

.btn-secondary {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
}
</style>
