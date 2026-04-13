<script setup lang="ts">
import { CheckCircle2, XCircle } from 'lucide-vue-next'
import CodeBlock from './CodeBlock.vue'

defineProps<{
  title?: string
  status?: number
  description?: string
  code: string
}>()

const isSuccess = (s?: number) => s !== undefined && s >= 200 && s < 300
</script>

<template>
  <div class="my-4">
    <div class="flex items-center gap-2 mb-2">
      <CheckCircle2 v-if="isSuccess(status)" :size="16" class="text-accent" />
      <XCircle v-else-if="status" :size="16" class="text-red-500" />
      <span v-if="title" class="text-sm font-heading font-semibold" :class="isSuccess(status) ? 'text-accent' : status ? 'text-red-500' : 'text-text'">
        {{ title }}
      </span>
      <span v-if="status" class="text-xs font-mono text-text-tertiary">{{ status }}</span>
    </div>
    <p v-if="description" class="text-sm text-text-secondary mb-2">{{ description }}</p>
    <CodeBlock :code="code" language="json" />
  </div>
</template>
