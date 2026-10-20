<script setup lang="ts">
const props = defineProps<{ level: number; clamped: boolean }>()

const steps = [
  { level: 1, name: '知识点提示' },
  { level: 2, name: '解题思路' },
  { level: 3, name: '局部示例' },
  { level: 4, name: '相似例题' },
]

function stateOf(level: number): 'done' | 'current' | 'locked' {
  if (level < props.level) return 'done'
  if (level === props.level) return 'current'
  return 'locked'
}
</script>

<template>
  <div class="ladder">
    <div
      v-for="step in steps"
      :key="step.level"
      class="step"
      :class="stateOf(step.level)"
    >
      <span class="dot">{{ step.level < props.level ? '✓' : step.level }}</span>
      <span class="name">{{ step.name }}</span>
    </div>
    <p v-if="clamped" class="clamp-note">
      请求的层级超出了「一次只升一级」的限制，已回落到当前可用的层级。
    </p>
  </div>
</template>

<style scoped>
.ladder {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.step {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  border: 1px solid var(--c-border);
  border-radius: 999px;
  background: #fff;
  color: var(--c-text-subtle);
  font-size: 13px;
}

.step .dot {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #eef2f7;
  color: var(--c-text-muted);
  font-size: 11px;
  font-weight: 700;
}

.step.done {
  border-color: var(--c-brand-100);
  background: var(--c-brand-50);
  color: var(--c-brand-700);
}

.step.done .dot {
  background: var(--c-brand-500);
  color: #fff;
}

.step.current {
  border-color: var(--c-brand-600);
  background: #fff;
  color: var(--c-brand-700);
  font-weight: 600;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.step.current .dot {
  background: var(--c-brand-600);
  color: #fff;
}

.clamp-note {
  width: 100%;
  margin-top: 4px;
  color: var(--c-warn);
  font-size: 12.5px;
}
</style>
