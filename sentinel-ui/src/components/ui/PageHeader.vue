<script setup lang="ts">
interface Props {
  title: string
  description?: string
}

defineProps<Props>()
</script>

<template>
  <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
    <div>
      <h1 class="text-2xl font-heading font-semibold text-kPrimary dark:text-white">
        {{ title }}
      </h1>
      <p v-if="description" class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        {{ description }}
      </p>
    </div>
    <div v-if="$slots.actions" class="flex items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>
