<script setup lang="ts">
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useRouter } from 'vue-router'
import { servicesService } from '@/services/services'
import { truncate } from '@/utils/formatters'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import { Container, RotateCw, Square, Play, RefreshCw } from 'lucide-vue-next'
import { useToast } from 'vue-toastification'

const router = useRouter()
const queryClient = useQueryClient()
const toast = useToast()

const { data: containers, isLoading, isError, refetch } = useQuery({
  queryKey: ['containers'],
  queryFn: () => servicesService.listContainers(),
  refetchInterval: 10000,
})

const restartMutation = useMutation({
  mutationFn: (name: string) => servicesService.restartContainer(name),
  onSuccess: (data) => {
    toast.success(data.message)
    queryClient.invalidateQueries({ queryKey: ['containers'] })
  },
  onError: () => {
    toast.error('Failed to restart container')
  },
})

const stopMutation = useMutation({
  mutationFn: (name: string) => servicesService.stopContainer(name),
  onSuccess: (data) => {
    toast.success(data.message)
    queryClient.invalidateQueries({ queryKey: ['containers'] })
  },
  onError: () => {
    toast.error('Failed to stop container')
  },
})

const startMutation = useMutation({
  mutationFn: (name: string) => servicesService.startContainer(name),
  onSuccess: (data) => {
    toast.success(data.message)
    queryClient.invalidateQueries({ queryKey: ['containers'] })
  },
  onError: () => {
    toast.error('Failed to start container')
  },
})

function getStatusVariant(status: string, health?: string | null): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (health === 'unhealthy') return 'warning'
  if (status === 'running') return 'success'
  if (status === 'stopped' || status === 'exited') return 'error'
  if (status === 'restarting') return 'warning'
  if (status === 'paused') return 'info'
  return 'neutral'
}

function navigateToDetail(name: string) {
  router.push(`/services/${name}`)
}
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader
      title="Services"
      description="Manage Docker containers"
    >
      <template #actions>
        <Button variant="outline" size="sm" @click="refetch()">
          <RefreshCw class="w-4 h-4" />
          Refresh
        </Button>
      </template>
    </PageHeader>

    <!-- Loading -->
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

    <!-- Error -->
    <div v-else-if="isError" class="card p-8 text-center">
      <p class="text-gray-500 dark:text-gray-400">Failed to load containers.</p>
      <Button variant="outline" size="sm" class="mt-3" @click="refetch()">Retry</Button>
    </div>

    <!-- Table -->
    <div v-else class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-kPrimary/10 dark:border-neutral-800">
              <th class="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-4 py-3">
                Container
              </th>
              <th class="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-4 py-3">
                Image
              </th>
              <th class="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-4 py-3">
                Status
              </th>
              <th class="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-4 py-3 hidden md:table-cell">
                Memory
              </th>
              <th class="text-right text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-4 py-3">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="container in containers"
              :key="container.name"
              class="border-b border-kPrimary/5 dark:border-neutral-800/50 last:border-0 hover:bg-gray-50 dark:hover:bg-neutral-800/30 cursor-pointer transition-colors"
              @click="navigateToDetail(container.name)"
            >
              <td class="px-4 py-3">
                <div class="flex items-center gap-2.5">
                  <div class="w-8 h-8 rounded-lg bg-kPrimary/5 dark:bg-neutral-800 flex items-center justify-center shrink-0">
                    <Container class="w-4 h-4 text-kPrimary dark:text-gray-400" />
                  </div>
                  <span class="text-sm font-semibold font-heading text-kPrimary dark:text-white">
                    {{ container.name }}
                  </span>
                </div>
              </td>
              <td class="px-4 py-3">
                <span class="text-sm text-gray-500 dark:text-gray-400">
                  {{ truncate(container.image, 40) }}
                </span>
              </td>
              <td class="px-4 py-3">
                <Badge :variant="getStatusVariant(container.status, container.health)" size="sm">
                  {{ container.health === 'unhealthy' ? 'unhealthy' : container.status }}
                </Badge>
              </td>
              <td class="px-4 py-3 hidden md:table-cell">
                <span class="text-sm text-gray-500 dark:text-gray-400">
                  {{ container.memory_usage_mb > 0 ? `${container.memory_usage_mb.toFixed(0)} MB` : '-' }}
                </span>
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center justify-end gap-1" @click.stop>
                  <button
                    v-if="container.status === 'running'"
                    class="p-1.5 rounded-md text-gray-400 hover:text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-950/30 transition-colors"
                    title="Restart"
                    :disabled="restartMutation.isPending.value"
                    @click="restartMutation.mutate(container.name)"
                  >
                    <RotateCw class="w-4 h-4" />
                  </button>
                  <button
                    v-if="container.status === 'running'"
                    class="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                    title="Stop"
                    :disabled="stopMutation.isPending.value"
                    @click="stopMutation.mutate(container.name)"
                  >
                    <Square class="w-4 h-4" />
                  </button>
                  <button
                    v-if="container.status !== 'running'"
                    class="p-1.5 rounded-md text-gray-400 hover:text-accent hover:bg-accent/10 transition-colors"
                    title="Start"
                    :disabled="startMutation.isPending.value"
                    @click="startMutation.mutate(container.name)"
                  >
                    <Play class="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="containers && containers.length === 0" class="p-8 text-center">
        <p class="text-gray-500 dark:text-gray-400">No containers found.</p>
      </div>
    </div>
  </div>
</template>
