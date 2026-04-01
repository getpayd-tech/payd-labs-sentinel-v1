<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { projectsService } from '@/services/projects'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import { useToast } from 'vue-toastification'
import type { ProjectType } from '@/types'
import {
  FolderGit2,
  Plus,
  ScanSearch,
  RefreshCw,
  Globe,
  Github,
  Container,
  ExternalLink,
} from 'lucide-vue-next'

const router = useRouter()
const queryClient = useQueryClient()
const toast = useToast()

const { data: projects, isLoading, isError, refetch } = useQuery({
  queryKey: ['projects'],
  queryFn: () => projectsService.list(),
})

const scanMutation = useMutation({
  mutationFn: () => projectsService.scan(),
  onSuccess: (result) => {
    toast.success(`Discovered ${result.total} project(s)`)
    queryClient.invalidateQueries({ queryKey: ['projects'] })
  },
  onError: () => {
    toast.error('Failed to scan for existing projects')
  },
})

function getTypeVariant(type: ProjectType): 'success' | 'info' | 'warning' | 'neutral' | 'error' {
  const map: Record<ProjectType, 'success' | 'info' | 'warning' | 'neutral' | 'error'> = {
    fastapi: 'success',
    vue: 'info',
    laravel: 'error',
    static: 'neutral',
    blended: 'warning',
  }
  return map[type] || 'neutral'
}

function getStatusVariant(status: string): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (status === 'running' || status === 'healthy') return 'success'
  if (status === 'stopped' || status === 'error') return 'error'
  if (status === 'provisioning') return 'info'
  return 'neutral'
}
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader
      title="Projects"
      description="Manage infrastructure projects"
    >
      <template #actions>
        <Button
          variant="outline"
          size="sm"
          :loading="scanMutation.isPending.value"
          @click="scanMutation.mutate()"
        >
          <ScanSearch class="w-4 h-4" />
          Scan Existing
        </Button>
        <Button variant="outline" size="sm" @click="refetch()">
          <RefreshCw class="w-4 h-4" />
          Refresh
        </Button>
        <Button variant="accent" size="sm" @click="router.push('/projects/new')">
          <Plus class="w-4 h-4" />
          New Project
        </Button>
      </template>
    </PageHeader>

    <!-- Loading skeleton -->
    <div v-if="isLoading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="i in 6" :key="i" class="card p-5">
        <div class="skeleton h-5 w-40 mb-3" />
        <div class="skeleton h-3 w-32 mb-2" />
        <div class="skeleton h-3 w-24 mb-4" />
        <div class="flex gap-2">
          <div class="skeleton h-5 w-14 rounded-full" />
          <div class="skeleton h-5 w-16 rounded-full" />
        </div>
      </div>
    </div>

    <!-- Error state -->
    <div v-else-if="isError" class="card p-8 text-center">
      <p class="text-gray-500 dark:text-gray-400">Failed to load projects.</p>
      <Button variant="outline" size="sm" class="mt-3" @click="refetch()">Retry</Button>
    </div>

    <!-- Projects grid -->
    <template v-else>
      <div
        v-if="projects && projects.length > 0"
        class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children"
      >
        <div
          v-for="project in projects"
          :key="project.id"
          class="card-hover p-5 cursor-pointer"
          @click="router.push(`/projects/${project.id}`)"
        >
          <!-- Header -->
          <div class="flex items-start justify-between gap-3 mb-3">
            <div class="flex items-center gap-2.5 min-w-0">
              <div class="w-10 h-10 rounded-lg bg-kPrimary/5 dark:bg-neutral-800 flex items-center justify-center shrink-0">
                <FolderGit2 class="w-5 h-5 text-kPrimary dark:text-gray-400" />
              </div>
              <div class="min-w-0">
                <h3 class="text-sm font-semibold font-heading text-kPrimary dark:text-white truncate">
                  {{ project.display_name || project.name }}
                </h3>
                <p class="text-2xs text-gray-400 truncate">{{ project.name }}</p>
              </div>
            </div>
            <Badge :variant="getStatusVariant(project.status)" size="sm">
              {{ project.status }}
            </Badge>
          </div>

          <!-- Details -->
          <div class="space-y-2 mb-3">
            <div v-if="project.domain" class="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
              <Globe class="w-3.5 h-3.5 shrink-0" />
              <span class="truncate">{{ project.domain }}</span>
            </div>
            <div v-if="project.github_repo" class="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
              <Github class="w-3.5 h-3.5 shrink-0" />
              <a
                :href="`https://github.com/${project.github_repo}`"
                target="_blank"
                class="truncate hover:text-accent transition-colors"
                @click.stop
              >
                {{ project.github_repo }}
                <ExternalLink class="w-3 h-3 inline ml-0.5" />
              </a>
            </div>
            <div class="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
              <Container class="w-3.5 h-3.5 shrink-0" />
              <span>{{ project.container_count }} container{{ project.container_count !== 1 ? 's' : '' }}</span>
            </div>
          </div>

          <!-- Badges -->
          <div class="flex items-center gap-2">
            <Badge :variant="getTypeVariant(project.type)" size="sm">{{ project.type }}</Badge>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="card p-12 text-center">
        <div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-kPrimary/5 dark:bg-neutral-800 flex items-center justify-center">
          <FolderGit2 class="w-7 h-7 text-gray-400" />
        </div>
        <h3 class="text-lg font-heading font-semibold text-kPrimary dark:text-white mb-2">
          No projects yet
        </h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto mb-4">
          Create your first project or scan for existing ones.
        </p>
        <div class="flex items-center justify-center gap-2">
          <Button variant="outline" size="sm" @click="scanMutation.mutate()">
            <ScanSearch class="w-4 h-4" />
            Scan Existing
          </Button>
          <Button variant="accent" size="sm" @click="router.push('/projects/new')">
            <Plus class="w-4 h-4" />
            New Project
          </Button>
        </div>
      </div>
    </template>
  </div>
</template>
