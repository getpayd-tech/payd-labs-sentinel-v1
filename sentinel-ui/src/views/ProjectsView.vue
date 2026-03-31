<script setup lang="ts">
import PageHeader from '@/components/ui/PageHeader.vue'
import { FolderGit2 } from 'lucide-vue-next'
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader
      title="Projects"
      description="Manage your infrastructure projects"
    />
    <div class="card p-12 text-center">
      <div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-kPrimary/5 dark:bg-neutral-800 flex items-center justify-center">
        <FolderGit2 class="w-7 h-7 text-gray-400" />
      </div>
      <h3 class="text-lg font-heading font-semibold text-kPrimary dark:text-white mb-2">
        Coming Soon
      </h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
        Project management with Docker Compose support, environment configuration, and team collaboration.
      </p>
    </div>
  </div>
</template>
