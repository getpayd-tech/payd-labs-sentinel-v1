<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { logsService } from '@/services/logs'
import { dashboardService } from '@/services/dashboard'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import {
  ScrollText,
  RefreshCw,
  Search,
  Filter,
  ChevronDown,
} from 'lucide-vue-next'

const selectedContainers = ref<string[]>([])
const searchQuery = ref('')
const debouncedSearch = ref('')
const streamFilter = ref<'all' | 'stdout' | 'stderr'>('all')
const tailCount = ref(200)
const showContainerDropdown = ref(false)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(searchQuery, (val) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    debouncedSearch.value = val
  }, 300)
})

const logViewerRef = ref<HTMLDivElement | null>(null)

// Get container list from dashboard stats
const { data: dashboardStats } = useQuery({
  queryKey: ['dashboard-stats'],
  queryFn: () => dashboardService.getStats(),
})

const containerList = computed(() => {
  return dashboardStats.value?.containers.map((c) => c.name) ?? []
})

// Fetch logs
const { data: logs, isLoading, isError, refetch } = useQuery({
  queryKey: ['aggregated-logs', selectedContainers, debouncedSearch, streamFilter, tailCount],
  queryFn: () =>
    logsService.getAggregatedLogs({
      containers: selectedContainers.value.length > 0 ? selectedContainers.value : undefined,
      search: debouncedSearch.value || undefined,
      stream: streamFilter.value,
      tail: tailCount.value,
    }),
  refetchInterval: false,
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

function toggleContainer(name: string) {
  const idx = selectedContainers.value.indexOf(name)
  if (idx >= 0) {
    selectedContainers.value.splice(idx, 1)
  } else {
    selectedContainers.value.push(name)
  }
}

function isContainerSelected(name: string): boolean {
  return selectedContainers.value.includes(name)
}

const selectedContainerLabel = computed(() => {
  if (selectedContainers.value.length === 0) return 'All containers'
  if (selectedContainers.value.length === 1) return selectedContainers.value[0]
  return `${selectedContainers.value.length} containers`
})
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader
      title="Logs"
      description="Aggregated container log viewer"
    >
      <template #actions>
        <Button variant="outline" size="sm" @click="refetch()">
          <RefreshCw class="w-4 h-4" />
          Refresh
        </Button>
      </template>
    </PageHeader>

    <!-- Filter bar -->
    <div class="card p-3 mb-4">
      <div class="flex flex-wrap items-center gap-3">
        <!-- Container multi-select dropdown -->
        <div class="relative">
          <button
            class="h-9 px-3 text-sm rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-kPrimary dark:text-white hover:bg-gray-50 dark:hover:bg-neutral-800 transition-colors flex items-center gap-2 min-w-[180px]"
            @click="showContainerDropdown = !showContainerDropdown"
          >
            <Filter class="w-4 h-4 text-gray-400" />
            <span class="flex-1 text-left truncate">{{ selectedContainerLabel }}</span>
            <ChevronDown class="w-3.5 h-3.5 text-gray-400" />
          </button>
          <div
            v-if="showContainerDropdown"
            class="absolute z-20 top-full left-0 mt-1 w-64 max-h-60 overflow-y-auto rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 shadow-strong custom-scrollbar"
          >
            <div v-if="containerList.length === 0" class="px-3 py-2 text-sm text-gray-400">
              No containers available
            </div>
            <label
              v-for="name in containerList"
              :key="name"
              class="flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-neutral-800 cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                :checked="isContainerSelected(name)"
                class="rounded border-kPrimary/15 dark:border-neutral-700 text-accent focus:ring-accent/20"
                @change="toggleContainer(name)"
              />
              <span class="text-kPrimary dark:text-white truncate">{{ name }}</span>
            </label>
          </div>
          <!-- Click-away overlay -->
          <div
            v-if="showContainerDropdown"
            class="fixed inset-0 z-10"
            @click="showContainerDropdown = false"
          />
        </div>

        <!-- Search -->
        <div class="flex-1 min-w-[200px]">
          <Input
            v-model="searchQuery"
            placeholder="Search logs..."
            size="sm"
          >
            <template #left>
              <Search class="w-4 h-4" />
            </template>
          </Input>
        </div>

        <!-- Stream filter -->
        <select
          v-model="streamFilter"
          class="h-9 px-3 text-sm rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-kPrimary dark:text-white focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
        >
          <option value="all">All streams</option>
          <option value="stdout">stdout</option>
          <option value="stderr">stderr</option>
        </select>

        <!-- Tail count -->
        <select
          v-model.number="tailCount"
          class="h-9 px-3 text-sm rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-kPrimary dark:text-white focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
        >
          <option :value="100">100 lines</option>
          <option :value="200">200 lines</option>
          <option :value="500">500 lines</option>
          <option :value="1000">1000 lines</option>
        </select>
      </div>
    </div>

    <!-- Log viewer -->
    <div class="card overflow-hidden">
      <!-- Loading -->
      <div v-if="isLoading" class="bg-neutral-950 p-4 h-[500px] flex items-center justify-center">
        <div class="text-gray-500 text-sm">Loading logs...</div>
      </div>

      <!-- Error -->
      <div v-else-if="isError" class="bg-neutral-950 p-4 h-[500px] flex items-center justify-center">
        <div class="text-center">
          <p class="text-gray-500 text-sm mb-3">Failed to load logs.</p>
          <Button variant="outline" size="sm" @click="refetch()">Retry</Button>
        </div>
      </div>

      <!-- Logs -->
      <template v-else>
        <div
          ref="logViewerRef"
          class="bg-neutral-950 p-4 h-[500px] overflow-y-auto custom-scrollbar font-mono text-xs leading-relaxed"
        >
          <div v-if="logs && logs.entries.length > 0">
            <div
              v-for="(entry, index) in logs.entries"
              :key="index"
              :class="[
                'py-0.5',
                entry.stream === 'stderr' ? 'text-red-400' : 'text-gray-300',
              ]"
            >
              <span class="text-blue-400 mr-2 select-none">[{{ entry.container }}]</span>
              <span class="text-gray-600 mr-2 select-none">{{ entry.timestamp }}</span>
              <span>{{ entry.message }}</span>
            </div>
          </div>
          <div v-else class="h-full flex items-center justify-center">
            <div class="text-center">
              <ScrollText class="w-8 h-8 mx-auto text-gray-600 mb-2" />
              <p class="text-gray-500">No log entries found</p>
              <p class="text-gray-600 text-2xs mt-1">Adjust your filters or click Refresh</p>
            </div>
          </div>
        </div>

        <!-- Footer stats -->
        <div v-if="logs" class="px-4 py-2 border-t border-neutral-800 bg-neutral-950 flex items-center gap-4 text-2xs text-gray-500">
          <span>{{ logs.entries.length }} entries</span>
          <span>{{ logs.containers.length }} container{{ logs.containers.length !== 1 ? 's' : '' }}</span>
        </div>
      </template>
    </div>
  </div>
</template>
