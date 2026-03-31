<script setup lang="ts">
import { useRouter } from 'vue-router'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import { ArrowLeft, FolderGit2 } from 'lucide-vue-next'

const router = useRouter()
</script>

<template>
  <div class="animate-fade-in">
    <button
      class="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-kPrimary dark:hover:text-white transition-colors mb-4"
      @click="router.push('/projects')"
    >
      <ArrowLeft class="w-4 h-4" />
      Back to Projects
    </button>

    <PageHeader
      title="New Project"
      description="Create a new infrastructure project"
    />
    <div class="card p-12 text-center">
      <div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-kPrimary/5 dark:bg-neutral-800 flex items-center justify-center">
        <FolderGit2 class="w-7 h-7 text-gray-400" />
      </div>
      <h3 class="text-lg font-heading font-semibold text-kPrimary dark:text-white mb-2">
        Coming Soon
      </h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
        Project creation wizard with Git repository linking, Docker Compose import, and template selection.
      </p>
    </div>
  </div>
</template>
