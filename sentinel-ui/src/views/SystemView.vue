<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { systemService } from '@/services/system'
import { formatPercent, formatUptime } from '@/utils/formatters'
import PageHeader from '@/components/ui/PageHeader.vue'
import Card from '@/components/ui/Card.vue'
import { Cpu, MemoryStick, HardDrive, Network, Activity, Server } from 'lucide-vue-next'

const { data: metrics, isLoading, isError } = useQuery({
  queryKey: ['system-metrics'],
  queryFn: () => systemService.getMetrics(),
  refetchInterval: 5000,
})

const cpuPercent = computed(() => metrics.value?.cpu_percent ?? 0)
const memPercent = computed(() => metrics.value?.memory_percent ?? 0)
const diskPercent = computed(() => metrics.value?.disk_percent ?? 0)

function getUsageColor(percent: number): string {
  if (percent >= 90) return 'bg-red-500'
  if (percent >= 70) return 'bg-yellow-500'
  return 'bg-accent'
}

function formatGb(gb: number): string {
  return `${gb.toFixed(1)} GB`
}

function formatMb(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
  return `${mb.toFixed(0)} MB`
}
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader
      title="System"
      description="Server metrics and resource usage"
    />

    <!-- Loading -->
    <div v-if="isLoading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="i in 6" :key="i" class="card p-5">
        <div class="skeleton h-4 w-24 mb-4" />
        <div class="skeleton h-8 w-32 mb-2" />
        <div class="skeleton h-2 w-full rounded-full" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="isError" class="card p-8 text-center">
      <p class="text-gray-500 dark:text-gray-400">Failed to load system metrics.</p>
    </div>

    <!-- Metrics -->
    <template v-else-if="metrics">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
        <!-- CPU -->
        <Card>
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
              <Cpu class="w-5 h-5 text-accent" />
            </div>
            <div>
              <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">CPU Usage</p>
              <p class="text-2xl font-heading font-bold text-kPrimary dark:text-white">
                {{ formatPercent(cpuPercent) }}
              </p>
            </div>
          </div>
          <div class="w-full h-2 bg-gray-100 dark:bg-neutral-800 rounded-full overflow-hidden">
            <div
              :class="['h-full rounded-full transition-all duration-500', getUsageColor(cpuPercent)]"
              :style="{ width: `${cpuPercent}%` }"
            />
          </div>
          <p class="text-xs text-gray-400 mt-2">{{ metrics.cpu_count }} cores</p>
        </Card>

        <!-- Memory -->
        <Card>
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-950/30 flex items-center justify-center">
              <MemoryStick class="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Memory</p>
              <p class="text-2xl font-heading font-bold text-kPrimary dark:text-white">
                {{ formatPercent(memPercent) }}
              </p>
            </div>
          </div>
          <div class="w-full h-2 bg-gray-100 dark:bg-neutral-800 rounded-full overflow-hidden">
            <div
              :class="['h-full rounded-full transition-all duration-500', getUsageColor(memPercent)]"
              :style="{ width: `${memPercent}%` }"
            />
          </div>
          <p class="text-xs text-gray-400 mt-2">
            {{ formatMb(metrics.memory_used_mb) }} / {{ formatMb(metrics.memory_total_mb) }}
          </p>
        </Card>

        <!-- Disk -->
        <Card>
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-lg bg-purple-50 dark:bg-purple-950/30 flex items-center justify-center">
              <HardDrive class="w-5 h-5 text-purple-500" />
            </div>
            <div>
              <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Disk</p>
              <p class="text-2xl font-heading font-bold text-kPrimary dark:text-white">
                {{ formatPercent(diskPercent) }}
              </p>
            </div>
          </div>
          <div class="w-full h-2 bg-gray-100 dark:bg-neutral-800 rounded-full overflow-hidden">
            <div
              :class="['h-full rounded-full transition-all duration-500', getUsageColor(diskPercent)]"
              :style="{ width: `${diskPercent}%` }"
            />
          </div>
          <p class="text-xs text-gray-400 mt-2">
            {{ formatGb(metrics.disk_used_gb) }} / {{ formatGb(metrics.disk_total_gb) }}
          </p>
        </Card>

        <!-- Network -->
        <Card>
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-lg bg-orange-50 dark:bg-orange-950/30 flex items-center justify-center">
              <Network class="w-5 h-5 text-orange-500" />
            </div>
            <div>
              <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Network I/O</p>
            </div>
          </div>
          <div class="space-y-2">
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">Sent</span>
              <span class="font-medium text-kPrimary dark:text-white">{{ formatMb(metrics.network_tx_mb) }}</span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">Received</span>
              <span class="font-medium text-kPrimary dark:text-white">{{ formatMb(metrics.network_rx_mb) }}</span>
            </div>
          </div>
        </Card>

        <!-- Load Average -->
        <Card>
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 flex items-center justify-center">
              <Activity class="w-5 h-5 text-emerald-500" />
            </div>
            <div>
              <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Load Average</p>
            </div>
          </div>
          <div class="flex items-center gap-4">
            <div class="text-center">
              <p class="text-xl font-heading font-bold text-kPrimary dark:text-white">
                {{ metrics.load_average[0]?.toFixed(2) ?? '-' }}
              </p>
              <p class="text-2xs text-gray-400">1 min</p>
            </div>
            <div class="text-center">
              <p class="text-xl font-heading font-bold text-kPrimary dark:text-white">
                {{ metrics.load_average[1]?.toFixed(2) ?? '-' }}
              </p>
              <p class="text-2xs text-gray-400">5 min</p>
            </div>
            <div class="text-center">
              <p class="text-xl font-heading font-bold text-kPrimary dark:text-white">
                {{ metrics.load_average[2]?.toFixed(2) ?? '-' }}
              </p>
              <p class="text-2xs text-gray-400">15 min</p>
            </div>
          </div>
        </Card>

        <!-- Server Info -->
        <Card>
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-lg bg-kPrimary/5 dark:bg-neutral-800 flex items-center justify-center">
              <Server class="w-5 h-5 text-kPrimary dark:text-gray-400" />
            </div>
            <div>
              <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Server Info</p>
            </div>
          </div>
          <div class="space-y-2">
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">Uptime</span>
              <span class="font-medium text-kPrimary dark:text-white">{{ formatUptime(metrics.uptime_seconds) }}</span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-gray-500 dark:text-gray-400">CPU Cores</span>
              <span class="font-medium text-kPrimary dark:text-white">{{ metrics.cpu_count }}</span>
            </div>
          </div>
        </Card>
      </div>
    </template>
  </div>
</template>
