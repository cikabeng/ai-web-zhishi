<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

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
const expandedCitation = ref<number | null>(null)

const submissionKind = ref<'thinking' | 'code'>('thinking')
const submissionText = ref('')
const feedback = ref<SubmissionFeedback | null>(null)
const feedbackLoading = ref(false)

// 引导模式进入 L3 前的「先提交尝试」弹窗（方案 D）
const attemptDialogVisible = ref(false)
const attemptText = ref('')
const attemptKind = ref<'thinking' | 'code'>('thinking')
const attemptSubmitting = ref(false)
const submissionPanel = ref<HTMLElement | null>(null)
const submissionInput = ref<{ focus: () => void } | null>(null)
const highlightSubmission = ref(false)

const canStart = computed(() => question.value.trim().length >= 4 && !loading.value)
const detectedCategory = computed(() => response.value?.category ?? null)
const confidence = computed(() => response.value?.category_confidence ?? 0)
const hasResult = computed(() => response.value !== null)

async function ask(
  current: number,
  target: number,
  action: HintAction = 'open',
  submission?: { kind: 'thinking' | 'code'; text: string },
) {
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
      ...(submission ? { submission } : {}),
    })
    understoodDone.value = false
    feedback.value = null
    activeCitation.value = null
    expandedCitation.value = null
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
  void ask(current.level, current.next_level, 'continue').then(() => {
    // 被「需要先提交尝试」拦住时，直接把输入弹窗摆到用户面前，避免不明不白卡住
    if (response.value?.clamp_reason === 'guided_requires_attempt') {
      openAttemptDialog()
    }
  })
}

function openAttemptDialog() {
  attemptKind.value = submissionKind.value
  attemptText.value = submissionText.value
  attemptDialogVisible.value = true
}

function scrollToSubmission() {
  void nextTick(() => {
    attemptDialogVisible.value = false
    const panel = submissionPanel.value
    if (panel) {
      panel.scrollIntoView({ behavior: 'smooth', block: 'center' })
      submissionInput.value?.focus?.()
      highlightSubmission.value = true
      window.setTimeout(() => {
        highlightSubmission.value = false
      }, 2000)
    }
  })
}

function buildDemoAttempt(): string {
  const text = question.value
  if (/NoneType|None/i.test(text)) {
    return [
      '我观察到：报错发生在 print(info[\'score\']) 这一行。',
      '我怀疑：info 是 None，因为 get_student 在查不到用户时走到了函数末尾，没有 return。',
      '我准备先验证：在报错前打印 type(info) 和 repr(info)，再决定是补 return 还是调用处判空。',
    ].join('\n')
  }
  if (/unsupported operand|int.*str|类型/i.test(text)) {
    return [
      '我观察到：对 1 和 "2" 做加法时崩溃。',
      '我怀疑：b 是从输入拿到的字符串，不是数字。',
      '我准备先验证：打印 type(a)、type(b)，再按业务语义决定用 int(b) 还是 str(a)。',
    ].join('\n')
  }
  return [
    '我观察到：程序在我自己写的某一行报错。',
    '我怀疑：那一行用到的变量，实际值和我的预期不一致。',
    '我准备先验证：在报错行之前打印相关变量的类型和值，再按结果决定下一步。',
  ].join('\n')
}

function fillDemoAttempt() {
  attemptKind.value = 'thinking'
  attemptText.value = buildDemoAttempt()
}

async function submitAttempt() {
  const text = attemptText.value.trim()
  if (text.length < 15) {
    ElMessage.warning('至少写 15 个字，说清楚你观察到了什么、怀疑什么')
    return
  }
  const current = response.value
  if (!current) return

  attemptSubmitting.value = true
  try {
    // 同步到下方提交面板，保证「已提交」这件事只记录一次
    submissionKind.value = attemptKind.value
    submissionText.value = text

    await ask(current.level, 3, 'continue', { kind: attemptKind.value, text })
    attemptDialogVisible.value = false

    // 顺手把反馈也取回来，学生能立刻看到对自己尝试的评价
    void submit()
  } catch (cause) {
    error.value = toErrorMessage(cause)
  } finally {
    attemptSubmitting.value = false
  }
}

function rephrase() {
  const current = response.value
  if (!current) return
  void ask(current.level, current.level, 'rephrase').then(() => {
    variant.value += 1
  })
}

function toggleCitation(index: number) {
  activeCitation.value = index
  expandedCitation.value = expandedCitation.value === index ? null : index
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

function setMode(value: TeachingModeValue) {
  if (mode.value === value) return
  mode.value = value
  onModeChange()
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
        <div class="mode-switch" role="group" aria-label="教学模式">
          <el-tooltip placement="bottom" :show-after="150" popper-class="mode-tooltip">
            <template #content>
              <div class="mode-tip">
                <strong>引导模式</strong>
                <ul>
                  <li>进入 L3 前必须提交一次自己的尝试</li>
                  <li>多反问、少下结论，像助教在旁边提问</li>
                  <li>适合：学生独立完成作业</li>
                </ul>
              </div>
            </template>
            <button
              type="button"
              class="mode-btn"
              :class="{ active: mode === 'guided' }"
              :aria-pressed="mode === 'guided'"
              @click="setMode('guided')"
            >
              引导模式
            </button>
          </el-tooltip>

          <el-tooltip placement="bottom" :show-after="150" popper-class="mode-tooltip">
            <template #content>
              <div class="mode-tip">
                <strong>学习模式</strong>
                <ul>
                  <li>不要求先提交尝试，可直接逐级查看</li>
                  <li>讲解更完整、更少反问</li>
                  <li>适合：复习、听讲解</li>
                </ul>
              </div>
            </template>
            <button
              type="button"
              class="mode-btn"
              :class="{ active: mode === 'study' }"
              :aria-pressed="mode === 'study'"
              @click="setMode('study')"
            >
              学习模式
            </button>
          </el-tooltip>
        </div>
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

      <div class="session-layout">
        <aside class="steps-rail">
          <p class="rail-title">学习进度</p>
          <HintLadder
            :level="response.level"
            :clamped="response.clamped"
            :reason="response.clamp_reason"
            vertical
          />
        </aside>

        <div class="session-main">

      <section class="card">
        <div class="row row-between">
          <div>
            <h3 class="card-title">L{{ response.level }} · {{ response.level_name }}</h3>
            <p class="muted small">{{ response.level_intent }}</p>
          </div>
          <div class="level-badges">
            <span v-if="response.example_generated" class="badge-ai">AI 生成示例</span>
            <span
              v-if="response.llm_status === 'model'"
              class="badge-ai"
              :title="response.llm_model ?? ''"
            >
              模型生成
            </span>
            <span v-else-if="response.llm_status === 'fallback'" class="badge-warn">
              模型失败 · 已回退模板
            </span>
            <span v-else class="badge-muted">模板生成</span>
          </div>
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
                  @click="toggleCitation(n)"
                >
                  [{{ n }}]
                </button>
              </span>
            </div>

            <pre v-if="block.kind === 'code'" class="code-block"><code>{{ block.content }}</code></pre>
            <div v-else class="md" v-html="renderMarkdown(block.content)" />

            <div v-if="block.meta.reason === 'guided_requires_attempt'" class="block-cta">
              <el-button type="primary" size="small" @click="openAttemptDialog">去写尝试并进入 L3</el-button>
              <el-button size="small" text @click="scrollToSubmission">滚到下方提交框</el-button>
            </div>
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
            :class="{
              active: activeCitation === citation.index,
              expanded: expandedCitation === citation.index,
            }"
          >
            <button type="button" class="cite-row" @click="toggleCitation(citation.index)">
              <span class="cite-index">[{{ citation.index }}]</span>
              <span class="cite-doc">《{{ citation.doc_name }}》</span>
              <span class="cite-loc">{{ citation.location }}</span>
              <span v-if="citation.heading" class="cite-heading">{{ citation.heading }}</span>
              <span class="cite-score">{{ (citation.score * 100).toFixed(0) }}%</span>
              <span class="cite-toggle">{{ expandedCitation === citation.index ? '收起' : '原文' }}</span>
            </button>
            <p v-if="expandedCitation === citation.index" class="cite-text">{{ citation.snippet }}</p>
          </li>
        </ol>
      </section>

      <section
        ref="submissionPanel"
        class="card submission-card"
        :class="{ 'is-highlighted': highlightSubmission }"
      >
        <div class="row row-between">
          <h3 class="card-title">提交你的思路或代码</h3>
          <span class="muted small">只做文本分析，不会执行你的代码</span>
        </div>

        <el-radio-group v-model="submissionKind" size="small" class="kind-switch">
          <el-radio-button value="thinking">我的思路</el-radio-button>
          <el-radio-button value="code">我的代码片段</el-radio-button>
        </el-radio-group>

        <el-input
          ref="submissionInput"
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
        </div>
      </div>
    </template>

    <el-dialog
      v-model="attemptDialogVisible"
      title="先写下你的尝试，再进 L3"
      width="560px"
      :close-on-click-modal="false"
      append-to-body
    >
      <p class="dialog-hint">
        引导模式下，进入 L3（局部示例）前需要先提交一次你自己的思路或代码片段。
        这不是考核，是为了让提示真正帮到你——直接看示例，学习效果会差很多。
      </p>

      <el-radio-group v-model="attemptKind" size="small" class="kind-switch">
        <el-radio-button value="thinking">我的思路</el-radio-button>
        <el-radio-button value="code">我的代码片段</el-radio-button>
      </el-radio-group>

      <el-input
        v-model="attemptText"
        type="textarea"
        :rows="5"
        maxlength="4000"
        show-word-limit
        resize="none"
        :placeholder="
          attemptKind === 'code'
            ? '把你改到一半的代码贴进来（建议只贴出问题的那几行）'
            : '例如：我怀疑 info 是 None，因为 get_student 在查不到时没有 return'
        "
      />
      <div class="dialog-tip-row">
        <p class="dialog-tip">至少 15 个字。提交后会立刻进入 L3，并给出针对你这段尝试的反馈。</p>
        <el-button text type="primary" size="small" @click="fillDemoAttempt">填入示例尝试（演示用）</el-button>
      </div>

      <template #footer>
        <el-button @click="scrollToSubmission">取消，去页面下方写</el-button>
        <el-button
          type="primary"
          :loading="attemptSubmitting"
          :disabled="attemptText.trim().length < 15"
          @click="submitAttempt"
        >
          提交并进入 L3
        </el-button>
      </template>
    </el-dialog>
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

/* 模式切换：两个按钮各自带悬浮说明，让评委一眼看出差别 */
.mode-switch {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  border: 1px solid var(--c-border);
  border-radius: 999px;
  background: #fff;
}

.mode-btn {
  padding: 5px 14px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--c-text);
  font-family: inherit;
  font-size: 12.5px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.mode-btn:hover {
  background: var(--c-brand-50);
  color: var(--c-brand-700);
}

.mode-btn.active {
  background: var(--c-brand-600);
  color: #fff;
  font-weight: 600;
}

.mode-btn.active:hover {
  background: var(--c-brand-700);
  color: #fff;
}

:global(.mode-tooltip) {
  max-width: 260px;
}

:global(.mode-tooltip .mode-tip strong) {
  display: block;
  margin-bottom: 4px;
  font-size: 13px;
}

:global(.mode-tooltip .mode-tip ul) {
  margin: 0;
  padding-left: 16px;
  font-size: 12.5px;
  line-height: 1.7;
}

/* 左侧竖向进度 + 右侧内容 */
.session-layout {
  display: grid;
  grid-template-columns: 170px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.steps-rail {
  position: sticky;
  top: 92px;
  padding: 14px 10px 12px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  background: var(--c-surface);
  box-shadow: var(--shadow-card);
  z-index: 2;
}

.rail-title {
  margin: 0 0 8px 10px;
  color: var(--c-text-muted);
  font-size: 11.5px;
  letter-spacing: 0.5px;
}

.session-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

@media (max-width: 960px) {
  .session-layout {
    grid-template-columns: 1fr;
  }

  .steps-rail {
    position: static;
  }
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

.badge-muted {
  padding: 2px 9px;
  border-radius: 999px;
  background: #f1f5f9;
  color: var(--c-text-muted);
  font-size: 11.5px;
  font-weight: 600;
}

.level-badges {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
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

/* 引用：默认一行，点击展开原文 */
.citation-list {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.citation-list li {
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  background: #fbfdff;
  overflow: hidden;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.citation-list li.active {
  border-color: var(--c-brand-500);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.citation-list li.expanded {
  border-color: var(--c-brand-100);
}

.cite-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: var(--c-text);
  font-family: inherit;
  font-size: 12.5px;
  text-align: left;
  cursor: pointer;
}

.cite-row:hover {
  background: var(--c-brand-50);
}

.cite-index {
  color: var(--c-brand-700);
  font-weight: 700;
}

.cite-doc {
  color: var(--c-text-strong);
  font-weight: 600;
  white-space: nowrap;
}

.cite-loc {
  padding: 1px 7px;
  border-radius: 999px;
  background: #eef2f7;
  color: var(--c-text-muted);
  font-size: 11px;
  white-space: nowrap;
}

.cite-heading {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--c-text-subtle);
  font-size: 11.5px;
}

.cite-score {
  color: var(--c-text-subtle);
  font-size: 11px;
  white-space: nowrap;
}

.cite-toggle {
  color: var(--c-brand-600);
  font-size: 11.5px;
  white-space: nowrap;
}

.cite-text {
  margin: 0;
  padding: 8px 12px 10px;
  border-top: 1px dashed var(--c-border);
  color: var(--c-text);
  font-size: 12.5px;
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

/* 提交反馈 */
.kind-switch {
  margin: 12px 0;
}

/* 「需要先提交尝试」的引导 */
.block-cta {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.submission-card {
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.submission-card.is-highlighted {
  border-color: var(--c-brand-500);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16), var(--shadow-card);
  animation: submit-pulse 1s ease-in-out 2;
}

@keyframes submit-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16), var(--shadow-card);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(37, 99, 235, 0.1), var(--shadow-card);
  }
}

.dialog-hint {
  margin: 0 0 6px;
  color: var(--c-text);
  font-size: 13.5px;
  line-height: 1.7;
}

.dialog-tip {
  margin: 8px 0 0;
  color: var(--c-text-muted);
  font-size: 12px;
}

.dialog-tip-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.dialog-tip-row .dialog-tip {
  margin: 8px 0 0;
  flex: 1;
  min-width: 200px;
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
