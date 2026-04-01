<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/utils/formatters'

interface Props {
  modelValue?: string
  label?: string
  placeholder?: string
  type?: string
  error?: string
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  class?: string
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  size: 'md',
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const sizes: Record<string, string> = {
  sm: 'h-8 px-3 text-sm',
  md: 'h-10 px-3.5 text-sm',
  lg: 'h-12 px-4 text-base',
}

const inputClasses = computed(() => {
  const base =
    'w-full rounded-lg border bg-surface text-text font-body transition-all duration-200 placeholder:text-text-tertiary focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50'

  const borderClass = props.error
    ? 'border-red-300 focus:border-red-500 focus:ring-red-500/20 dark:border-red-800'
    : 'border-border focus:border-accent focus:ring-accent/20'

  return cn(base, borderClass, sizes[props.size], props.class)
})

function onInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', target.value)
}
</script>

<template>
  <div class="w-full">
    <label
      v-if="props.label"
      class="block text-sm font-medium text-text mb-1.5"
    >
      {{ props.label }}
    </label>
    <div class="relative">
      <div v-if="$slots.left" class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary">
        <slot name="left" />
      </div>
      <input
        :type="props.type"
        :value="props.modelValue"
        :placeholder="props.placeholder"
        :disabled="props.disabled"
        :class="[inputClasses, $slots.left ? 'pl-10' : '', $slots.right ? 'pr-10' : '']"
        @input="onInput"
      />
      <div v-if="$slots.right" class="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary">
        <slot name="right" />
      </div>
    </div>
    <p v-if="props.error" class="mt-1 text-sm text-red-500 dark:text-red-400">
      {{ props.error }}
    </p>
  </div>
</template>
