<script setup lang="ts">
defineProps<{
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  path: string
}>()

const methodStyles: Record<string, string> = {
  GET: 'bg-blue-50 text-blue-600 border-blue-200 dark:bg-blue-500/10 dark:text-blue-400 dark:border-blue-500/20',
  POST: 'bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20',
  PUT: 'bg-amber-50 text-amber-600 border-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/20',
  DELETE: 'bg-red-50 text-red-600 border-red-200 dark:bg-red-500/10 dark:text-red-400 dark:border-red-500/20',
  PATCH: 'bg-purple-50 text-purple-600 border-purple-200 dark:bg-purple-500/10 dark:text-purple-400 dark:border-purple-500/20',
}
</script>

<template>
  <div class="flex items-center gap-3 px-4 py-3 rounded-xl bg-surface-secondary border border-border font-mono text-sm my-4">
    <span class="px-2.5 py-1 rounded-lg text-xs font-bold border" :class="methodStyles[method]">
      {{ method }}
    </span>
    <code class="text-text font-medium">{{ path }}</code>
  </div>
</template>
