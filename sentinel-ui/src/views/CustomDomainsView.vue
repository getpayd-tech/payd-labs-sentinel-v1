<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { customDomainsService } from '@/services/customDomains'
import { projectsService } from '@/services/projects'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import { useToast } from 'vue-toastification'
import { relativeTime } from '@/utils/formatters'
import {
  Globe,
  RefreshCw,
  Trash2,
  Filter,
  ExternalLink,
} from 'lucide-vue-next'

const queryClient = useQueryClient()
const toast = useToast()
const selectedProject = ref('')

const { data: domainData, isLoading, isError, refetch } = useQuery({
  queryKey: ['custom-domains', selectedProject],
  queryFn: () => customDomainsService.listAll(selectedProject.value || undefined),
  refetchInterval: 15000,
})

const { data: projects } = useQuery({
  queryKey: ['projects-list'],
  queryFn: () => projectsService.list(),
})

const items = computed(() => domainData.value?.items ?? [])

const deleteMutation = useMutation({
  mutationFn: (domain: string) => customDomainsService.adminRemove(domain),
  onSuccess: (_data, domain) => {
    toast.success(`Domain '${domain}' removed`)
    queryClient.invalidateQueries({ queryKey: ['custom-domains'] })
  },
  onError: () => toast.error('Failed to remove domain'),
})

function getStatusVariant(status: string): 'success' | 'warning' | 'error' | 'neutral' {
  const map: Record<string, 'success' | 'warning' | 'error' | 'neutral'> = {
    active: 'success',
    pending: 'neutral',
    failed: 'error',
    removing: 'warning',
  }
  return map[status] || 'neutral'
}

function confirmDelete(domain: string) {
  if (window.confirm(`Remove custom domain "${domain}"? This will delete the Caddy route and TLS cert.`)) {
    deleteMutation.mutate(domain)
  }
}
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader
      title="Custom Domains"
      description="Dynamic domains registered by services for on-demand TLS"
    >
      <template #actions>
        <Button variant="outline" size="sm" @click="refetch()">
          <RefreshCw class="w-4 h-4" />
          Refresh
        </Button>
      </template>
    </PageHeader>

    <!-- Filter -->
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
        <option v-for="p in projects" :key="p.id" :value="p.id">
          {{ p.display_name || p.name }}
        </option>
      </select>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="card">
      <div v-for="i in 5" :key="i" class="flex items-center gap-4 p-4 border-b border-border last:border-0">
        <div class="skeleton h-9 w-9 rounded-lg" />
        <div class="flex-1">
          <div class="skeleton h-4 w-48 mb-2" />
          <div class="skeleton h-3 w-32" />
        </div>
        <div class="skeleton h-6 w-16 rounded-full" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="isError" class="card p-8 text-center">
      <p class="text-text-secondary">Failed to load custom domains.</p>
      <Button variant="outline" size="sm" class="mt-3" @click="refetch()">Retry</Button>
    </div>

    <!-- Table -->
    <div v-else class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-border">
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Domain</th>
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3 hidden md:table-cell">Project</th>
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Status</th>
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3 hidden lg:table-cell">Created</th>
              <th class="text-right text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="cd in items"
              :key="cd.id"
              class="border-b border-border last:border-0 hover:bg-surface-secondary transition-colors"
            >
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <Globe class="w-4 h-4 text-text-secondary shrink-0" />
                  <a :href="`https://${cd.domain}`" target="_blank" class="text-sm font-semibold text-accent hover:underline">
                    {{ cd.domain }}
                    <ExternalLink class="w-3 h-3 inline" />
                  </a>
                </div>
                <p v-if="cd.error_message" class="text-xs text-red-500 mt-1 ml-6">{{ cd.error_message }}</p>
              </td>
              <td class="px-4 py-3 hidden md:table-cell">
                <span class="text-sm text-text">{{ cd.project_name }}</span>
              </td>
              <td class="px-4 py-3">
                <Badge :variant="getStatusVariant(cd.status)" size="sm">{{ cd.status }}</Badge>
              </td>
              <td class="px-4 py-3 hidden lg:table-cell">
                <span class="text-sm text-text-secondary">{{ cd.created_at ? relativeTime(cd.created_at) : '-' }}</span>
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center justify-end">
                  <button
                    class="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                    title="Remove domain"
                    @click="confirmDelete(cd.domain)"
                  >
                    <Trash2 class="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Empty -->
      <div v-if="items.length === 0" class="p-12 text-center">
        <div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-surface-tertiary flex items-center justify-center">
          <Globe class="w-7 h-7 text-gray-400" />
        </div>
        <h3 class="text-lg font-heading font-semibold text-text mb-2">No custom domains</h3>
        <p class="text-sm text-text-secondary max-w-md mx-auto">
          Services register custom domains via the API. Enable custom domains on a project and configure its upstream to get started.
        </p>
      </div>
    </div>
  </div>
</template>
