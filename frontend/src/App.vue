<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { fetchHealth } from '@/api/client'

const route = useRoute()
// 全局演示模式提示：没配模型时每条页面都要看得到，不能只写在首页
const demoMode = ref(false)

onMounted(async () => {
  try {
    const health = await fetchHealth()
    demoMode.value = health.demo_mode
  } catch {
    demoMode.value = false
  }
})
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand">
        <div class="brand-mark">知</div>
        <div class="brand-text">
          <h1 class="brand-name">知实 AI</h1>
          <p class="brand-sub">高校软件工程实训 · 智能答疑知识库</p>
        </div>
      </div>

      <nav class="app-nav" aria-label="主导航">
        <RouterLink to="/" class="nav-item" :class="{ 'is-active': route.path === '/' }">
          首页
        </RouterLink>
        <RouterLink
          to="/teaching"
          class="nav-item"
          :class="{ 'is-active': route.path === '/teaching' }"
        >
          分层教学
        </RouterLink>
        <RouterLink
          to="/errors"
          class="nav-item"
          :class="{ 'is-active': route.path === '/errors' }"
        >
          报错分析
        </RouterLink>
        <RouterLink
          to="/library"
          class="nav-item"
          :class="{ 'is-active': route.path === '/library' }"
        >
          知识库
        </RouterLink>
      </nav>
    </header>

    <div v-if="demoMode" class="demo-banner">
      演示模式 · 未配置大模型：检索与引用真实执行，回答由模板生成并已明确标注
    </div>

    <main class="app-main">
      <RouterView />
    </main>

    <footer class="app-footer">
      知实 AI · 仅依据课程资料作答，检索不到就明确说明 · RAG 驱动的课程答疑助手
    </footer>
  </div>
</template>

<style scoped>
.demo-banner {
  padding: 8px 16px;
  background: var(--c-warn-bg);
  border-bottom: 1px solid #fde3b5;
  color: var(--c-warn);
  font-size: 12.5px;
  text-align: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--c-brand-600), var(--c-brand-500));
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  box-shadow: 0 6px 14px rgba(37, 99, 235, 0.28);
}

.brand-name {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: var(--c-text-strong);
}

.brand-sub {
  font-size: 12.5px;
  color: var(--c-text-muted);
}

.app-nav {
  display: flex;
  align-items: center;
  gap: 6px;
}

.nav-item {
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  color: var(--c-text);
  font-size: 14px;
  font-weight: 500;
  transition: background 0.15s ease, color 0.15s ease;
}

.nav-item:hover {
  background: var(--c-brand-50);
  color: var(--c-brand-700);
  text-decoration: none;
}

.nav-item.is-active {
  background: var(--c-brand-50);
  color: var(--c-brand-700);
}

.nav-item.is-disabled {
  color: var(--c-text-subtle);
  cursor: not-allowed;
}

.nav-item.is-disabled:hover {
  background: transparent;
  color: var(--c-text-subtle);
}
</style>
