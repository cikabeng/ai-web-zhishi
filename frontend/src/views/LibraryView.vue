<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { toErrorMessage } from '@/api/client'
import {
  deleteDocument,
  fetchDocuments,
  previewChunks,
  reindexDocument,
  uploadDocument,
} from '@/api/library'
import type { LibraryDocument, LibraryStats, PreviewChunk } from '@/api/library'

const documents = ref<LibraryDocument[]>([])
const stats = ref<LibraryStats | null>(null)
const loading = ref(false)
const uploading = ref(false)
const error = ref('')
const dragActive = ref(false)

const previewVisible = ref(false)
const previewTitle = ref('')
const previewItems = ref<PreviewChunk[]>([])

const isEmpty = computed(() => !loading.value && documents.value.length === 0)

function statusMeta(status: LibraryDocument['status']) {
  if (status === 'indexed') return { text: '已索引', type: 'success' as const }
  if (status === 'failed') return { text: '失败', type: 'danger' as const }
  return { text: '处理中', type: 'warning' as const }
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const payload = await fetchDocuments()
    documents.value = payload.documents
    stats.value = payload.stats
  } catch (cause) {
    error.value = toErrorMessage(cause)
  } finally {
    loading.value = false
  }
}

async function handleFiles(files: FileList | null) {
  if (!files || !files.length) return
  uploading.value = true
  error.value = ''
  try {
    for (const file of Array.from(files)) {
      const result = await uploadDocument(file)
      if (result.duplicate) {
        ElMessage.info(`${result.document.name} 已存在，跳过重复索引`)
      } else if (result.document.status === 'failed') {
        ElMessage.error(`${result.document.name} 解析失败：${result.document.error}`)
      } else {
        ElMessage.success(`${result.document.name} 已入库，${result.document.chunks} 个片段`)
      }
    }
    await refresh()
  } catch (cause) {
    error.value = toErrorMessage(cause)
  } finally {
    uploading.value = false
  }
}

function onPick(event: Event) {
  const input = event.target as HTMLInputElement
  void handleFiles(input.files)
  input.value = ''
}

function onDrop(event: DragEvent) {
  dragActive.value = false
  void handleFiles(event.dataTransfer?.files ?? null)
}

async function remove(document: LibraryDocument) {
  try {
    await ElMessageBox.confirm(`删除《${document.name}》会同时移除它的向量索引，确定吗？`, '删除文档', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteDocument(document.id)
    ElMessage.success('已删除')
    await refresh()
  } catch (cause) {
    error.value = toErrorMessage(cause)
  }
}

async function reindex(document: LibraryDocument) {
  try {
    await reindexDocument(document.id)
    ElMessage.success(`《${document.name}》已重建索引`)
    await refresh()
  } catch (cause) {
    error.value = toErrorMessage(cause)
  }
}

async function openPreview(document: LibraryDocument) {
  previewTitle.value = document.name
  previewItems.value = []
  previewVisible.value = true
  try {
    previewItems.value = await previewChunks(document.id, 5)
  } catch (cause) {
    error.value = toErrorMessage(cause)
  }
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

onMounted(refresh)
</script>

<template>
  <div class="library-page">
    <header class="page-head">
      <div>
        <h2 class="page-title">课程知识库</h2>
        <p class="page-sub">
          上传课程资料后，系统会自动解析、分块并建立可检索索引。问答与截图分析都只依据这里的资料作答。
        </p>
      </div>
      <el-button :loading="loading" @click="refresh">刷新</el-button>
    </header>

    <section class="stats">
      <article class="stat">
        <span class="stat-label">文档</span>
        <strong class="stat-value">{{ stats?.documents ?? 0 }}</strong>
        <span class="stat-hint">已索引 {{ stats?.indexed ?? 0 }} 篇</span>
      </article>
      <article class="stat">
        <span class="stat-label">片段</span>
        <strong class="stat-value">{{ stats?.chunks ?? 0 }}</strong>
        <span class="stat-hint">检索的最小单位</span>
      </article>
      <article class="stat">
        <span class="stat-label">字符</span>
        <strong class="stat-value">{{ (stats?.chars ?? 0).toLocaleString() }}</strong>
        <span class="stat-hint">已解析正文总量</span>
      </article>
      <article class="stat">
        <span class="stat-label">状态</span>
        <strong class="stat-value" :class="stats?.status === 'ready' ? 'ok' : 'warn'">
          {{ stats?.status === 'ready' ? '就绪' : '空库' }}
        </strong>
        <span class="stat-hint">失败 {{ stats?.failed ?? 0 }} 篇</span>
      </article>
    </section>

    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />

    <section class="card">
      <label
        class="dropzone"
        :class="{ dragging: dragActive }"
        @dragover.prevent="dragActive = true"
        @dragleave.prevent="dragActive = false"
        @drop.prevent="onDrop"
      >
        <input type="file" accept=".pdf,.docx,.txt,.md" multiple hidden @change="onPick" />
        <span class="drop-icon">＋</span>
        <span class="drop-title">{{ uploading ? '正在解析并建立索引…' : '点击或拖拽课程资料到这里' }}</span>
        <span class="drop-hint">支持 PDF / DOCX / TXT / Markdown，单个文件不超过 20 MB</span>
      </label>
    </section>

    <section class="card">
      <div class="row row-between">
        <h3 class="card-title">文档列表</h3>
        <span class="muted small">删除会同时清理向量索引</span>
      </div>

      <div v-if="isEmpty" class="empty">
        <p>知识库还是空的。</p>
        <p class="muted small">先上传 1–3 份课程资料，然后去「分层教学」或「报错分析」提问，回答会带上这里的引用。</p>
      </div>

      <div v-else-if="loading && !documents.length" class="empty">加载中…</div>

      <el-table v-else :data="documents" style="width: 100%" row-key="id">
        <el-table-column prop="name" label="文件名" min-width="180" show-overflow-tooltip />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).text }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunks" label="片段" width="80" />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column label="页码" width="80">
          <template #default="{ row }">{{ row.pages || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button text size="small" :disabled="row.status !== 'indexed'" @click="openPreview(row)">预览</el-button>
            <el-button text size="small" :disabled="row.status === 'parsing'" @click="reindex(row)">重建</el-button>
            <el-button text size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <el-table-column label="错误信息" min-width="180">
          <template #default="{ row }">
            <span v-if="row.error" class="error-text">{{ row.error }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="previewVisible" :title="`分块预览 · ${previewTitle}`" width="720px">
      <div v-if="!previewItems.length" class="muted">没有可预览的片段。</div>
      <article v-for="(chunk, index) in previewItems" :key="index" class="chunk">
        <header class="chunk-head">
          <span class="chunk-index">#{{ chunk.ordinal }}</span>
          <span v-if="chunk.page > 0" class="chunk-page">第 {{ chunk.page }} 页</span>
          <span v-if="chunk.heading" class="chunk-heading">{{ chunk.heading }}</span>
        </header>
        <p class="chunk-text">{{ chunk.text }}</p>
      </article>
    </el-dialog>
  </div>
</template>

<style scoped>
.library-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-title {
  color: var(--c-text-strong);
  font-size: 22px;
  font-weight: 700;
}

.page-sub {
  max-width: 720px;
  margin-top: 6px;
  color: var(--c-text-muted);
  font-size: 14px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  background: var(--c-surface);
  box-shadow: var(--shadow-card);
}

.stat-label {
  color: var(--c-text-muted);
  font-size: 12.5px;
}

.stat-value {
  color: var(--c-text-strong);
  font-size: 22px;
  font-weight: 700;
}

.stat-value.ok {
  color: var(--c-success);
  font-size: 18px;
}

.stat-value.warn {
  color: var(--c-warn);
  font-size: 18px;
}

.stat-hint {
  color: var(--c-text-subtle);
  font-size: 11.5px;
}

.card {
  padding: 20px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  background: var(--c-surface);
  box-shadow: var(--shadow-card);
}

.card-title {
  color: var(--c-text-strong);
  font-size: 15px;
  font-weight: 700;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}

.row-between {
  justify-content: space-between;
  margin-top: 0;
}

.muted {
  color: var(--c-text-muted);
}

.small {
  font-size: 12.5px;
}

.dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 150px;
  padding: 20px;
  border: 1.5px dashed var(--c-border);
  border-radius: var(--radius-md);
  background: #fbfdff;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.dropzone:hover,
.dropzone.dragging {
  border-color: var(--c-brand-500);
  background: var(--c-brand-50);
}

.drop-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--c-brand-50);
  color: var(--c-brand-700);
  font-size: 20px;
}

.drop-title {
  color: var(--c-text-strong);
  font-size: 14px;
  font-weight: 600;
}

.drop-hint {
  color: var(--c-text-subtle);
  font-size: 12.5px;
}

.empty {
  margin-top: 14px;
  padding: 26px 16px;
  border: 1px dashed var(--c-border);
  border-radius: var(--radius-md);
  color: var(--c-text-muted);
  font-size: 13px;
  text-align: center;
}

.error-text {
  color: var(--c-danger);
  font-size: 12px;
}

.chunk {
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: #fbfdff;
}

.chunk-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
}

.chunk-index {
  color: var(--c-brand-700);
  font-weight: 700;
}

.chunk-page {
  padding: 1px 7px;
  border-radius: 999px;
  background: #eef2f7;
  color: var(--c-text-muted);
}

.chunk-heading {
  color: var(--c-text-subtle);
}

.chunk-text {
  margin-top: 8px;
  color: var(--c-text);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

@media (max-width: 860px) {
  .stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
