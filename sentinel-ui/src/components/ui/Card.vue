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
    default: 'bg-white border border-kPrimary/10 dark:bg-neutral-900 dark:border-neutral-800',
    outline: 'bg-transparent border border-kPrimary/15 dark:border-neutral-700',
    elevated: 'bg-white border border-kPrimary/10 shadow-medium dark:bg-neutral-900 dark:border-neutral-800',
  }
  const hoverClass = props.hover
    ? 'hover:shadow-medium hover:border-kPrimary/20 dark:hover:border-neutral-700 active:scale-[0.98] cursor-pointer'
    : ''

  return cn(base, variants[props.variant], hoverClass, props.class)
})
</script>

<template>
  <div :class="classes">
    <div v-if="$slots.header" class="px-5 py-4 border-b border-kPrimary/10 dark:border-neutral-800">
      <slot name="header" />
    </div>
    <div class="px-5 py-4">
      <slot />
    </div>
    <div v-if="$slots.footer" class="px-5 py-3 border-t border-kPrimary/10 dark:border-neutral-800 bg-gray-50/50 dark:bg-neutral-900/50 rounded-b-xl">
      <slot name="footer" />
    </div>
  </div>
</template>
