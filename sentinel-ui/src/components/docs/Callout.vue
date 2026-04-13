<script setup lang="ts">
import { Info, AlertTriangle, CheckCircle2, AlertCircle } from 'lucide-vue-next'

defineProps<{
  type?: 'info' | 'warning' | 'success' | 'error'
  title?: string
}>()

const icons = { info: Info, warning: AlertTriangle, success: CheckCircle2, error: AlertCircle }
</script>

<template>
  <div class="flex gap-3 px-4 py-3.5 rounded-xl border my-4" :class="`callout-${type || 'info'}`">
    <component :is="icons[type || 'info']" :size="18" class="shrink-0 mt-0.5 callout-icon" />
    <div class="text-sm leading-relaxed text-text-secondary">
      <strong v-if="title" class="font-heading font-semibold mr-1 callout-title">{{ title }}</strong>
      <slot />
    </div>
  </div>
</template>
