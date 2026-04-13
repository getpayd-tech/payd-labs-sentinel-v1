<script setup lang="ts">
defineProps<{
  params: Array<{
    name: string
    type: string
    required: boolean
    description: string
  }>
}>()
</script>

<template>
  <div class="hidden sm:block rounded-xl border border-border overflow-hidden my-4">
    <table class="w-full">
      <thead>
        <tr class="bg-surface-secondary border-b border-border">
          <th class="text-left px-4 py-2.5 font-heading font-semibold text-text-secondary text-xs uppercase tracking-wider">Parameter</th>
          <th class="text-left px-4 py-2.5 font-heading font-semibold text-text-secondary text-xs uppercase tracking-wider">Type</th>
          <th class="text-left px-4 py-2.5 font-heading font-semibold text-text-secondary text-xs uppercase tracking-wider">Required</th>
          <th class="text-left px-4 py-2.5 font-heading font-semibold text-text-secondary text-xs uppercase tracking-wider">Description</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in params" :key="p.name" class="border-b border-border/50 last:border-0 hover:bg-surface-secondary/50 transition-colors">
          <td class="px-4 py-2.5"><code class="text-xs font-mono font-semibold text-accent bg-accent/10 px-1.5 py-0.5 rounded">{{ p.name }}</code></td>
          <td class="px-4 py-2.5"><span class="text-xs font-mono text-text-secondary">{{ p.type }}</span></td>
          <td class="px-4 py-2.5">
            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold"
              :class="p.required ? 'bg-accent/10 text-accent' : 'bg-surface-tertiary text-text-tertiary'">
              {{ p.required ? 'Required' : 'Optional' }}
            </span>
          </td>
          <td class="px-4 py-2.5 text-sm text-text-secondary">{{ p.description }}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="sm:hidden space-y-2 my-4">
    <div v-for="p in params" :key="p.name" class="rounded-xl border border-border p-3 bg-surface-secondary/30">
      <div class="flex items-center justify-between mb-1.5">
        <code class="text-xs font-mono font-semibold text-accent bg-accent/10 px-1.5 py-0.5 rounded">{{ p.name }}</code>
        <span class="text-[9px] font-semibold px-1.5 py-0.5 rounded-full"
          :class="p.required ? 'bg-accent/10 text-accent' : 'bg-surface-tertiary text-text-tertiary'">
          {{ p.required ? 'Required' : 'Optional' }}
        </span>
      </div>
      <div class="text-[11px] font-mono text-text-tertiary mb-1">{{ p.type }}</div>
      <div class="text-xs text-text-secondary">{{ p.description }}</div>
    </div>
  </div>
</template>
