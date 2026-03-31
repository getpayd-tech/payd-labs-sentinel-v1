<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { dashboardService } from '@/services/dashboard'
import { formatNumber } from '@/utils/formatters'
import PageHeader from '@/components/ui/PageHeader.vue'
import MetricWidget from '@/components/dashboard/MetricWidget.vue'
import ServiceCard from '@/components/dashboard/ServiceCard.vue'
import { Container, Cpu, HardDrive, MemoryStick } from 'lucide-vue-next'

const { data: stats, isLoading, isError } = useQuery({
  queryKey: ['dashboard-stats'],
  queryFn: () => dashboardService.getStats(),
  refetchInterval: 10000,
})

const totalContainers = computed(() => stats.value?.total_containers ?? 0)
const runningContainers = computed(() => stats.value?.running_containers ?? 0)
const cpuUsage = computed(() => `${(stats.value?.system?.cpu_percent ?? 0).toFixed(1)}%`)
const memoryUsage = computed(() => `${(stats.value?.system?.memory_percent ?? 0).toFixed(1)}%`)
const memoryDetail = computed(() => {
  if (!stats.value?.system) return ''
  const used = (stats.value.system.memory_used_mb / 1024).toFixed(1)
  const total = (stats.value.system.memory_total_mb / 1024).toFixed(1)
  return `${used} / ${total} GB`
})
const containers = computed(() => stats.value?.containers ?? [])
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader
      title="Dashboard"
      description="Server overview and container health"
    />

    <!-- Loading skeleton -->
    <template v-if="isLoading">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div v-for="i in 4" :key="i" class="card p-4">
          <div class="skeleton h-3 w-24 mb-3" />
          <div class="skeleton h-8 w-16" />
        </div>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="i in 6" :key="i" class="card p-4">
          <div class="skeleton h-4 w-32 mb-2" />
          <div class="skeleton h-3 w-20 mb-3" />
          <div class="skeleton h-3 w-16" />
        </div>
      </div>
    </template>

    <!-- Error state -->
    <div v-else-if="isError" class="card p-8 text-center">
      <p class="text-gray-500 dark:text-gray-400">Failed to load dashboard data. Please try again.</p>
    </div>

    <!-- Content -->
    <template v-else>
      <!-- Metric widgets -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6 stagger-children">
        <MetricWidget
          label="Total Containers"
          :value="String(totalContainers)"
          :icon="Container"
        />
        <MetricWidget
          label="Running"
          :value="String(runningContainers)"
          :icon="Container"
          :trend="runningContainers === totalContainers ? 'up' : 'neutral'"
          :trend-value="runningContainers === totalContainers ? 'All healthy' : `${totalContainers - runningContainers} down`"
        />
        <MetricWidget
          label="CPU Usage"
          :value="cpuUsage"
          :icon="Cpu"
          :trend="(stats?.system?.cpu_percent ?? 0) > 80 ? 'down' : 'neutral'"
        />
        <MetricWidget
          label="Memory"
          :value="memoryUsage"
          :icon="MemoryStick"
          trend="neutral"
          :trend-value="memoryDetail"
        />
      </div>

      <!-- Services grid -->
      <div class="mb-4">
        <h2 class="text-lg font-heading font-semibold text-kPrimary dark:text-white mb-3">
          Containers
        </h2>
      </div>

      <div
        v-if="containers.length > 0"
        class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children"
      >
        <ServiceCard
          v-for="container in containers"
          :key="container.name"
          :container="container"
        />
      </div>
      <div v-else class="card p-8 text-center">
        <HardDrive class="w-8 h-8 mx-auto text-gray-300 dark:text-gray-600 mb-2" />
        <p class="text-gray-500 dark:text-gray-400">No containers found</p>
      </div>
    </template>
  </div>
</template>
