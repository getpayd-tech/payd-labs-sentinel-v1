<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/utils/formatters'

interface Props {
  variant?: 'default' | 'outline' | 'elevated'
  hover?: boolean
  class?: string
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  hover: false,
})

const classes = computed(() => {
  const base = 'rounded-xl transition-all duration-200'
  const variants: Record<string, string> = {
    default: 'bg-surface border border-border',
    outline: 'bg-transparent border border-border-medium',
    elevated: 'bg-surface border border-border shadow-[var(--shadow-medium)]',
  }
  const hoverClass = props.hover
    ? 'hover:shadow-[var(--shadow-medium)] hover:border-border-medium active:scale-[0.98] cursor-pointer'
    : ''

  return cn(base, variants[props.variant], hoverClass, props.class)
})
</script>

<template>
  <div :class="classes">
    <div v-if="$slots.header" class="px-5 py-4 border-b border-border">
      <slot name="header" />
    </div>
    <div class="px-5 py-4">
      <slot />
    </div>
    <div v-if="$slots.footer" class="px-5 py-3 border-t border-border bg-surface-secondary rounded-b-xl">
      <slot name="footer" />
    </div>
  </div>
</template>
