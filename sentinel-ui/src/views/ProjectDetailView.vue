<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { projectsService } from '@/services/projects'
import { useToast } from 'vue-toastification'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Input from '@/components/ui/Input.vue'
import Modal from '@/components/ui/Modal.vue'
import {
  ArrowLeft, Save, Plus, Trash2, Copy, Check,
  Globe, Github, Container, Database, Key,
  ExternalLink, FolderGit2, RefreshCw,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const toast = useToast()
const projectId = route.params.id as string
const copied = ref('')
const showEnvModal = ref(false)
const envVars = ref<{ key: string; value: string }[]>([])
const savingEnv = ref(false)
const showEditModal = ref(false)

const editForm = ref({
  display_name: '',
  github_repo: '',
  domain: '',
  health_endpoint: '',
})

const { data: project, isLoading, isError } = useQuery({
  queryKey: ['project', projectId],
  queryFn: () => projectsService.get(projectId),
})

const { data: projectEnv } = useQuery({
  queryKey: ['project-env', projectId],
  queryFn: () => projectsService.getEnv(projectId),
})

const deleteMutation = useMutation({
  mutationFn: () => projectsService.remove(projectId),
  onSuccess: () => {
    toast.success('Project deleted')
    router.push('/projects')
  },
  onError: () => toast.error('Failed to delete project'),
})

function githubUrl(repo: string): string {
  if (!repo) return '#'
  return repo.startsWith('http') ? repo : `https://github.com/${repo}`
}

function githubDisplay(repo: string): string {
  if (!repo) return ''
  return repo.replace(/^https?:\/\/github\.com\//, '')
}

async function copy(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = label
    setTimeout(() => { copied.value = '' }, 2000)
  } catch {}
}

function openEnvModal() {
  envVars.value = (projectEnv.value || []).map((v: any) => ({
    key: v.key || '',
    value: v.value || '',
  }))
  showEnvModal.value = true
}

function addEnvVar() {
  envVars.value.push({ key: '', value: '' })
}

function removeEnvVar(index: number) {
  envVars.value.splice(index, 1)
}

async function saveEnvVars() {
  savingEnv.value = true
  try {
    const vars: Record<string, string> = {}
    for (const v of envVars.value) {
      if (v.key.trim()) vars[v.key.trim()] = v.value
    }
    await projectsService.updateEnv(projectId, vars)
    toast.success('Environment variables updated')
    showEnvModal.value = false
    queryClient.invalidateQueries({ queryKey: ['project-env', projectId] })
  } catch (e: any) {
    toast.error(e.response?.data?.detail || 'Failed to update env vars')
  } finally {
    savingEnv.value = false
  }
}

function openEditModal() {
  if (!project.value) return
  editForm.value = {
    display_name: project.value.display_name || '',
    github_repo: project.value.github_repo || '',
    domain: project.value.domain || '',
    health_endpoint: project.value.health_endpoint || '/health',
  }
  showEditModal.value = true
}

async function saveProject() {
  try {
    await projectsService.update(projectId, editForm.value as any)
    toast.success('Project updated')
    showEditModal.value = false
    queryClient.invalidateQueries({ queryKey: ['project', projectId] })
  } catch (e: any) {
    toast.error(e.response?.data?.detail || 'Failed to update project')
  }
}

function confirmDelete() {
  if (window.confirm(`Delete project "${project.value?.display_name || project.value?.name}"? This removes the record from Sentinel but does NOT delete server files or containers.`)) {
    deleteMutation.mutate()
  }
}
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader :title="project?.display_name || project?.name || 'Project'" :description="project?.name || ''">
      <template #actions>
        <Button variant="outline" size="sm" @click="router.push('/projects')">
          <ArrowLeft class="w-4 h-4" /> Back
        </Button>
        <Button variant="outline" size="sm" @click="openEditModal">Edit</Button>
        <Button variant="outline" size="sm" @click="openEnvModal">
          <Key class="w-4 h-4" /> Env Vars
        </Button>
      </template>
    </PageHeader>

    <!-- Loading -->
    <div v-if="isLoading" class="space-y-4">
      <div class="card p-5"><div class="skeleton h-6 w-48 mb-3" /><div class="skeleton h-4 w-64" /></div>
    </div>

    <!-- Error -->
    <div v-else-if="isError" class="card p-8 text-center">
      <p class="text-text-secondary">Failed to load project.</p>
      <Button variant="outline" size="sm" class="mt-3" @click="router.push('/projects')">Back to Projects</Button>
    </div>

    <!-- Content -->
    <div v-else-if="project" class="space-y-4">
      <!-- Info card -->
      <div class="card p-5">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <span class="text-xs text-text-tertiary">Status</span>
            <div class="mt-1"><Badge :variant="project.status === 'active' ? 'success' : 'neutral'" size="sm">{{ project.status }}</Badge></div>
          </div>
          <div>
            <span class="text-xs text-text-tertiary">Type</span>
            <p class="text-sm font-medium text-text mt-1">{{ project.project_type || project.type || 'custom' }}</p>
          </div>
          <div>
            <span class="text-xs text-text-tertiary">Health Endpoint</span>
            <p class="text-sm font-mono text-text mt-1">{{ project.health_endpoint || '/health' }}</p>
          </div>
          <div v-if="project.domain">
            <span class="text-xs text-text-tertiary">Domain</span>
            <div class="flex items-center gap-1.5 mt-1">
              <Globe class="w-3.5 h-3.5 text-text-secondary" />
              <a :href="`https://${project.domain}`" target="_blank" class="text-sm text-accent hover:underline">
                {{ project.domain }} <ExternalLink class="w-3 h-3 inline" />
              </a>
            </div>
          </div>
          <div v-if="project.github_repo">
            <span class="text-xs text-text-tertiary">Repository</span>
            <div class="flex items-center gap-1.5 mt-1">
              <Github class="w-3.5 h-3.5 text-text-secondary" />
              <a :href="githubUrl(project.github_repo)" target="_blank" class="text-sm text-accent hover:underline">
                {{ githubDisplay(project.github_repo) }} <ExternalLink class="w-3 h-3 inline" />
              </a>
            </div>
          </div>
          <div v-if="project.database_name">
            <span class="text-xs text-text-tertiary">Database</span>
            <div class="flex items-center gap-1.5 mt-1">
              <Database class="w-3.5 h-3.5 text-text-secondary" />
              <span class="text-sm text-text">{{ project.database_name }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Webhook secret -->
      <div v-if="project.webhook_secret" class="card p-5">
        <h3 class="text-sm font-heading font-semibold text-text mb-2">Webhook Secret</h3>
        <div class="flex items-center gap-2">
          <code class="flex-1 px-3 py-2 text-xs font-mono bg-surface-tertiary rounded-lg text-text break-all">{{ project.webhook_secret }}</code>
          <button class="p-2 rounded-lg text-text-tertiary hover:text-accent transition-colors shrink-0" @click="copy(project.webhook_secret, 'secret')">
            <component :is="copied === 'secret' ? Check : Copy" class="w-4 h-4" />
          </button>
        </div>
      </div>

      <!-- Containers -->
      <div v-if="project.container_names" class="card p-5">
        <h3 class="text-sm font-heading font-semibold text-text mb-3">Containers</h3>
        <div class="flex flex-wrap gap-2">
          <router-link
            v-for="(_, name) in project.container_names"
            :key="name"
            :to="`/services/${name}`"
            class="flex items-center gap-1.5 px-3 py-1.5 bg-surface-tertiary rounded-lg text-sm text-text hover:text-accent transition-colors"
          >
            <Container class="w-3.5 h-3.5" /> {{ name }}
          </router-link>
        </div>
      </div>

      <!-- Env vars (read-only display) -->
      <div v-if="projectEnv && projectEnv.length > 0" class="card p-5">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-heading font-semibold text-text">Environment Variables</h3>
          <Button variant="outline" size="xs" @click="openEnvModal">Edit</Button>
        </div>
        <div class="space-y-1">
          <div v-for="v in projectEnv" :key="v.key" class="flex items-center gap-2 text-xs font-mono">
            <span class="text-accent">{{ v.key }}</span>
            <span class="text-text-tertiary">=</span>
            <span class="text-text-secondary">{{ v.value || '••••••' }}</span>
          </div>
        </div>
      </div>

      <!-- Danger zone -->
      <div class="card p-5 border-red-200 dark:border-red-900/30">
        <h3 class="text-sm font-heading font-semibold text-red-500 mb-2">Danger Zone</h3>
        <p class="text-xs text-text-secondary mb-3">Delete this project from Sentinel. Server files and containers are NOT removed.</p>
        <Button variant="outline" size="sm" class="text-red-500 border-red-200 hover:bg-red-50 dark:border-red-900/30 dark:hover:bg-red-950/30" @click="confirmDelete">
          <Trash2 class="w-4 h-4" /> Delete Project
        </Button>
      </div>
    </div>

    <!-- Edit Modal -->
    <Modal v-model="showEditModal" title="Edit Project" size="lg">
      <div class="space-y-4">
        <Input v-model="editForm.display_name" label="Display Name" />
        <Input v-model="editForm.github_repo" label="GitHub Repository" />
        <Input v-model="editForm.domain" label="Domain" />
        <Input v-model="editForm.health_endpoint" label="Health Endpoint" />
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <Button variant="outline" size="sm" @click="showEditModal = false">Cancel</Button>
          <Button variant="accent" size="sm" @click="saveProject"><Save class="w-4 h-4" /> Save</Button>
        </div>
      </template>
    </Modal>

    <!-- Env Vars Modal -->
    <Modal v-model="showEnvModal" title="Environment Variables" size="lg">
      <div class="space-y-3 max-h-96 overflow-y-auto">
        <div v-for="(v, i) in envVars" :key="i" class="flex items-center gap-2">
          <input v-model="v.key" type="text" placeholder="KEY"
            class="w-40 h-9 px-3 text-xs font-mono rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20" />
          <input v-model="v.value" type="text" placeholder="value"
            class="flex-1 h-9 px-3 text-xs font-mono rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20" />
          <button class="p-1.5 rounded-md text-text-tertiary hover:text-red-500 transition-colors" @click="removeEnvVar(i)">
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
        <Button variant="outline" size="xs" @click="addEnvVar"><Plus class="w-3.5 h-3.5" /> Add</Button>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <Button variant="outline" size="sm" @click="showEnvModal = false">Cancel</Button>
          <Button variant="accent" size="sm" :loading="savingEnv" @click="saveEnvVars"><Save class="w-4 h-4" /> Save</Button>
        </div>
      </template>
    </Modal>
  </div>
</template>
