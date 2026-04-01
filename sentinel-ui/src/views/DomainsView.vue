<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { domainsService } from '@/services/domains'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Input from '@/components/ui/Input.vue'
import Modal from '@/components/ui/Modal.vue'
import { useToast } from 'vue-toastification'
import {
  Globe,
  Plus,
  RefreshCw,
  Pencil,
  Trash2,
  Lock,
  LockOpen,
  Server,
} from 'lucide-vue-next'

const queryClient = useQueryClient()
const toast = useToast()

const showAddModal = ref(false)
const showEditModal = ref(false)

const newDomain = reactive({
  domain: '',
  tls_mode: 'auto' as 'auto' | 'cloudflare_dns' | 'off',
  targets: [{ path_prefix: '/', upstream: '' }] as { path_prefix: string; upstream: string }[],
})

const editDomain = reactive({
  domain: '',
  tls_mode: 'auto' as 'auto' | 'cloudflare_dns' | 'off',
  targets: [{ path_prefix: '/', upstream: '' }] as { path_prefix: string; upstream: string }[],
})

const { data: domains, isLoading, isError, refetch } = useQuery({
  queryKey: ['domains'],
  queryFn: () => domainsService.list(),
})

const createMutation = useMutation({
  mutationFn: () => {
    const upstreams = newDomain.targets
      .filter((t) => t.upstream.trim())
      .map((t) => {
        const parts = t.upstream.split(':')
        return {
          address: parts[0],
          port: parseInt(parts[1] || '80', 10),
        }
      })
    return domainsService.create({
      domain: newDomain.domain,
      upstreams,
      tls_mode: newDomain.tls_mode,
    })
  },
  onSuccess: () => {
    toast.success(`Domain "${newDomain.domain}" created`)
    showAddModal.value = false
    resetNewDomain()
    queryClient.invalidateQueries({ queryKey: ['domains'] })
  },
  onError: (e: any) => {
    toast.error(e.response?.data?.detail || 'Failed to create domain')
  },
})

const updateMutation = useMutation({
  mutationFn: () => {
    const upstreams = editDomain.targets
      .filter((t) => t.upstream.trim())
      .map((t) => {
        const parts = t.upstream.split(':')
        return {
          address: parts[0],
          port: parseInt(parts[1] || '80', 10),
        }
      })
    return domainsService.update(editDomain.domain, {
      upstreams,
      tls_mode: editDomain.tls_mode,
    })
  },
  onSuccess: () => {
    toast.success(`Domain "${editDomain.domain}" updated`)
    showEditModal.value = false
    queryClient.invalidateQueries({ queryKey: ['domains'] })
  },
  onError: (e: any) => {
    toast.error(e.response?.data?.detail || 'Failed to update domain')
  },
})

const deleteMutation = useMutation({
  mutationFn: (domain: string) => domainsService.remove(domain),
  onSuccess: (_data, domain) => {
    toast.success(`Domain "${domain}" deleted`)
    queryClient.invalidateQueries({ queryKey: ['domains'] })
  },
  onError: () => {
    toast.error('Failed to delete domain')
  },
})

const reloadMutation = useMutation({
  mutationFn: () => domainsService.reload(),
  onSuccess: (data) => {
    toast.success(data.message)
  },
  onError: () => {
    toast.error('Failed to reload Caddy')
  },
})

function resetNewDomain() {
  newDomain.domain = ''
  newDomain.tls_mode = 'auto'
  newDomain.targets = [{ path_prefix: '/', upstream: '' }]
}

function openAddModal() {
  resetNewDomain()
  showAddModal.value = true
}

function openEditModal(domainInfo: any) {
  editDomain.domain = domainInfo.domain
  editDomain.tls_mode = domainInfo.tls_mode || 'auto'
  editDomain.targets = (domainInfo.upstreams || []).map((u: any) => ({
    path_prefix: '/',
    upstream: `${u.address}:${u.port}`,
  }))
  if (editDomain.targets.length === 0) {
    editDomain.targets = [{ path_prefix: '/', upstream: '' }]
  }
  showEditModal.value = true
}

function addTarget(targets: { path_prefix: string; upstream: string }[]) {
  targets.push({ path_prefix: '/', upstream: '' })
}

function removeTarget(targets: { path_prefix: string; upstream: string }[], index: number) {
  if (targets.length > 1) {
    targets.splice(index, 1)
  }
}

function confirmDelete(domain: string) {
  if (window.confirm(`Are you sure you want to delete "${domain}"? This cannot be undone.`)) {
    deleteMutation.mutate(domain)
  }
}
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader
      title="Domains"
      description="Caddy reverse proxy domain management"
    >
      <template #actions>
        <Button
          variant="outline"
          size="sm"
          :loading="reloadMutation.isPending.value"
          @click="reloadMutation.mutate()"
        >
          <RefreshCw class="w-4 h-4" />
          Reload Caddy
        </Button>
        <Button variant="accent" size="sm" @click="openAddModal">
          <Plus class="w-4 h-4" />
          Add Domain
        </Button>
      </template>
    </PageHeader>

    <!-- Loading skeleton -->
    <div v-if="isLoading" class="card">
      <div v-for="i in 4" :key="i" class="flex items-center gap-4 p-4 border-b border-kPrimary/5 dark:border-neutral-800 last:border-0">
        <div class="skeleton h-9 w-9 rounded-lg" />
        <div class="flex-1">
          <div class="skeleton h-4 w-48 mb-2" />
          <div class="skeleton h-3 w-32" />
        </div>
        <div class="skeleton h-6 w-16 rounded-full" />
      </div>
    </div>

    <!-- Error state -->
    <div v-else-if="isError" class="card p-8 text-center">
      <p class="text-text-secondary">Failed to load domains.</p>
      <Button variant="outline" size="sm" class="mt-3" @click="refetch()">Retry</Button>
    </div>

    <!-- Domains table -->
    <div v-else class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-border">
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Domain</th>
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Upstreams</th>
              <th class="text-left text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">TLS</th>
              <th class="text-right text-xs font-semibold text-text-secondary uppercase tracking-wide px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="domain in domains"
              :key="domain.domain"
              class="border-b border-border last:border-0 hover:bg-surface-secondary transition-colors"
            >
              <td class="px-4 py-3">
                <div class="flex items-center gap-2.5">
                  <div class="w-8 h-8 rounded-lg bg-surface-tertiary flex items-center justify-center shrink-0">
                    <Globe class="w-4 h-4 text-text-secondary" />
                  </div>
                  <span class="text-sm font-semibold font-heading text-text">
                    {{ domain.domain }}
                  </span>
                </div>
              </td>
              <td class="px-4 py-3">
                <div class="flex flex-wrap gap-1.5">
                  <Badge
                    v-for="(upstream, idx) in domain.upstreams"
                    :key="idx"
                    variant="info"
                    size="sm"
                  >
                    {{ upstream.address }}:{{ upstream.port }}
                  </Badge>
                  <span v-if="domain.upstreams.length === 0" class="text-sm text-gray-400">-</span>
                </div>
              </td>
              <td class="px-4 py-3">
                <Badge :variant="domain.tls_mode === 'off' ? 'neutral' : domain.tls_mode === 'cloudflare_dns' ? 'info' : 'success'" size="sm">
                  <component :is="domain.tls_mode === 'off' ? LockOpen : Lock" class="w-3 h-3 mr-0.5" />
                  {{ domain.tls_mode === 'cloudflare_dns' ? 'Cloudflare DNS' : domain.tls_mode === 'off' ? 'Off' : 'Auto ACME' }}
                </Badge>
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center justify-end gap-1">
                  <button
                    class="p-1.5 rounded-md text-gray-400 hover:text-accent hover:bg-accent/10 transition-colors"
                    title="Edit"
                    @click="openEditModal(domain)"
                  >
                    <Pencil class="w-4 h-4" />
                  </button>
                  <button
                    class="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                    title="Delete"
                    :disabled="deleteMutation.isPending.value"
                    @click="confirmDelete(domain.domain)"
                  >
                    <Trash2 class="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Empty state -->
      <div v-if="domains && domains.length === 0" class="p-12 text-center">
        <div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-surface-tertiary flex items-center justify-center">
          <Globe class="w-7 h-7 text-gray-400" />
        </div>
        <h3 class="text-lg font-heading font-semibold text-text mb-2">No domains configured</h3>
        <p class="text-sm text-text-secondary max-w-md mx-auto mb-4">
          Add your first domain to start routing traffic.
        </p>
        <Button variant="accent" size="sm" @click="openAddModal">
          <Plus class="w-4 h-4" />
          Add Domain
        </Button>
      </div>
    </div>

    <!-- Add Domain Modal -->
    <Modal v-model="showAddModal" title="Add Domain" size="lg">
      <div class="space-y-4">
        <Input
          v-model="newDomain.domain"
          label="Domain"
          placeholder="app.example.com"
        />
        <div>
          <label class="block text-sm font-medium text-text mb-1.5">TLS Mode</label>
          <select
            v-model="newDomain.tls_mode"
            class="w-full h-10 px-3 text-sm rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
          >
            <option value="auto">Auto ACME (Let's Encrypt)</option>
            <option value="cloudflare_dns">Cloudflare DNS Challenge (wildcards)</option>
            <option value="off">Off (HTTP only)</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-kPrimary dark:text-gray-300 mb-1.5">Proxy Targets</label>
          <div class="space-y-2">
            <div
              v-for="(target, index) in newDomain.targets"
              :key="index"
              class="flex items-center gap-2"
            >
              <input
                v-model="target.path_prefix"
                type="text"
                placeholder="/"
                class="w-20 h-9 px-3 text-sm rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors placeholder:text-gray-400"
              />
              <input
                v-model="target.upstream"
                type="text"
                placeholder="container:8000"
                class="flex-1 h-9 px-3 text-sm rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors placeholder:text-gray-400"
              />
              <button
                v-if="newDomain.targets.length > 1"
                class="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                @click="removeTarget(newDomain.targets, index)"
              >
                <Trash2 class="w-4 h-4" />
              </button>
            </div>
          </div>
          <Button variant="ghost" size="xs" class="mt-2" @click="addTarget(newDomain.targets)">
            <Plus class="w-3.5 h-3.5" />
            Add Target
          </Button>
        </div>
      </div>
      <template #footer>
        <div class="flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" @click="showAddModal = false">Cancel</Button>
          <Button
            variant="accent"
            size="sm"
            :disabled="!newDomain.domain.trim()"
            :loading="createMutation.isPending.value"
            @click="createMutation.mutate()"
          >
            <Plus class="w-4 h-4" />
            Create
          </Button>
        </div>
      </template>
    </Modal>

    <!-- Edit Domain Modal -->
    <Modal v-model="showEditModal" title="Edit Domain" size="lg">
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-kPrimary dark:text-gray-300 mb-1.5">Domain</label>
          <p class="text-sm font-mono text-text">{{ editDomain.domain }}</p>
        </div>
        <div>
          <label class="block text-sm font-medium text-text mb-1.5">TLS Mode</label>
          <select
            v-model="editDomain.tls_mode"
            class="w-full h-10 px-3 text-sm rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
          >
            <option value="auto">Auto ACME (Let's Encrypt)</option>
            <option value="cloudflare_dns">Cloudflare DNS Challenge (wildcards)</option>
            <option value="off">Off (HTTP only)</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-kPrimary dark:text-gray-300 mb-1.5">Proxy Targets</label>
          <div class="space-y-2">
            <div
              v-for="(target, index) in editDomain.targets"
              :key="index"
              class="flex items-center gap-2"
            >
              <input
                v-model="target.path_prefix"
                type="text"
                placeholder="/"
                class="w-20 h-9 px-3 text-sm rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors placeholder:text-gray-400"
              />
              <input
                v-model="target.upstream"
                type="text"
                placeholder="container:8000"
                class="flex-1 h-9 px-3 text-sm rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors placeholder:text-gray-400"
              />
              <button
                v-if="editDomain.targets.length > 1"
                class="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                @click="removeTarget(editDomain.targets, index)"
              >
                <Trash2 class="w-4 h-4" />
              </button>
            </div>
          </div>
          <Button variant="ghost" size="xs" class="mt-2" @click="addTarget(editDomain.targets)">
            <Plus class="w-3.5 h-3.5" />
            Add Target
          </Button>
        </div>
      </div>
      <template #footer>
        <div class="flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" @click="showEditModal = false">Cancel</Button>
          <Button
            variant="accent"
            size="sm"
            :loading="updateMutation.isPending.value"
            @click="updateMutation.mutate()"
          >
            Save Changes
          </Button>
        </div>
      </template>
    </Modal>
  </div>
</template>
