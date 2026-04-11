<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { deploymentsService } from '@/services/deployments'
import { projectsService } from '@/services/projects'
import { relativeTime } from '@/utils/formatters'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Modal from '@/components/ui/Modal.vue'
import Input from '@/components/ui/Input.vue'
import { useToast } from 'vue-toastification'
import type { DeploymentStatus } from '@/types'
import {
  Rocket,
  RefreshCw,
  RotateCcw,
  Play,
  Filter,
  Clock,
  User,
  Tag,
  Loader2,
} from 'lucide-vue-next'

const queryClient = useQueryClient()
const toast = useToast()

const selectedProject = ref<string>('')
const showDeployModal = ref(false)
const deployProjectId = ref('')
const deployImageTag = ref('')

const { data: deployments, isLoading, isError, refetch } = useQuery({
  queryKey: ['deployments', selectedProject],
  queryFn: () =>
    deploymentsService.list(
      selectedProject.value
        ? { project_id: selectedProject.value, page_size: 50 }
        : { page_size: 50 }
    ),
  refetchInterval: 10000,
})

const { data: projects } = useQuery({
  queryKey: ['projects-list'],
  queryFn: () => projectsService.list(),
})

const items = computed(() => deployments.value?.items ?? [])

const deployMutation = useMutation({
  mutationFn: () =>
    deploymentsService.deploy(
      deployProjectId.value,
      deployImageTag.value ? { image_tag: deployImageTag.value } : undefined
    ),
  onSuccess: () => {
    toast.success('Deployment triggered successfully')
    showDeployModal.value = false
    deployProjectId.value = ''
    deployImageTag.value = ''
    queryClient.invalidateQueries({ queryKey: ['deployments'] })
  },
  onError: (e: any) => {
    toast.error(e.response?.data?.detail || 'Failed to trigger deployment')
  },
})

const rollbackMutation = useMutation({
  mutationFn: (params: { projectId: string; deploymentId: string }) =>
    deploymentsService.rollback(params.projectId, params.deploymentId),
  onSuccess: () => {
    toast.success('Rollback initiated')
    queryClient.invalidateQueries({ queryKey: ['deployments'] })
  },
  onError: () => {
    toast.error('Failed to initiate rollback')
  },
})

function getStatusVariant(status: DeploymentStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  const map: Record<DeploymentStatus, 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
    pending: 'neutral',
    in_progress: 'info',
    pulling: 'info',
    success: 'success',
    healthy: 'success',
    failed: 'error',
    rolled_back: 'warning',
  }
  return map[status] || 'neutral'
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '-'
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}m ${secs}s`
}

function openDeployModal() {
  deployProjectId.value = ''
  deployImageTag.value = ''
  showDeployModal.value = true
}
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader
      title="Deployments"
      description="Deployment history and pipeline management"
    >
      <template #actions>
        <Button variant="outline" size="sm" @click="refetch()">
          <RefreshCw class="w-4 h-4" />
          Refresh
        </Button>
        <Button variant="accent" size="sm" @click="openDeployModal">
          <Play class="w-4 h-4" />
          Deploy
        </Button>
      </template>
    </PageHeader>

    <!-- Filter bar -->
    <div class="flex items-center gap-3 mb-4">
      <div class="flex items-center gap-2 text-sm text-text-secondary">
        <Filter class="w-4 h-4" />
        <span>Filter by project:</span>
      </div>
      <select
        v-model="selectedProject"
        class="h-9 px-3 text-sm rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
      >
        <option value="">All Projects</option>
        <option v-for="project in projects" :key="project.id" :value="project.id">
          {{ project.display_name || project.name }}
        </option>
      </select>
    </div>

    <!-- Loading skeleton -->
    <div v-if="isLoading" class="card">
      <div v-for="i in 5" :key="i" class="flex items-center gap-4 p-4 border-b border-kPrimary/5 dark:border-neutral-800 last:border-0">
        <div class="skeleton h-9 w-9 rounded-lg" />
        <div class="flex-1">
          <div class="skeleton h-4 w-40 mb-2" />
          <div class="skeleton h-3 w-56" />
        </div>
        <div class="skeleton h-6 w-16 rounded-full" />
      </div>
    </div>

    <!-- Error state -->
    <div v-else-if="isError" class="card p-8 text-center">
      <p class="text-text-secondary">Failed to load deployments.</p>
      <Button variant="outline" size="sm" class="mt-3" @click="refetch()">Retry</Button>
    </div>

    <!-- Deployments table -->
    <div v-else class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-border">
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Project</th>
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3 hidden md:table-cell">Trigger</th>
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3 hidden lg:table-cell">Image Tag</th>
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Status</th>
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3 hidden md:table-cell">Duration</th>
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3 hidden lg:table-cell">Triggered By</th>
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Time</th>
              <th class="text-right text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="deploy in items"
              :key="deploy.id"
              class="border-b border-border last:border-0 hover:bg-surface-secondary transition-colors"
            >
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <div class="w-8 h-8 rounded-lg bg-surface-tertiary flex items-center justify-center shrink-0">
                    <Rocket class="w-4 h-4 text-text-secondary" />
                  </div>
                  <span class="text-sm font-semibold font-heading text-text">
                    {{ deploy.project_name }}
                  </span>
                </div>
              </td>
              <td class="px-4 py-3 hidden md:table-cell">
                <Badge variant="neutral" size="sm">{{ deploy.trigger }}</Badge>
              </td>
              <td class="px-4 py-3 hidden lg:table-cell">
                <div class="flex items-center gap-1.5 text-sm text-text-secondary">
                  <Tag class="w-3.5 h-3.5" />
                  <span class="font-mono text-xs">{{ deploy.image_tag || '-' }}</span>
                </div>
              </td>
              <td class="px-4 py-3">
                <Badge :variant="getStatusVariant(deploy.status)" size="sm">
                  <Loader2 v-if="deploy.status === 'pending' || deploy.status === 'pulling'" class="w-3 h-3 animate-spin mr-1" />
                  {{ deploy.status }}
                </Badge>
              </td>
              <td class="px-4 py-3 hidden md:table-cell">
                <div class="flex items-center gap-1.5 text-sm text-text-secondary">
                  <Clock class="w-3.5 h-3.5" />
                  {{ formatDuration(deploy.duration_seconds) }}
                </div>
              </td>
              <td class="px-4 py-3 hidden lg:table-cell">
                <div class="flex items-center gap-1.5 text-sm text-text-secondary">
                  <User class="w-3.5 h-3.5" />
                  {{ deploy.triggered_by }}
                </div>
              </td>
              <td class="px-4 py-3">
                <span class="text-sm text-text-secondary">
                  {{ deploy.started_at ? relativeTime(deploy.started_at) : '-' }}
                </span>
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center justify-end gap-1">
                  <button
                    class="p-1.5 rounded-md text-gray-400 hover:text-accent hover:bg-accent/10 transition-colors"
                    title="Redeploy"
                    :disabled="deployMutation.isPending.value"
                    @click="deployProjectId = deploy.project_id; deployMutation.mutate()"
                  >
                    <Play class="w-4 h-4" />
                  </button>
                  <button
                    v-if="deploy.status === 'failed' || deploy.status === 'success'"
                    class="p-1.5 rounded-md text-gray-400 hover:text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-950/30 transition-colors"
                    title="Rollback to this version"
                    :disabled="rollbackMutation.isPending.value"
                    @click="rollbackMutation.mutate({ projectId: deploy.project_id, deploymentId: deploy.id })"
                  >
                    <RotateCcw class="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Empty state -->
      <div v-if="items.length === 0" class="p-12 text-center">
        <div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-surface-tertiary flex items-center justify-center">
          <Rocket class="w-7 h-7 text-gray-400" />
        </div>
        <h3 class="text-lg font-heading font-semibold text-text mb-2">No deployments yet</h3>
        <p class="text-sm text-text-secondary max-w-md mx-auto">
          Trigger your first deployment to see it here.
        </p>
      </div>
    </div>

    <!-- Deploy Modal -->
    <Modal v-model="showDeployModal" title="Manual Deploy" size="md">
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-text mb-1.5">Project</label>
          <select
            v-model="deployProjectId"
            class="w-full h-10 px-3.5 text-sm rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
          >
            <option value="" disabled>Select a project</option>
            <option v-for="project in projects" :key="project.id" :value="project.id">
              {{ project.display_name || project.name }}
            </option>
          </select>
        </div>
        <Input
          v-model="deployImageTag"
          label="Image Tag (optional)"
          placeholder="e.g. latest, v1.2.3, sha-abc123"
        />
      </div>
      <template #footer>
        <div class="flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" @click="showDeployModal = false">Cancel</Button>
          <Button
            variant="accent"
            size="sm"
            :disabled="!deployProjectId"
            :loading="deployMutation.isPending.value"
            @click="deployMutation.mutate()"
          >
            <Play class="w-4 h-4" />
            Deploy
          </Button>
        </div>
      </template>
    </Modal>
  </div>
</template>
