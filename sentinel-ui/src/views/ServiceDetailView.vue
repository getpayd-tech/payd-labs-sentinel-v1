<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { servicesService } from '@/services/services'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import { useToast } from 'vue-toastification'
import {
  ArrowLeft,
  RotateCw,
  Square,
  Play,
  RefreshCw,
  Network,
  HardDrive,
  Clock,
  Tag,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const toast = useToast()

const containerName = computed(() => route.params.name as string)
const logViewerRef = ref<HTMLDivElement | null>(null)

const { data: container, isLoading, isError } = useQuery({
  queryKey: ['container', containerName],
  queryFn: () => servicesService.getContainer(containerName.value),
  refetchInterval: 10000,
})

const { data: logs, isLoading: logsLoading, refetch: refetchLogs } = useQuery({
  queryKey: ['container-logs', containerName],
  queryFn: () => servicesService.getContainerLogs(containerName.value, 200),
})

// Auto-scroll to bottom when logs update
watch(
  () => logs.value,
  async () => {
    await nextTick()
    if (logViewerRef.value) {
      logViewerRef.value.scrollTop = logViewerRef.value.scrollHeight
    }
  }
)

const restartMutation = useMutation({
  mutationFn: () => servicesService.restartContainer(containerName.value),
  onSuccess: (data) => {
    toast.success(data.message)
    queryClient.invalidateQueries({ queryKey: ['container', containerName.value] })
  },
  onError: () => toast.error('Failed to restart container'),
})

const stopMutation = useMutation({
  mutationFn: () => servicesService.stopContainer(containerName.value),
  onSuccess: (data) => {
    toast.success(data.message)
    queryClient.invalidateQueries({ queryKey: ['container', containerName.value] })
  },
  onError: () => toast.error('Failed to stop container'),
})

const startMutation = useMutation({
  mutationFn: () => servicesService.startContainer(containerName.value),
  onSuccess: (data) => {
    toast.success(data.message)
    queryClient.invalidateQueries({ queryKey: ['container', containerName.value] })
  },
  onError: () => toast.error('Failed to start container'),
})

function getStatusVariant(status?: string, health?: string): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (health === 'unhealthy') return 'warning'
  if (status === 'running') return 'success'
  if (status === 'stopped' || status === 'exited') return 'error'
  if (status === 'restarting') return 'warning'
  return 'neutral'
}
</script>

<template>
  <div class="animate-fade-in">
    <!-- Back button -->
    <button
      class="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-kPrimary dark:hover:text-white transition-colors mb-4"
      @click="router.push('/services')"
    >
      <ArrowLeft class="w-4 h-4" />
      Back to Services
    </button>

    <!-- Loading -->
    <div v-if="isLoading" class="space-y-4">
      <div class="card p-6">
        <div class="skeleton h-6 w-48 mb-3" />
        <div class="skeleton h-4 w-72 mb-2" />
        <div class="skeleton h-4 w-40" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="isError" class="card p-8 text-center">
      <p class="text-gray-500 dark:text-gray-400">Failed to load container details.</p>
      <Button variant="outline" size="sm" class="mt-3" @click="router.push('/services')">
        Go Back
      </Button>
    </div>

    <template v-else-if="container">
      <!-- Container info -->
      <div class="card p-5 mb-4">
        <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-4">
          <div>
            <div class="flex items-center gap-3 mb-1">
              <h1 class="text-xl font-heading font-bold text-kPrimary dark:text-white">
                {{ container.name }}
              </h1>
              <Badge :variant="getStatusVariant(container.status, container.health)" size="sm">
                {{ container.health === 'unhealthy' ? 'unhealthy' : container.status }}
              </Badge>
            </div>
            <p class="text-sm text-gray-500 dark:text-gray-400">{{ container.image }}</p>
          </div>

          <div class="flex items-center gap-2">
            <Button
              v-if="container.status === 'running'"
              variant="outline"
              size="sm"
              :loading="restartMutation.isPending.value"
              @click="restartMutation.mutate()"
            >
              <RotateCw class="w-4 h-4" />
              Restart
            </Button>
            <Button
              v-if="container.status === 'running'"
              variant="danger"
              size="sm"
              :loading="stopMutation.isPending.value"
              @click="stopMutation.mutate()"
            >
              <Square class="w-4 h-4" />
              Stop
            </Button>
            <Button
              v-if="container.status !== 'running'"
              variant="accent"
              size="sm"
              :loading="startMutation.isPending.value"
              @click="startMutation.mutate()"
            >
              <Play class="w-4 h-4" />
              Start
            </Button>
          </div>
        </div>

        <!-- Details grid -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div v-if="container.started_at" class="flex items-center gap-2 text-sm">
            <Clock class="w-4 h-4 text-gray-400" />
            <span class="text-gray-500 dark:text-gray-400">Started:</span>
            <span class="font-medium text-kPrimary dark:text-white">{{ container.started_at }}</span>
          </div>
          <div class="flex items-center gap-2 text-sm">
            <Tag class="w-4 h-4 text-gray-400" />
            <span class="text-gray-500 dark:text-gray-400">ID:</span>
            <span class="font-mono text-xs text-kPrimary dark:text-white">{{ container.id }}</span>
          </div>
          <div class="flex items-center gap-2 text-sm">
            <RotateCw class="w-4 h-4 text-gray-400" />
            <span class="text-gray-500 dark:text-gray-400">Restarts:</span>
            <span class="font-medium text-kPrimary dark:text-white">{{ container.restart_count }}</span>
          </div>
        </div>
      </div>

      <!-- Networks & Volumes -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div class="card p-4">
          <div class="flex items-center gap-2 mb-3">
            <Network class="w-4 h-4 text-accent" />
            <h3 class="text-sm font-semibold font-heading text-kPrimary dark:text-white">Networks</h3>
          </div>
          <div v-if="container.networks.length > 0" class="flex flex-wrap gap-1.5">
            <Badge v-for="net in container.networks" :key="net" variant="info" size="sm">
              {{ net }}
            </Badge>
          </div>
          <p v-else class="text-sm text-gray-400">No networks</p>
        </div>

        <div class="card p-4">
          <div class="flex items-center gap-2 mb-3">
            <HardDrive class="w-4 h-4 text-accent" />
            <h3 class="text-sm font-semibold font-heading text-kPrimary dark:text-white">Volumes</h3>
          </div>
          <div v-if="container.volumes.length > 0" class="space-y-1">
            <p
              v-for="vol in container.volumes"
              :key="vol"
              class="text-xs font-mono text-gray-500 dark:text-gray-400 truncate"
            >
              {{ vol }}
            </p>
          </div>
          <p v-else class="text-sm text-gray-400">No volumes</p>
        </div>
      </div>

      <!-- Logs -->
      <div class="card overflow-hidden">
        <div class="flex items-center justify-between px-4 py-3 border-b border-kPrimary/10 dark:border-neutral-800">
          <h3 class="text-sm font-semibold font-heading text-kPrimary dark:text-white">Logs</h3>
          <Button variant="ghost" size="xs" @click="refetchLogs()">
            <RefreshCw class="w-3.5 h-3.5" />
            Refresh
          </Button>
        </div>
        <div
          ref="logViewerRef"
          class="bg-neutral-950 p-4 h-80 overflow-y-auto custom-scrollbar font-mono text-xs leading-relaxed"
        >
          <div v-if="logsLoading" class="text-gray-500">Loading logs...</div>
          <div v-else-if="logs && logs.logs.length > 0">
            <div
              v-for="(entry, index) in logs.logs"
              :key="index"
              :class="[
                'py-0.5',
                entry.stream === 'stderr' ? 'text-red-400' : 'text-gray-300',
              ]"
            >
              <span class="text-gray-600 mr-2 select-none">{{ entry.timestamp }}</span>
              <span>{{ entry.message }}</span>
            </div>
          </div>
          <div v-else class="text-gray-500">No logs available</div>
        </div>
      </div>
    </template>
  </div>
</template>
