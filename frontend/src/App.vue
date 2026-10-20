<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()
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
        <span class="nav-item is-disabled" title="P1 阶段开放">知识库</span>
        <span class="nav-item is-disabled" title="P4 阶段开放">报错诊断</span>
      </nav>
    </header>

    <main class="app-main">
      <RouterView />
    </main>

    <footer class="app-footer">
      知实 AI · 仅依据课程资料作答，检索不到就明确说明 · RAG 驱动的课程答疑助手
    </footer>
  </div>
</template>

<style scoped>
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
