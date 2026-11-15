<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  level: number
  clamped: boolean
  reason?: 'max_one_level_per_step' | 'guided_requires_attempt' | null
  /** 竖排（左侧进度栏）或横排（顶部步骤条） */
  vertical?: boolean
}>()

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

const clampText = computed(() => {
  if (props.reason === 'guided_requires_attempt') {
    return '引导模式下，进入 L3 前需要先提交一次自己的思路或代码片段。'
  }
  return '请求的层级超出了「一次只升一级」的限制，已回落到当前可用的层级。'
})
</script>

<template>
  <div class="ladder" :class="{ vertical: vertical }">
    <div
      v-for="step in steps"
      :key="step.level"
      class="step"
      :class="stateOf(step.level)"
    >
      <span class="dot">{{ step.level < props.level ? '✓' : step.level }}</span>
      <span class="name">{{ step.name }}</span>
      <span v-if="stateOf(step.level) === 'current'" class="current-tag">当前</span>
    </div>
    <p v-if="clamped" class="clamp-note">{{ clampText }}</p>
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

.current-tag {
  display: none;
}

.clamp-note {
  width: 100%;
  margin-top: 4px;
  color: var(--c-warn);
  font-size: 12.5px;
}

/* ---------- 竖排：左侧进度栏 ---------- */
.ladder.vertical {
  position: relative;
  flex-direction: column;
  align-items: stretch;
  gap: 2px;
  flex-wrap: nowrap;
}

.ladder.vertical::before {
  content: '';
  position: absolute;
  left: 15px;
  top: 16px;
  bottom: 16px;
  width: 2px;
  background: var(--c-border);
}

.ladder.vertical .step {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  font-size: 13px;
}

.ladder.vertical .step .dot {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border: 3px solid var(--c-surface);
  box-sizing: content-box;
}

.ladder.vertical .step.done {
  background: transparent;
  color: var(--c-brand-700);
}

.ladder.vertical .step.current {
  border-color: var(--c-brand-100);
  background: var(--c-brand-50);
  box-shadow: none;
}

.ladder.vertical .step.locked {
  color: var(--c-text-subtle);
}

.ladder.vertical .current-tag {
  display: inline-block;
  margin-left: auto;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--c-brand-600);
  color: #fff;
  font-size: 10.5px;
  font-weight: 600;
}

.ladder.vertical .clamp-note {
  margin: 6px 2px 0;
  font-size: 12px;
  line-height: 1.6;
}
</style>
