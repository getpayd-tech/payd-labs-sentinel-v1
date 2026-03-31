<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/utils/formatters'

interface Props {
  variant?: 'success' | 'warning' | 'error' | 'info' | 'neutral'
  size?: 'sm' | 'md'
  class?: string
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'neutral',
  size: 'md',
})

const classes = computed(() => {
  const base = 'inline-flex items-center rounded-full font-medium'

  const sizes: Record<string, string> = {
    sm: 'px-2 py-0.5 text-2xs',
    md: 'px-2.5 py-0.5 text-xs',
  }

  const variants: Record<string, string> = {
    success: 'bg-accent/10 text-accent border border-accent/20',
    warning: 'bg-yellow-50 dark:bg-amber-950 text-amber-700 dark:text-amber-400 border border-yellow-200 dark:border-amber-800',
    error: 'bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800',
    info: 'bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800',
    neutral: 'bg-gray-100 dark:bg-neutral-800 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-neutral-700',
  }

  return cn(base, sizes[props.size], variants[props.variant], props.class)
})
</script>

<template>
  <span :class="classes">
    <slot />
  </span>
</template>
