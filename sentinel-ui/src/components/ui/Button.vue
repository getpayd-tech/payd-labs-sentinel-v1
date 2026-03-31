<script setup lang="ts">
import { computed } from 'vue'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/utils/formatters'
import { Loader2 } from 'lucide-vue-next'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98]',
  {
    variants: {
      variant: {
        primary:
          'bg-kPrimary text-white hover:bg-kPrimary-light focus-visible:ring-kPrimary dark:bg-kPrimary-light dark:hover:bg-kPrimary',
        accent:
          'bg-accent text-white hover:bg-accent-dark focus-visible:ring-accent shadow-sm hover:shadow-glow-accent',
        outline:
          'border border-kPrimary/20 bg-transparent text-kPrimary hover:bg-kPrimary/5 focus-visible:ring-kPrimary dark:border-neutral-700 dark:text-white dark:hover:bg-neutral-800',
        ghost:
          'bg-transparent text-kPrimary hover:bg-kPrimary/5 dark:text-white dark:hover:bg-neutral-800',
        danger:
          'bg-red-500 text-white hover:bg-red-600 focus-visible:ring-red-500',
      },
      size: {
        xs: 'h-7 px-2.5 text-xs rounded-md',
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4 text-sm',
        lg: 'h-12 px-6 text-base',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
)

type ButtonVariants = VariantProps<typeof buttonVariants>

interface Props {
  variant?: NonNullable<ButtonVariants['variant']>
  size?: NonNullable<ButtonVariants['size']>
  loading?: boolean
  disabled?: boolean
  type?: 'button' | 'submit' | 'reset'
  class?: string
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  loading: false,
  disabled: false,
  type: 'button',
})

const classes = computed(() =>
  cn(buttonVariants({ variant: props.variant, size: props.size }), props.class)
)
</script>

<template>
  <button
    :type="props.type"
    :class="classes"
    :disabled="props.disabled || props.loading"
  >
    <Loader2 v-if="props.loading" class="h-4 w-4 animate-spin" />
    <slot />
  </button>
</template>
