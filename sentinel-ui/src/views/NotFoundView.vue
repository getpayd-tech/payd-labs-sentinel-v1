<script setup lang="ts">
import { useRouter } from 'vue-router'
import Button from '@/components/ui/Button.vue'
import { Home, AlertTriangle } from 'lucide-vue-next'

const router = useRouter()
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-neutral-950 p-4">
    <div class="text-center max-w-md animate-fade-in-up">
      <div class="w-16 h-16 mx-auto mb-6 rounded-2xl bg-surface-tertiary flex items-center justify-center">
        <AlertTriangle class="w-8 h-8 text-gray-400" />
      </div>
      <h1 class="text-4xl font-heading font-bold text-text mb-2">
        404
      </h1>
      <p class="text-lg text-text-secondary mb-6">
        Page not found
      </p>
      <p class="text-sm text-gray-400 dark:text-gray-500 mb-8">
        The page you are looking for does not exist or has been moved.
      </p>
      <Button variant="accent" @click="router.push('/')">
        <Home class="w-4 h-4" />
        Back to Dashboard
      </Button>
    </div>
  </div>
</template>
