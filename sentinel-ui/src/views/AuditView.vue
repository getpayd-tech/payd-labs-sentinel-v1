<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { auditService } from '@/services/audit'
import { formatDate } from '@/utils/formatters'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Input from '@/components/ui/Input.vue'
import {
  ClipboardList,
  RefreshCw,
  Filter,
  ChevronLeft,
  ChevronRight,
  User,
  Clock,
  Globe,
} from 'lucide-vue-next'

const actionFilter = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const page = ref(1)
const perPage = ref(25)
const expandedRow = ref<string | null>(null)

// Applied filters (only update when Filter button is clicked)
const appliedFilters = ref({
  action: '',
  dateFrom: '',
  dateTo: '',
})

function applyFilters() {
  appliedFilters.value = {
    action: actionFilter.value,
    dateFrom: dateFrom.value,
    dateTo: dateTo.value,
  }
  page.value = 1
}

const { data: auditData, isLoading, isError, refetch } = useQuery({
  queryKey: ['audit-logs', appliedFilters, page, perPage],
  queryFn: () =>
    auditService.list({
      action: appliedFilters.value.action || undefined,
      date_from: appliedFilters.value.dateFrom || undefined,
      date_to: appliedFilters.value.dateTo || undefined,
      page: page.value,
      per_page: perPage.value,
    }),
})

const items = computed(() => auditData.value?.items ?? [])
const total = computed(() => auditData.value?.total ?? 0)
const totalPages = computed(() => Math.ceil(total.value / perPage.value) || 1)

function toggleDetails(id: string) {
  expandedRow.value = expandedRow.value === id ? null : id
}

function getActionVariant(action: string): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (action.includes('create') || action.includes('provision')) return 'success'
  if (action.includes('delete') || action.includes('remove')) return 'error'
  if (action.includes('update') || action.includes('restart') || action.includes('deploy')) return 'warning'
  if (action.includes('login') || action.includes('auth')) return 'info'
  return 'neutral'
}

function prevPage() {
  if (page.value > 1) page.value--
}

function nextPage() {
  if (page.value < totalPages.value) page.value++
}

function truncateDetails(text: string | null, length = 60): string {
  if (!text) return '-'
  if (text.length <= length) return text
  return text.slice(0, length) + '...'
}
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader
      title="Audit Log"
      description="Activity trail and security events"
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
      <div class="flex flex-wrap items-end gap-3">
        <div class="min-w-[180px]">
          <Input
            v-model="actionFilter"
            label="Action"
            placeholder="e.g. deploy, login"
            size="sm"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-kPrimary dark:text-gray-300 mb-1.5">From</label>
          <input
            v-model="dateFrom"
            type="date"
            class="h-8 px-3 text-sm rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-kPrimary dark:text-white focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-kPrimary dark:text-gray-300 mb-1.5">To</label>
          <input
            v-model="dateTo"
            type="date"
            class="h-8 px-3 text-sm rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-kPrimary dark:text-white focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
          />
        </div>
        <Button variant="accent" size="sm" @click="applyFilters">
          <Filter class="w-4 h-4" />
          Filter
        </Button>
      </div>
    </div>

    <!-- Loading skeleton -->
    <div v-if="isLoading" class="card">
      <div v-for="i in 8" :key="i" class="flex items-center gap-4 p-4 border-b border-kPrimary/5 dark:border-neutral-800 last:border-0">
        <div class="skeleton h-4 w-36" />
        <div class="skeleton h-4 w-20" />
        <div class="skeleton h-5 w-16 rounded-full" />
        <div class="flex-1">
          <div class="skeleton h-4 w-40" />
        </div>
        <div class="skeleton h-4 w-24" />
      </div>
    </div>

    <!-- Error state -->
    <div v-else-if="isError" class="card p-8 text-center">
      <p class="text-gray-500 dark:text-gray-400">Failed to load audit logs.</p>
      <Button variant="outline" size="sm" class="mt-3" @click="refetch()">Retry</Button>
    </div>

    <!-- Audit table -->
    <div v-else class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-kPrimary/10 dark:border-neutral-800">
              <th class="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-4 py-3">Timestamp</th>
              <th class="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-4 py-3">User</th>
              <th class="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-4 py-3">Action</th>
              <th class="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-4 py-3">Target</th>
              <th class="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-4 py-3 hidden lg:table-cell">Details</th>
              <th class="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide px-4 py-3 hidden md:table-cell">IP Address</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="entry in items" :key="entry.id">
              <tr
                class="border-b border-kPrimary/5 dark:border-neutral-800/50 last:border-0 hover:bg-gray-50 dark:hover:bg-neutral-800/30 transition-colors"
                :class="{ 'cursor-pointer': entry.details }"
                @click="entry.details ? toggleDetails(entry.id) : null"
              >
                <td class="px-4 py-3">
                  <div class="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">
                    <Clock class="w-3.5 h-3.5 shrink-0" />
                    {{ formatDate(entry.timestamp) }}
                  </div>
                </td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-1.5 text-sm">
                    <User class="w-3.5 h-3.5 text-gray-400 shrink-0" />
                    <span class="text-kPrimary dark:text-white font-medium">{{ entry.user || 'system' }}</span>
                  </div>
                </td>
                <td class="px-4 py-3">
                  <Badge :variant="getActionVariant(entry.action)" size="sm">
                    {{ entry.action }}
                  </Badge>
                </td>
                <td class="px-4 py-3">
                  <span class="text-sm text-kPrimary dark:text-white">{{ entry.target }}</span>
                </td>
                <td class="px-4 py-3 hidden lg:table-cell">
                  <span class="text-sm text-gray-500 dark:text-gray-400">
                    {{ truncateDetails(entry.details) }}
                  </span>
                </td>
                <td class="px-4 py-3 hidden md:table-cell">
                  <div v-if="entry.ip_address" class="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
                    <Globe class="w-3.5 h-3.5 shrink-0" />
                    <span class="font-mono text-xs">{{ entry.ip_address }}</span>
                  </div>
                  <span v-else class="text-sm text-gray-400">-</span>
                </td>
              </tr>
              <!-- Expanded details row -->
              <tr v-if="expandedRow === entry.id && entry.details">
                <td colspan="6" class="px-4 py-3 bg-gray-50 dark:bg-neutral-800/50">
                  <div class="text-sm font-mono text-kPrimary dark:text-gray-300 whitespace-pre-wrap break-all">
                    {{ entry.details }}
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Empty state -->
      <div v-if="items.length === 0" class="p-12 text-center">
        <div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-kPrimary/5 dark:bg-neutral-800 flex items-center justify-center">
          <ClipboardList class="w-7 h-7 text-gray-400" />
        </div>
        <h3 class="text-lg font-heading font-semibold text-kPrimary dark:text-white mb-2">No audit entries</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
          No audit log entries match your current filters.
        </p>
      </div>

      <!-- Pagination -->
      <div v-if="items.length > 0" class="px-4 py-3 border-t border-kPrimary/10 dark:border-neutral-800 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="text-sm text-gray-500 dark:text-gray-400">
            Page {{ page }} of {{ totalPages }}
          </span>
          <span class="text-2xs text-gray-400">
            ({{ total }} total)
          </span>
        </div>
        <div class="flex items-center gap-2">
          <select
            v-model.number="perPage"
            class="h-8 px-2 text-xs rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-kPrimary dark:text-white focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
            @change="page = 1"
          >
            <option :value="10">10 / page</option>
            <option :value="25">25 / page</option>
            <option :value="50">50 / page</option>
            <option :value="100">100 / page</option>
          </select>
          <Button variant="outline" size="xs" :disabled="page <= 1" @click="prevPage">
            <ChevronLeft class="w-4 h-4" />
          </Button>
          <Button variant="outline" size="xs" :disabled="page >= totalPages" @click="nextPage">
            <ChevronRight class="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
