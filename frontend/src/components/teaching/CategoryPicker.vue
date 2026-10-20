<script setup lang="ts">
import type { CategoryMeta, CategoryValue } from '@/api/teaching'

const props = defineProps<{
  categories: CategoryMeta[]
  selected: CategoryValue | null
  detected: CategoryValue | null
  confidence: number
}>()

const emit = defineEmits<{ (event: 'select', value: CategoryValue): void }>()

function isActive(value: CategoryValue): boolean {
  return (props.selected ?? props.detected) === value
}
</script>

<template>
  <div class="picker">
    <button
      v-for="item in categories"
      :key="item.value"
      type="button"
      class="chip"
      :class="{ active: isActive(item.value), detected: detected === item.value }"
      :title="item.description"
      @click="emit('select', item.value)"
    >
      <span class="chip-label">{{ item.label }}</span>
      <span v-if="detected === item.value" class="chip-auto">
        自动 {{ (confidence * 100).toFixed(0) }}%
      </span>
    </button>
  </div>
</template>

<style scoped>
.picker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 13px;
  border: 1px solid var(--c-border);
  border-radius: 999px;
  background: #fff;
  color: var(--c-text);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s ease;
}

.chip:hover {
  border-color: var(--c-brand-500);
  color: var(--c-brand-700);
}

.chip.active {
  border-color: var(--c-brand-600);
  background: var(--c-brand-50);
  color: var(--c-brand-700);
  font-weight: 600;
}

.chip-auto {
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--c-brand-100);
  color: var(--c-brand-700);
  font-size: 11px;
  font-weight: 600;
}
</style>
