<script setup lang="ts">
import { computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { cn } from '@/utils/formatters'
import { X } from 'lucide-vue-next'

interface Props {
  modelValue: boolean
  title?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  class?: string
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const sizes: Record<string, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
}

const panelClasses = computed(() =>
  cn(
    'relative w-full rounded-xl bg-white shadow-strong dark:bg-neutral-900 border border-kPrimary/10 dark:border-neutral-800 animate-scale-in',
    sizes[props.size],
    props.class
  )
)

function close() {
  emit('update:modelValue', false)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
  }
)

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="modelValue"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <!-- Backdrop -->
        <div
          class="absolute inset-0 bg-kPrimary/40 dark:bg-black/60 backdrop-blur-sm"
          @click="close"
        />

        <!-- Panel -->
        <div :class="panelClasses">
          <!-- Header -->
          <div
            v-if="title || $slots.header"
            class="flex items-center justify-between px-5 py-4 border-b border-kPrimary/10 dark:border-neutral-800"
          >
            <slot name="header">
              <h3 class="text-lg font-heading font-semibold text-kPrimary dark:text-white">
                {{ title }}
              </h3>
            </slot>
            <button
              class="rounded-lg p-1.5 text-gray-400 hover:text-kPrimary hover:bg-gray-100 dark:hover:text-white dark:hover:bg-neutral-800 transition-colors"
              @click="close"
            >
              <X class="h-4 w-4" />
            </button>
          </div>

          <!-- Body -->
          <div class="px-5 py-4">
            <slot />
          </div>

          <!-- Footer -->
          <div
            v-if="$slots.footer"
            class="px-5 py-3 border-t border-kPrimary/10 dark:border-neutral-800 bg-gray-50/50 dark:bg-neutral-900/50 rounded-b-xl"
          >
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
