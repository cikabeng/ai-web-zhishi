<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { toErrorMessage } from '@/api/client'
import {
  fetchCategories,
  fetchDemoCase,
  requestFeedback,
  requestHint,
} from '@/api/teaching'
import type {
  CategoryMeta,
  CategoryValue,
  HintAction,
  SubmissionFeedback,
  TeachingModeValue,
  TeachingResponse,
} from '@/api/teaching'
import CategoryPicker from '@/components/teaching/CategoryPicker.vue'
import HintLadder from '@/components/teaching/HintLadder.vue'
import { renderMarkdown } from '@/utils/markdown'

const LEVEL_GUIDE = [
  { level: 1, name: '知识点提示', desc: '只解释概念，指出该看哪段资料，不给解法' },
  { level: 2, name: '解题思路', desc: '给出分步骤的检查顺序，先查什么、后查什么' },
  { level: 3, name: '局部示例', desc: '给最小验证片段并解释关键语句，不是答案' },
  { level: 4, name: '相似例题', desc: '换一个条件不同的例题，练完再回原题' },
]

const question = ref('')
const mode = ref<TeachingModeValue>('guided')
const selectedCategory = ref<CategoryValue | null>(null)
const categories = ref<CategoryMeta[]>([])
const route = useRoute()

const response = ref<TeachingResponse | null>(null)
const loading = ref(false)
const error = ref('')

const variant = ref(0)
const understoodDone = ref(false)
const activeCitation = ref<number | null>(null)

const submissionKind = ref<'thinking' | 'code'>('thinking')
const submissionText = ref('')
const feedback = ref<SubmissionFeedback | null>(null)
const feedbackLoading = ref(false)

const canStart = computed(() => question.value.trim().length >= 4 && !loading.value)
const detectedCategory = computed(() => response.value?.category ?? null)
const confidence = computed(() => response.value?.category_confidence ?? 0)
const hasResult = computed(() => response.value !== null)

async function ask(current: number, target: number, action: HintAction = 'open') {
  if (!question.value.trim()) return
  loading.value = true
  error.value = ''
  try {
    response.value = await requestHint({
      question: question.value.trim(),
      mode: mode.value,
      category: selectedCategory.value,
      current_level: current,
      target_level: target,
      variant: variant.value,
      action,
    })
    understoodDone.value = false
    feedback.value = null
    activeCitation.value = null
  } catch (cause) {
    error.value = toErrorMessage(cause)
  } finally {
    loading.value = false
  }
}

function start() {
  selectedCategory.value = null
  variant.value = 0
  response.value = null
  feedback.value = null
  submissionText.value = ''
  understoodDone.value = false
  void ask(0, 1, 'open')
}

function next() {
  const current = response.value
  if (!current || current.next_level === null) return
  variant.value = 0
  void ask(current.level, current.next_level, 'continue')
}

function rephrase() {
  const current = response.value
  if (!current) return
  void ask(current.level, current.level, 'rephrase').then(() => {
    variant.value += 1
  })
}

function understood() {
  understoodDone.value = true
}

function onCategorySelect(value: CategoryValue) {
  selectedCategory.value = value
  const current = response.value
  if (current) void ask(current.level, current.level, 'open')
}

function onModeChange() {
  const current = response.value
  if (current) void ask(current.level, current.level, 'open')
}

async function loadDemo() {
  try {
    const demo = await fetchDemoCase()
    question.value = demo.question
    selectedCategory.value = null
    response.value = null
  } catch (cause) {
    error.value = toErrorMessage(cause)
  }
}

async function submit() {
  const current = response.value
  if (!current || !submissionText.value.trim()) return
  feedbackLoading.value = true
  error.value = ''
  try {
    feedback.value = await requestFeedback({
      question: question.value.trim(),
      mode: mode.value,
      category: selectedCategory.value,
      current_level: current.level,
      target_level: current.level,
      submission: { kind: submissionKind.value, text: submissionText.value.trim() },
    })
  } catch (cause) {
    error.value = toErrorMessage(cause)
  } finally {
    feedbackLoading.value = false
  }
}

onMounted(async () => {
  try {
    categories.value = await fetchCategories()
  } catch {
    categories.value = []
  }

  // 从截图报错分析跳转过来时，带上识别/修正后的报错内容
  const preset = route.query.question
  if (typeof preset === 'string' && preset.trim()) {
    question.value = preset
    await ask(0, 1, 'open')
    return
  }

  // 演示/录屏用：/teaching?demo=1 自动载入演示问题并给出第一层提示
  if (route.query.demo === '1') {
    await loadDemo()
    await ask(0, 1, 'open')
  }
})
</script>

<template>
  <div class="teaching">
    <header class="page-head">
      <div>
        <h2 class="page-title">分层教学引擎</h2>
        <p class="page-sub">
          同一道题，四步引导：先理解概念，再梳理思路，然后给最小片段，最后用相似例题迁移。
          每次只推进一级，不直接给完整答案。
        </p>
      </div>
      <div class="head-actions">
        <el-radio-group v-model="mode" size="small" @change="onModeChange">
          <el-radio-button value="guided">引导模式</el-radio-button>
          <el-radio-button value="study">学习模式</el-radio-button>
        </el-radio-group>
        <el-button size="small" @click="loadDemo">载入演示问题</el-button>
      </div>
    </header>

    <section class="card">
      <el-input
        v-model="question"
        type="textarea"
        :rows="4"
        maxlength="2000"
        show-word-limit
        resize="none"
        placeholder="描述你卡住的地方，例如：运行 Python 时报错 TypeError: 'NoneType' object is not subscriptable，代码里 info = get_student('李四') 然后 print(info['score']) 就挂了……"
      />
      <div class="row row-between">
        <span class="muted small">回答会附带课程资料引用；检索不到时会明确说明资料不足。</span>
        <el-button type="primary" :loading="loading" :disabled="!canStart" @click="start">
          开始引导
        </el-button>
      </div>
    </section>

    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />

    <section v-if="!hasResult && !loading" class="card guide">
      <h3 class="card-title">四层提示各自给什么</h3>
      <div class="guide-grid">
        <article v-for="item in LEVEL_GUIDE" :key="item.level" class="guide-item">
          <span class="guide-level">L{{ item.level }}</span>
          <div>
            <p class="guide-name">{{ item.name }}</p>
            <p class="guide-desc">{{ item.desc }}</p>
          </div>
        </article>
      </div>
    </section>

    <template v-if="response">
      <section class="card">
        <div class="row row-between">
          <div>
            <h3 class="card-title">问题分类</h3>
            <p class="muted small">
              自动识别：{{ response.category_label }}（{{ (response.category_confidence * 100).toFixed(0) }}%，
              {{ response.category_source === 'user' ? '已手动指定' : '系统判断' }}）
            </p>
          </div>
          <span v-if="response.insufficient_evidence" class="badge-warn">资料不足</span>
        </div>
        <CategoryPicker
          :categories="categories"
          :selected="selectedCategory"
          :detected="detectedCategory"
          :confidence="confidence"
          @select="onCategorySelect"
        />
      </section>

      <section class="card">
        <HintLadder :level="response.level" :clamped="response.clamped" />
      </section>

      <section class="card">
        <div class="row row-between">
          <div>
            <h3 class="card-title">L{{ response.level }} · {{ response.level_name }}</h3>
            <p class="muted small">{{ response.level_intent }}</p>
          </div>
          <span v-if="response.example_generated" class="badge-ai">AI 生成示例</span>
        </div>

        <div class="blocks">
          <article
            v-for="(block, index) in response.blocks"
            :key="`${block.kind}-${index}`"
            class="block"
            :class="`block-${block.kind}`"
          >
            <div class="block-head">
              <span class="block-title">{{ block.title }}</span>
              <span v-if="block.kind === 'example'" class="badge-ai">AI 生成示例</span>
              <span v-if="block.citations.length" class="block-cites">
                <button
                  v-for="n in block.citations"
                  :key="n"
                  type="button"
                  class="cite-btn"
                  @click="activeCitation = n"
                >
                  [{{ n }}]
                </button>
              </span>
            </div>

            <pre v-if="block.kind === 'code'" class="code-block"><code>{{ block.content }}</code></pre>
            <div v-else class="md" v-html="renderMarkdown(block.content)" />
          </article>
        </div>

        <div class="check">
          <p class="check-label">检查问题</p>
          <p class="check-q">{{ response.check_question.question }}</p>
          <p class="check-purpose">{{ response.check_question.purpose }}</p>
        </div>

        <div class="actions">
          <el-button :disabled="understoodDone" @click="understood">我理解了</el-button>
          <el-button :loading="loading" @click="rephrase">换一种解释</el-button>
          <el-button
            type="primary"
            :loading="loading"
            :disabled="!response.next_level"
            @click="next"
          >
            {{ response.next_level ? `继续提示（L${response.next_level}）` : '已到最高层' }}
          </el-button>
        </div>
        <p v-if="understoodDone" class="ok-note">
          已记录「我理解了」。建议先自己动手改一版，再决定要不要继续要提示。
        </p>
      </section>

      <section class="card">
        <div class="row row-between">
          <h3 class="card-title">引用来源</h3>
          <span class="muted small">仅来自本次检索，未命中的不会出现</span>
        </div>

        <p v-if="!response.citations.length" class="empty">
          这次没有检索到相关课程资料，上面的解释已标注为通用知识，请以课堂资料为准。
        </p>

        <ol v-else class="citation-list">
          <li
            v-for="citation in response.citations"
            :key="citation.chunk_id"
            :class="{ active: activeCitation === citation.index }"
          >
            <div class="cite-head">
              <span class="cite-index">[{{ citation.index }}]</span>
              <strong>《{{ citation.doc_name }}》</strong>
              <span class="cite-loc">{{ citation.location }}</span>
              <span class="cite-score">相关度 {{ (citation.score * 100).toFixed(0) }}%</span>
            </div>
            <p class="cite-text">{{ citation.snippet }}</p>
            <p v-if="citation.heading" class="cite-heading">章节：{{ citation.heading }}</p>
          </li>
        </ol>
      </section>

      <section class="card">
        <div class="row row-between">
          <h3 class="card-title">提交你的思路或代码</h3>
          <span class="muted small">只做文本分析，不会执行你的代码</span>
        </div>

        <el-radio-group v-model="submissionKind" size="small" class="kind-switch">
          <el-radio-button value="thinking">我的思路</el-radio-button>
          <el-radio-button value="code">我的代码片段</el-radio-button>
        </el-radio-group>

        <el-input
          v-model="submissionText"
          type="textarea"
          :rows="4"
          maxlength="4000"
          show-word-limit
          resize="none"
          :placeholder="
            submissionKind === 'code'
              ? '粘贴你改到一半的代码（建议只贴出问题的那几行）'
              : '说说你观察到了什么、怀疑原因是什么'
          "
        />

        <div class="row row-between">
          <span class="muted small">我会针对你写的内容给反馈，而不是直接给答案。</span>
          <el-button
            type="primary"
            plain
            :loading="feedbackLoading"
            :disabled="!submissionText.trim()"
            @click="submit"
          >
            获取反馈
          </el-button>
        </div>

        <div v-if="feedback" class="feedback" :class="`feedback-${feedback.verdict}`">
          <p class="feedback-summary">{{ feedback.summary }}</p>
          <p v-for="(item, index) in feedback.blocks" :key="index" class="feedback-item" :class="`item-${item.kind}`">
            {{ item.text }}
          </p>
          <p class="feedback-next">下一步：{{ feedback.next_question }}</p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.teaching {
  display: flex;
  flex-direction: column;
  gap: 18px;
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

.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
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

.muted {
  color: var(--c-text-muted);
}

.small {
  font-size: 12.5px;
}

.badge-ai {
  padding: 2px 9px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 11.5px;
  font-weight: 600;
}

.badge-warn {
  padding: 2px 9px;
  border-radius: 999px;
  background: var(--c-warn-bg);
  color: var(--c-warn);
  font-size: 11.5px;
  font-weight: 600;
}

/* 引导说明 */
.guide-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.guide-item {
  display: flex;
  gap: 12px;
  padding: 14px;
  border: 1px dashed var(--c-border);
  border-radius: var(--radius-md);
  background: #fbfdff;
}

.guide-level {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--c-brand-50);
  color: var(--c-brand-700);
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.guide-name {
  color: var(--c-text-strong);
  font-size: 14px;
  font-weight: 600;
}

.guide-desc {
  margin-top: 3px;
  color: var(--c-text-muted);
  font-size: 12.5px;
}

/* 提示块 */
.blocks {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
}

.block {
  padding: 14px 16px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: #fbfdff;
}

.block-explain {
  background: #f7faff;
  border-color: #dce9ff;
}

.block-evidence {
  background: #f6fdf9;
  border-color: #d6f0e1;
}

.block-limit {
  background: var(--c-warn-bg);
  border-color: #fde3b5;
}

.block-example {
  background: #f7f6ff;
  border-color: #e0dcff;
}

.block-note {
  background: #f8fafc;
}

.block-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.block-title {
  color: var(--c-text-strong);
  font-size: 13.5px;
  font-weight: 700;
}

.block-cites {
  margin-left: auto;
  display: flex;
  gap: 4px;
}

.cite-btn {
  border: none;
  background: var(--c-brand-50);
  color: var(--c-brand-700);
  border-radius: 6px;
  padding: 1px 6px;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
}

.cite-btn:hover {
  background: var(--c-brand-100);
}

.code-block {
  margin: 0;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  background: #0f172a;
  color: #e2e8f0;
  font-size: 13px;
  line-height: 1.65;
  overflow-x: auto;
  font-family: 'JetBrains Mono', Consolas, 'Courier New', monospace;
}

.md {
  color: var(--c-text);
  font-size: 14px;
  line-height: 1.75;
}

.md :deep(p) {
  margin: 0 0 8px;
}

.md :deep(ul),
.md :deep(ol) {
  margin: 6px 0;
  padding-left: 20px;
}

.md :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(37, 99, 235, 0.08);
  color: var(--c-brand-700);
  font-size: 12.5px;
}

.md :deep(strong) {
  color: var(--c-text-strong);
}

/* 检查问题 */
.check {
  margin-top: 16px;
  padding: 14px 16px;
  border-left: 3px solid var(--c-brand-500);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--c-brand-50);
}

.check-label {
  color: var(--c-brand-700);
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.check-q {
  margin-top: 4px;
  color: var(--c-text-strong);
  font-size: 14.5px;
  font-weight: 600;
}

.check-purpose {
  margin-top: 4px;
  color: var(--c-text-muted);
  font-size: 12.5px;
}

.actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.ok-note {
  margin-top: 10px;
  color: var(--c-success);
  font-size: 12.5px;
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
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.citation-list li.active {
  border-color: var(--c-brand-500);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
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

.cite-heading {
  margin-top: 6px;
  color: var(--c-text-subtle);
  font-size: 11.5px;
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

/* 提交反馈 */
.kind-switch {
  margin: 12px 0;
}

.feedback {
  margin-top: 14px;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  background: #f8fafc;
  border: 1px solid var(--c-border);
}

.feedback-on_track {
  background: var(--c-success-bg);
  border-color: #bfe7cf;
}

.feedback-off_track {
  background: var(--c-danger-bg);
  border-color: #f5c6c6;
}

.feedback-summary {
  color: var(--c-text-strong);
  font-size: 14px;
  font-weight: 600;
}

.feedback-item {
  margin-top: 8px;
  color: var(--c-text);
  font-size: 13.5px;
}

.item-question {
  color: var(--c-brand-700);
}

.item-warning {
  color: var(--c-warn);
}

.feedback-next {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--c-border);
  color: var(--c-text-muted);
  font-size: 13px;
}

@media (max-width: 820px) {
  .guide-grid {
    grid-template-columns: 1fr;
  }

  .page-head {
    flex-direction: column;
  }
}
</style>
