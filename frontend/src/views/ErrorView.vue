<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { toErrorMessage } from '@/api/client'
import { analyzeImage, analyzeText, fetchCapabilities, fetchSampleImage } from '@/api/errors'
import type { Capabilities, ErrorAnalysis } from '@/api/errors'
import { renderMarkdown } from '@/utils/markdown'

const router = useRouter()
const route = useRoute()

const mode = ref<'image' | 'text'>('image')
const capabilities = ref<Capabilities | null>(null)

const file = ref<File | null>(null)
const previewUrl = ref('')
const analysis = ref<ErrorAnalysis | null>(null)
const editableText = ref('')

const loading = ref(false)
const error = ref('')
const dragActive = ref(false)
const manualText = ref('')

const MAX_MB = 8
const ACCEPT = 'image/png,image/jpeg,image/webp'

const canAnalyzeImage = computed(() => !!file.value && !loading.value)
const canAnalyzeText = computed(() => manualText.value.trim().length >= 5 && !loading.value)
const ocrAvailable = computed(() => {
  const active = capabilities.value?.active
  return !!active && active !== 'none'
})

const parsedRows = computed(() => {
  const parsed = analysis.value?.parsed
  if (!parsed) return []
  return [
    { label: '异常类型', value: parsed.exception_type, warn: false },
    { label: '错误信息', value: parsed.message, warn: false },
    { label: '文件名', value: parsed.file, warn: false },
    {
      label: parsed.line_estimated ? '行号（识别，可能不准）' : '行号',
      value: parsed.line === null ? null : String(parsed.line),
      warn: parsed.line_estimated,
    },
    { label: '语言', value: parsed.language === 'unknown' ? null : parsed.language, warn: false },
    { label: '缺失字段', value: parsed.missing.length ? parsed.missing.join('、') : '无', warn: false },
  ]
})

function revokePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

function acceptFile(next: File | null) {
  error.value = ''
  analysis.value = null
  revokePreview()
  file.value = next
  if (next) {
    previewUrl.value = URL.createObjectURL(next)
  }
}

function onPick(event: Event) {
  const input = event.target as HTMLInputElement
  acceptFile(input.files?.[0] ?? null)
  input.value = ''
}

function onDrop(event: DragEvent) {
  dragActive.value = false
  const dropped = event.dataTransfer?.files?.[0] ?? null
  if (!dropped) return
  acceptFile(dropped)
}

function clientValidate(picked: File): string {
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(picked.type)) {
    return '只支持 PNG、JPEG、WEBP 三种图片格式'
  }
  if (picked.size > MAX_MB * 1024 * 1024) {
    return `图片不能超过 ${MAX_MB} MB`
  }
  return ''
}

async function runImageAnalysis() {
  if (!file.value) return
  const invalid = clientValidate(file.value)
  if (invalid) {
    error.value = invalid
    return
  }

  loading.value = true
  error.value = ''
  try {
    analysis.value = await analyzeImage(file.value)
    editableText.value = analysis.value.recognized_text
  } catch (cause) {
    error.value = toErrorMessage(cause)
  } finally {
    loading.value = false
  }
}

async function runTextAnalysis(edited: boolean) {
  const text = edited ? editableText.value : manualText.value
  if (text.trim().length < 5) {
    error.value = '报错内容太短，请补充完整'
    return
  }

  loading.value = true
  error.value = ''
  try {
    analysis.value = await analyzeText(text, edited)
    editableText.value = analysis.value.recognized_text
  } catch (cause) {
    error.value = toErrorMessage(cause)
  } finally {
    loading.value = false
  }
}

async function loadSample() {
  try {
    const blob = await fetchSampleImage()
    const sample = new File([blob], 'sample-error.png', { type: 'image/png' })
    acceptFile(sample)
    await runImageAnalysis()
  } catch (cause) {
    error.value = toErrorMessage(cause)
  }
}

function goTeaching() {
  const entry = analysis.value?.teaching_entry
  if (entry) void router.push(entry.path)
}

onMounted(async () => {
  try {
    capabilities.value = await fetchCapabilities()
  } catch {
    capabilities.value = null
  }

  if (route.query.demo === '1') {
    await loadSample()
  }
})

onBeforeUnmount(revokePreview)
</script>

<template>
  <div class="errors-page">
    <header class="page-head">
      <div>
        <h2 class="page-title">截图报错分析</h2>
        <p class="page-sub">
          上传报错截图，先识别文字、再解析字段，最后用课程知识库给出解释与排查步骤。
          识别结果可以修改后重新分析。
        </p>
      </div>
      <div class="capability">
        <span class="cap-dot" :class="{ on: ocrAvailable }"></span>
        <span v-if="ocrAvailable">OCR：{{ capabilities?.active }}</span>
        <span v-else>未配置 OCR</span>
      </div>
    </header>

    <div class="mode-switch">
      <button type="button" class="mode" :class="{ active: mode === 'image' }" @click="mode = 'image'">
        上传截图
      </button>
      <button type="button" class="mode" :class="{ active: mode === 'text' }" @click="mode = 'text'">
        手动粘贴报错
      </button>
    </div>

    <!-- 上传 -->
    <section v-if="mode === 'image'" class="card">
      <label
        class="dropzone"
        :class="{ dragging: dragActive, filled: !!file }"
        @dragover.prevent="dragActive = true"
        @dragleave.prevent="dragActive = false"
        @drop.prevent="onDrop"
      >
        <input type="file" :accept="ACCEPT" hidden @change="onPick" />
        <template v-if="!file">
          <span class="drop-icon">＋</span>
          <span class="drop-title">点击或拖拽报错截图到这里</span>
          <span class="drop-hint">支持 PNG / JPEG / WEBP，不超过 {{ MAX_MB }} MB</span>
        </template>
        <template v-else>
          <div class="preview">
            <img :src="previewUrl" alt="报错截图预览" />
            <div class="preview-meta">
              <span class="file-name">{{ file.name }}</span>
              <span class="muted small">{{ (file.size / 1024).toFixed(0) }} KB</span>
              <span class="muted small">点击可重新选择</span>
            </div>
          </div>
        </template>
      </label>

      <div class="row row-between">
        <div class="row-inline">
          <el-button text type="primary" size="small" @click="loadSample">载入示例截图</el-button>
          <span class="muted small">
            {{ ocrAvailable ? '识别结果会明确标注，行号可能不准，请核对' : '当前没有可用 OCR，请切到「手动粘贴报错」' }}
          </span>
        </div>
        <el-button type="primary" :loading="loading" :disabled="!canAnalyzeImage" @click="runImageAnalysis">
          {{ loading ? '识别并分析中…' : '开始识别并分析' }}
        </el-button>
      </div>
    </section>

    <!-- 手动粘贴 -->
    <section v-else class="card">
      <el-input
        v-model="manualText"
        type="textarea"
        :rows="7"
        maxlength="8000"
        show-word-limit
        resize="none"
        placeholder="把完整的报错信息粘贴到这里，例如：&#10;Traceback (most recent call last):&#10;  File &quot;demo.py&quot;, line 12, in &lt;module&gt;&#10;    print(info['score'])&#10;TypeError: 'NoneType' object is not subscriptable"
      />
      <div class="row row-between">
        <span class="muted small">没有截图也能用；粘贴后直接分析，同样会检索课程资料。</span>
        <el-button type="primary" :loading="loading" :disabled="!canAnalyzeText" @click="runTextAnalysis(false)">
          分析报错文本
        </el-button>
      </div>
    </section>

    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />

    <!-- 结果 -->
    <template v-if="analysis">
      <el-alert
        v-for="(warning, index) in analysis.warnings"
        :key="index"
        :title="warning"
        type="warning"
        :closable="false"
        show-icon
      />

      <section v-if="analysis.ocr" class="card">
        <div class="row row-between">
          <h3 class="card-title">识别结果（可修改）</h3>
          <span class="muted small">
            {{ analysis.ocr.provider }} ·
            {{ analysis.ocr.mean_confidence ? `置信度 ${(analysis.ocr.mean_confidence * 100).toFixed(0)}%` : '置信度未知' }}
          </span>
        </div>
        <el-input
          v-model="editableText"
          type="textarea"
          :rows="6"
          maxlength="8000"
          show-word-limit
          resize="none"
          class="recognized"
        />
        <div class="row row-between">
          <span class="muted small">改完点右边按钮，系统会用修正后的内容重新检索。</span>
          <el-button type="primary" plain :loading="loading" :disabled="loading" @click="runTextAnalysis(true)">
            用修正后的内容重新分析
          </el-button>
        </div>
      </section>

      <section class="card">
        <h3 class="card-title">解析结果</h3>
        <p class="muted small">
          项目分类：{{ analysis.category_label }} · 检索命中 {{ analysis.retrieval.hit_count }} 条
          <span v-if="analysis.parsed.line_estimated" class="badge-warn">行号来自识别，可能不准</span>
        </p>
        <dl class="parsed-grid">
          <div v-for="row in parsedRows" :key="row.label" class="parsed-item">
            <dt>{{ row.label }}</dt>
            <dd :class="{ warn: row.warn, empty: !row.value }">{{ row.value ?? '未识别' }}</dd>
          </div>
        </dl>
        <pre v-if="analysis.parsed.code_snippet" class="code-block"><code>{{ analysis.parsed.code_snippet }}</code></pre>
      </section>

      <section class="card">
        <h3 class="card-title">错误解释</h3>
        <div class="md" v-html="renderMarkdown(analysis.explanation)" />

        <h4 class="sub-title">可能原因</h4>
        <ul class="cause-list">
          <li v-for="(cause, index) in analysis.causes" :key="index">{{ cause }}</li>
        </ul>

        <h4 class="sub-title">排查步骤</h4>
        <ol class="step-list">
          <li v-for="(step, index) in analysis.steps" :key="index">{{ step }}</li>
        </ol>
      </section>

      <section class="card">
        <div class="row row-between">
          <h3 class="card-title">教材引用</h3>
          <span class="muted small">仅来自本次检索</span>
        </div>
        <p v-if="!analysis.citations.length" class="empty">
          没有检索到相关课程资料，上面的解释属于通用知识，请以课堂材料为准。
        </p>
        <ol v-else class="citation-list">
          <li v-for="citation in analysis.citations" :key="citation.chunk_id">
            <div class="cite-head">
              <span class="cite-index">[{{ citation.index }}]</span>
              <strong>《{{ citation.doc_name }}》</strong>
              <span class="cite-loc">{{ citation.location }}</span>
              <span class="cite-score">相关度 {{ (citation.score * 100).toFixed(0) }}%</span>
            </div>
            <p class="cite-text">{{ citation.snippet }}</p>
          </li>
        </ol>

        <div class="row actions">
          <el-button type="primary" @click="goTeaching">进入分层提示</el-button>
          <span class="muted small">会用当前报错内容打开教学页，从 L1 开始逐级引导。</span>
        </div>

        <p class="safety">安全说明：系统不会执行截图或文本中的任何代码，只做文字解析。</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.errors-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
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

.capability {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border: 1px solid var(--c-border);
  border-radius: 999px;
  background: #fff;
  color: var(--c-text-muted);
  font-size: 12.5px;
}

.cap-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--c-danger);
}

.cap-dot.on {
  background: var(--c-success);
}

.mode-switch {
  display: inline-flex;
  gap: 6px;
  padding: 4px;
  border: 1px solid var(--c-border);
  border-radius: 999px;
  background: #fff;
  width: fit-content;
}

.mode {
  padding: 7px 16px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--c-text);
  font-family: inherit;
  font-size: 13.5px;
  cursor: pointer;
}

.mode.active {
  background: var(--c-brand-50);
  color: var(--c-brand-700);
  font-weight: 600;
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
}

.row-inline {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.muted {
  color: var(--c-text-muted);
}

.small {
  font-size: 12.5px;
}

/* 上传区 */
.dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 180px;
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

.dropzone.filled {
  border-style: solid;
  align-items: stretch;
}

.drop-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: var(--c-brand-50);
  color: var(--c-brand-700);
  font-size: 22px;
  font-weight: 300;
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

.preview {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.preview img {
  max-width: 320px;
  max-height: 200px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  background: #0f172a;
}

.preview-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-name {
  color: var(--c-text-strong);
  font-size: 13px;
  font-weight: 600;
  word-break: break-all;
}

/* 结果 */
.recognized {
  margin-top: 12px;
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.parsed-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0 0;
}

.parsed-item {
  padding: 10px 12px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  background: #fbfdff;
}

.parsed-item dt {
  color: var(--c-text-muted);
  font-size: 11.5px;
}

.parsed-item dd {
  margin: 4px 0 0;
  color: var(--c-text-strong);
  font-size: 13px;
  word-break: break-all;
}

.parsed-item dd.empty {
  color: var(--c-text-subtle);
}

.parsed-item dd.warn {
  color: var(--c-warn);
}

.badge-warn {
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--c-warn-bg);
  color: var(--c-warn);
  font-size: 11.5px;
  font-weight: 600;
}

.code-block {
  margin: 14px 0 0;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  background: #0f172a;
  color: #e2e8f0;
  font-size: 13px;
  overflow-x: auto;
  font-family: 'JetBrains Mono', Consolas, 'Courier New', monospace;
}

.md {
  margin-top: 10px;
  color: var(--c-text);
  font-size: 14px;
  line-height: 1.75;
}

.md :deep(p) {
  margin: 0 0 8px;
}

.md :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(37, 99, 235, 0.08);
  color: var(--c-brand-700);
  font-size: 12.5px;
}

.sub-title {
  margin: 16px 0 8px;
  color: var(--c-text-strong);
  font-size: 13.5px;
  font-weight: 700;
}

.cause-list {
  margin: 0;
  padding-left: 20px;
  color: var(--c-text);
  font-size: 13.5px;
}

.cause-list li {
  margin-bottom: 6px;
}

.step-list {
  margin: 0;
  padding-left: 20px;
  color: var(--c-text);
  font-size: 13.5px;
}

.step-list li {
  margin-bottom: 6px;
}

/* 引用 */
.citation-list {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.citation-list li {
  padding: 12px 14px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: #fbfdff;
}

.cite-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
}

.cite-index {
  color: var(--c-brand-700);
  font-weight: 700;
}

.cite-loc {
  padding: 1px 7px;
  border-radius: 999px;
  background: #eef2f7;
  color: var(--c-text-muted);
  font-size: 11.5px;
}

.cite-score {
  margin-left: auto;
  color: var(--c-text-subtle);
  font-size: 11.5px;
}

.cite-text {
  margin-top: 8px;
  color: var(--c-text);
  font-size: 13px;
  line-height: 1.7;
}

.empty {
  margin-top: 12px;
  padding: 14px;
  border: 1px dashed var(--c-border);
  border-radius: var(--radius-md);
  color: var(--c-text-muted);
  font-size: 13px;
  text-align: center;
}

.actions {
  margin-top: 16px;
}

.safety {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--c-border);
  color: var(--c-text-subtle);
  font-size: 12px;
}

@media (max-width: 860px) {
  .parsed-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .preview {
    flex-direction: column;
  }
}
</style>
