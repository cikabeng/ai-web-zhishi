<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchHealth, toErrorMessage } from '@/api/client'
import type { HealthResponse } from '@/api/types'

const health = ref<HealthResponse | null>(null)
const loading = ref(true)
const error = ref('')

const modeLabel = computed(() => {
  if (!health.value) return '—'
  return health.value.demo_mode ? '演示模式' : '模型模式'
})

const modeHint = computed(() => {
  const h = health.value
  if (!h) return ''
  return h.demo_mode
    ? '未配置大模型，回答由模板生成（检索仍真实执行）'
    : `模型：${h.llm_model ?? '未知'}`
})

const embedLabel = computed(() => {
  const h = health.value
  if (!h) return '—'
  return h.embed_provider === 'hash' ? '本地 hash' : (h.embed_model ?? '远程模型')
})

const embedHint = computed(() => {
  const h = health.value
  if (!h) return ''
  return h.embed_provider === 'hash'
    ? '离线字面匹配，语义能力有限'
    : `语义向量 · ${h.embed_dim ?? '?'} 维`
})

const kbLabel = computed(() => {
  const kb = health.value?.knowledge_base
  if (!kb || kb.status === 'not_initialized') return '未初始化'
  return kb.status === 'ready' ? '就绪' : '降级'
})

const kbHint = computed(() => {
  const kb = health.value?.knowledge_base
  if (!kb || kb.status === 'not_initialized') return 'P1 阶段接入文档入库'
  return `${kb.documents} 篇文档 · ${kb.chunks} 个片段`
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    health.value = await fetchHealth()
  } catch (cause) {
    health.value = null
    error.value = toErrorMessage(cause)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="home">
    <section class="hero">
      <div class="hero-badge">RAG · 检索增强生成</div>
      <h2 class="hero-title">让每一次卡住，都能在课程资料里找到依据</h2>
      <p class="hero-desc">
        知实 AI 面向 Python、Web 开发、数据库与软件工程实训场景，只依据教师上传的教材、讲义与实验指导作答，
        并给出可核对的出处。资料里没有的，它会直接说没有。
      </p>

      <ul class="hero-points">
        <li><span class="point-dot"></span>有据可查：每条结论都附文档名与页码</li>
        <li><span class="point-dot"></span>无据则明说：检索不到就直说资料不足</li>
        <li><span class="point-dot"></span>引导优先：分层提示，不直接给完整作业答案</li>
      </ul>
    </section>

    <section class="panel">
      <header class="panel-head">
        <div>
          <h3 class="panel-title">系统状态</h3>
          <p class="panel-sub">实时读取后端 /api/health</p>
        </div>
        <el-button text type="primary" :loading="loading" @click="load">重新检测</el-button>
      </header>

      <el-alert
        v-if="error"
        :title="error"
        type="error"
        :closable="false"
        show-icon
        class="status-alert"
      />

      <div v-if="loading && !health" class="status-grid">
        <div v-for="i in 4" :key="i" class="status-card">
          <el-skeleton :rows="2" animated />
        </div>
      </div>

      <div v-else-if="health" class="status-grid">
        <article class="status-card">
          <span class="status-label">后端服务</span>
          <strong class="status-value is-ok">已连接</strong>
          <span class="status-hint">v{{ health.version }} · {{ health.env }}</span>
        </article>

        <article class="status-card">
          <span class="status-label">运行模式</span>
          <strong class="status-value" :class="health.demo_mode ? 'is-warn' : 'is-ok'">
            {{ modeLabel }}
          </strong>
          <span class="status-hint">{{ modeHint }}</span>
        </article>

        <article class="status-card">
          <span class="status-label">向量模型</span>
          <strong class="status-value">{{ embedLabel }}</strong>
          <span class="status-hint">{{ embedHint }}</span>
        </article>

        <article class="status-card">
          <span class="status-label">知识库</span>
          <strong class="status-value">{{ kbLabel }}</strong>
          <span class="status-hint">{{ kbHint }}</span>
        </article>
      </div>

      <p class="panel-foot">
        当前为 <strong>P0 骨架</strong>：接口与页面已连通，文档上传、检索与问答将在 P1–P3 依次接入。
        <a href="http://127.0.0.1:8000/api/docs" target="_blank" rel="noreferrer">查看后端接口文档 ↗</a>
      </p>
    </section>
  </div>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

/* ---------- Hero ---------- */
.hero {
  padding: clamp(24px, 4vw, 40px);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  background:
    radial-gradient(1200px 300px at 88% -10%, rgba(59, 130, 246, 0.16), transparent 70%),
    linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: var(--shadow-soft);
}

.hero-badge {
  display: inline-block;
  padding: 4px 10px;
  border: 1px solid var(--c-brand-100);
  border-radius: 999px;
  background: var(--c-brand-50);
  color: var(--c-brand-700);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.hero-title {
  margin-top: 14px;
  color: var(--c-text-strong);
  font-size: clamp(24px, 3.2vw, 34px);
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: 0.2px;
}

.hero-desc {
  max-width: 760px;
  margin-top: 12px;
  color: var(--c-text);
  font-size: 15px;
}

.hero-points {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 26px;
  margin: 20px 0 0;
  padding: 0;
  list-style: none;
}

.hero-points li {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--c-text);
  font-size: 14px;
}

.point-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--c-brand-500);
  box-shadow: 0 0 0 3px var(--c-brand-50);
}

/* ---------- Panel ---------- */
.panel {
  padding: 22px clamp(16px, 3vw, 26px);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  background: var(--c-surface);
  box-shadow: var(--shadow-card);
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel-title {
  color: var(--c-text-strong);
  font-size: 16px;
  font-weight: 700;
}

.panel-sub {
  margin-top: 2px;
  color: var(--c-text-muted);
  font-size: 12.5px;
}

.status-alert {
  margin-top: 16px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.status-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: #fbfdff;
}

.status-label {
  color: var(--c-text-muted);
  font-size: 12.5px;
}

.status-value {
  color: var(--c-text-strong);
  font-size: 17px;
  font-weight: 700;
  line-height: 1.3;
}

.status-value.is-ok {
  color: var(--c-success);
}

.status-value.is-warn {
  color: var(--c-warn);
}

.status-hint {
  color: var(--c-text-subtle);
  font-size: 12px;
  line-height: 1.5;
}

.panel-foot {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px dashed var(--c-border);
  color: var(--c-text-muted);
  font-size: 13px;
}

@media (max-width: 900px) {
  .status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 520px) {
  .status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
