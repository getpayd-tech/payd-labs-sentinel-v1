<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { wizardService, type TypeDefaults, type WizardResponse } from '@/services/wizard'
import { useToast } from 'vue-toastification'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import Badge from '@/components/ui/Badge.vue'
import {
  Zap, Globe, Database, Key, Eye, Rocket,
  ArrowLeft, ArrowRight, Check, X, Loader2,
  Plus, Trash2, Copy, CheckCircle2, XCircle, Clock,
  FileText, Info,
} from 'lucide-vue-next'

const router = useRouter()
const toast = useToast()

const currentStep = ref(1)
const totalSteps = 6
const loading = ref(false)
const deploying = ref(false)
const result = ref<WizardResponse | null>(null)
const defaults = ref<TypeDefaults | null>(null)
const previewData = ref<{ compose: string; caddyfile: string; workflow: string } | null>(null)
const previewTab = ref<'compose' | 'caddyfile' | 'workflow'>('compose')
const copied = ref('')
const bulkPasteMode = ref(false)
const bulkPasteText = ref('')

const PROJECT_TYPES = [
  { id: 'fastapi', label: 'FastAPI', icon: '🐍', desc: 'Python API with health checks' },
  { id: 'vue', label: 'Vue / Vite', icon: '💚', desc: 'SPA served by Caddy' },
  { id: 'blended', label: 'Blended', icon: '🔗', desc: 'FastAPI API + Vue frontend' },
  { id: 'nuxt', label: 'Nuxt', icon: '💎', desc: 'Nuxt 3 SSR application' },
  { id: 'laravel', label: 'Laravel', icon: '🔴', desc: 'Laravel PHP application' },
]

const form = reactive({
  project_type: '',
  github_repo: '',
  name: '',
  display_name: '',
  domain: '',
  tls_mode: 'auto' as 'auto' | 'cloudflare_dns' | 'off',
  create_database: false,
  database_name: '',
  health_endpoint: '/health',
  env_vars: [] as { key: string; value: string }[],
  compose_filename: 'docker-compose.yml',
  use_custom_routes: false,
  caddy_routes: [] as { path: string; upstream: string }[],
  first_deploy: true,
})

const SERVER_IP = '46.101.240.141'

// Auto-derive project name from repo
watch(() => form.github_repo, (repo) => {
  if (repo && !form.name) {
    const parts = repo.split('/')
    const repoName = parts[parts.length - 1] || ''
    form.name = repoName.toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/-+/g, '-')
    form.display_name = repoName.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  }
})

// Load type defaults when type changes
watch(() => form.project_type, async (type) => {
  if (type) {
    try {
      defaults.value = await wizardService.getDefaults(type)
      form.health_endpoint = defaults.value.health_endpoint || '/health'
      if (defaults.value.suggested_env.length > 0 && form.env_vars.length === 0) {
        form.env_vars = defaults.value.suggested_env.map(key => ({ key, value: '' }))
      }
    } catch { /* ignore */ }
  }
})

// Auto-populate default caddy routes when switching to custom mode
watch(() => form.use_custom_routes, (custom) => {
  if (custom && form.caddy_routes.length === 0 && form.name) {
    populateDefaultRoutes()
  }
})

function populateDefaultRoutes() {
  const name = form.name
  if (form.project_type === 'blended') {
    form.caddy_routes = [
      { path: '/api/*', upstream: `${name}-api:8000` },
      { path: '/*', upstream: `${name}-ui:80` },
    ]
  } else if (form.project_type === 'vue') {
    form.caddy_routes = [{ path: '/*', upstream: `${name}:80` }]
  } else if (form.project_type === 'nuxt') {
    form.caddy_routes = [{ path: '/*', upstream: `${name}:3000` }]
  } else {
    form.caddy_routes = [{ path: '/*', upstream: `${name}:8000` }]
  }
}

const canProceed = computed(() => {
  switch (currentStep.value) {
    case 1: return !!form.project_type
    case 2: return !!form.github_repo && !!form.name
    case 3: return !!form.domain
    case 4: return true
    case 5: return true
    case 6: return true
    default: return false
  }
})

function nextStep() {
  if (currentStep.value < totalSteps && canProceed.value) {
    currentStep.value++
    if (currentStep.value === 6) loadPreview()
  }
}

function prevStep() {
  if (currentStep.value > 1) {
    currentStep.value--
    result.value = null
  }
}

function addEnvVar() { form.env_vars.push({ key: '', value: '' }) }
function removeEnvVar(index: number) { form.env_vars.splice(index, 1) }
function addRoute() { form.caddy_routes.push({ path: '/', upstream: '' }) }
function removeRoute(index: number) { form.caddy_routes.splice(index, 1) }

function parseBulkPaste() {
  const lines = bulkPasteText.value.split('\n')
  const vars: { key: string; value: string }[] = []
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue
    const eqIdx = trimmed.indexOf('=')
    if (eqIdx > 0) {
      vars.push({ key: trimmed.slice(0, eqIdx).trim(), value: trimmed.slice(eqIdx + 1).trim() })
    }
  }
  if (vars.length > 0) {
    form.env_vars = vars
    bulkPasteMode.value = false
    bulkPasteText.value = ''
    toast.success(`Parsed ${vars.length} environment variables`)
  } else {
    toast.warning('No valid KEY=VALUE pairs found')
  }
}

async function loadPreview() {
  loading.value = true
  try {
    const routes = form.use_custom_routes ? form.caddy_routes : undefined
    previewData.value = await wizardService.preview({
      name: form.name,
      display_name: form.display_name,
      project_type: form.project_type,
      github_repo: form.github_repo,
      domain: form.domain,
      tls_mode: form.tls_mode,
      health_endpoint: form.health_endpoint,
      caddy_routes: routes,
    })
  } catch {
    toast.error('Failed to generate preview')
  } finally {
    loading.value = false
  }
}

async function executeDeploy() {
  deploying.value = true
  try {
    const envVarsObj: Record<string, string> = {}
    for (const v of form.env_vars) {
      if (v.key.trim()) envVarsObj[v.key.trim()] = v.value
    }

    result.value = await wizardService.execute({
      name: form.name,
      display_name: form.display_name,
      project_type: form.project_type,
      github_repo: form.github_repo,
      domain: form.domain,
      tls_mode: form.tls_mode,
      create_database: form.create_database,
      database_name: form.database_name || form.name.replace(/-/g, '_'),
      env_vars: envVarsObj,
      health_endpoint: form.health_endpoint,
      compose_filename: form.compose_filename,
      caddy_routes: form.use_custom_routes ? form.caddy_routes : undefined,
      first_deploy: form.first_deploy,
    })

    const errors = result.value.steps.filter(s => s.status === 'error')
    if (errors.length > 0) {
      toast.warning(`Completed with ${errors.length} error(s)`)
    } else {
      toast.success('Project deployed successfully!')
    }
  } catch (e: any) {
    toast.error(e.response?.data?.detail || 'Wizard execution failed')
  } finally {
    deploying.value = false
  }
}

async function copyToClipboard(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = label
    setTimeout(() => { copied.value = '' }, 2000)
  } catch {
    toast.error('Failed to copy')
  }
}

const stepLabels = ['Type', 'Repository', 'Domain', 'Database', 'Env Vars', 'Deploy']
const stepIcons = [Zap, Globe, Globe, Database, Key, Rocket]
</script>

<template>
  <div class="animate-fade-in">
    <PageHeader title="Deploy Wizard" description="Set up and deploy a new project end-to-end">
      <template #actions>
        <Button variant="outline" size="sm" @click="router.push('/projects')">
          <ArrowLeft class="w-4 h-4" /> Back to Projects
        </Button>
      </template>
    </PageHeader>

    <!-- Step indicator -->
    <div class="flex items-center gap-1 mb-8 overflow-x-auto pb-2">
      <template v-for="(label, idx) in stepLabels" :key="idx">
        <button
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap"
          :class="currentStep === idx + 1 ? 'bg-accent/10 text-accent border border-accent/20' : idx + 1 < currentStep ? 'bg-surface-tertiary text-accent' : 'bg-surface-tertiary text-text-tertiary'"
          @click="idx + 1 < currentStep ? currentStep = idx + 1 : null"
        >
          <component :is="idx + 1 < currentStep ? Check : stepIcons[idx]" class="w-3.5 h-3.5" />
          {{ label }}
        </button>
        <div v-if="idx < stepLabels.length - 1" class="w-4 h-px bg-border shrink-0" />
      </template>
    </div>

    <!-- ─── Step 1: Project Type ─── -->
    <div v-if="currentStep === 1" class="space-y-4">
      <h2 class="text-lg font-heading font-semibold text-text">Choose Project Type</h2>
      <p class="text-sm text-text-secondary">Select the framework or stack for your project.</p>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <button v-for="pt in PROJECT_TYPES" :key="pt.id"
          class="card p-5 text-left transition-all"
          :class="form.project_type === pt.id ? 'ring-2 ring-accent border-accent' : 'hover:border-border-medium'"
          @click="form.project_type = pt.id"
        >
          <div class="text-2xl mb-2">{{ pt.icon }}</div>
          <h3 class="text-sm font-heading font-semibold text-text">{{ pt.label }}</h3>
          <p class="text-xs text-text-secondary mt-1">{{ pt.desc }}</p>
        </button>
      </div>
    </div>

    <!-- ─── Step 2: GitHub Repository ─── -->
    <div v-if="currentStep === 2" class="space-y-4">
      <h2 class="text-lg font-heading font-semibold text-text">GitHub Repository</h2>
      <p class="text-sm text-text-secondary">Enter the GitHub repository for this project.</p>
      <div class="card p-5 space-y-4">
        <Input v-model="form.github_repo" label="GitHub Repository" placeholder="getpayd-tech/my-app" />
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input v-model="form.name" label="Project Name" placeholder="my-app" />
          <Input v-model="form.display_name" label="Display Name" placeholder="My App" />
        </div>
        <Input v-model="form.health_endpoint" label="Health Endpoint" :placeholder="defaults?.health_endpoint || '/health'" />
      </div>
    </div>

    <!-- ─── Step 3: Domain, TLS & Routing ─── -->
    <div v-if="currentStep === 3" class="space-y-4">
      <h2 class="text-lg font-heading font-semibold text-text">Domain, TLS & Routing</h2>
      <div class="card p-5 space-y-4">
        <Input v-model="form.domain" label="Domain" placeholder="app.paydlabs.com" />
        <div>
          <label class="block text-sm font-medium text-text mb-1.5">TLS Mode</label>
          <select v-model="form.tls_mode"
            class="w-full h-10 px-3 text-sm rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent">
            <option value="auto">Auto ACME (Let's Encrypt)</option>
            <option value="cloudflare_dns">Cloudflare DNS Challenge (wildcards)</option>
            <option value="off">Off (HTTP only)</option>
          </select>
        </div>

        <!-- Custom Caddy Routes -->
        <div class="pt-2 border-t border-border">
          <label class="flex items-center gap-3 cursor-pointer mb-3">
            <input v-model="form.use_custom_routes" type="checkbox" class="w-4 h-4 rounded border-border text-accent focus:ring-accent/20" />
            <div>
              <span class="text-sm font-medium text-text">Custom Caddy routes</span>
              <p class="text-xs text-text-secondary">Configure multiple path-to-upstream mappings (e.g. /api/*, /ingest/*, /callbacks/*)</p>
            </div>
          </label>

          <div v-if="form.use_custom_routes" class="space-y-2 pl-7">
            <div v-for="(route, idx) in form.caddy_routes" :key="idx" class="flex items-center gap-2">
              <input v-model="route.path" type="text" placeholder="/api/*"
                class="w-32 h-9 px-3 text-xs font-mono rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent" />
              <span class="text-text-tertiary text-xs">→</span>
              <input v-model="route.upstream" type="text" placeholder="container:8000"
                class="flex-1 h-9 px-3 text-xs font-mono rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent" />
              <button v-if="form.caddy_routes.length > 1" class="p-1.5 rounded-md text-text-tertiary hover:text-red-500 transition-colors" @click="removeRoute(idx)">
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
            <Button variant="outline" size="xs" @click="addRoute"><Plus class="w-3.5 h-3.5" /> Add Route</Button>
          </div>
        </div>
      </div>
    </div>

    <!-- ─── Step 4: Database ─── -->
    <div v-if="currentStep === 4" class="space-y-4">
      <h2 class="text-lg font-heading font-semibold text-text">Database</h2>
      <div class="card p-5 space-y-4">
        <label class="flex items-center gap-3 cursor-pointer">
          <input v-model="form.create_database" type="checkbox" class="w-4 h-4 rounded border-border text-accent focus:ring-accent/20" />
          <div>
            <span class="text-sm font-medium text-text">Create a PostgreSQL database</span>
            <p class="text-xs text-text-secondary">A new database and user will be created on the managed DigitalOcean cluster.</p>
          </div>
        </label>
        <div v-if="form.create_database">
          <Input v-model="form.database_name" label="Database Name" :placeholder="form.name.replace(/-/g, '_')" />
        </div>
      </div>
    </div>

    <!-- ─── Step 5: Environment Variables ─── -->
    <div v-if="currentStep === 5" class="space-y-4">
      <h2 class="text-lg font-heading font-semibold text-text">Environment Variables</h2>
      <div class="card p-5 space-y-3">
        <!-- Bulk paste mode -->
        <div v-if="bulkPasteMode" class="space-y-3">
          <p class="text-xs text-text-secondary">Paste your .env file content below. Lines starting with # are ignored.</p>
          <textarea v-model="bulkPasteText" rows="10" placeholder="DATABASE_URL=postgresql://...
SECRET_KEY=my-secret
APP_ENV=production"
            class="w-full px-3 py-2 text-xs font-mono rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent resize-y" />
          <div class="flex gap-2">
            <Button variant="accent" size="xs" @click="parseBulkPaste">Parse Variables</Button>
            <Button variant="outline" size="xs" @click="bulkPasteMode = false">Cancel</Button>
          </div>
        </div>

        <!-- Key-value mode -->
        <template v-else>
          <div v-for="(envVar, index) in form.env_vars" :key="index" class="flex items-center gap-2">
            <input v-model="envVar.key" type="text" placeholder="KEY"
              class="w-40 h-9 px-3 text-xs font-mono rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent" />
            <input v-model="envVar.value" type="text" placeholder="value"
              class="flex-1 h-9 px-3 text-xs font-mono rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent" />
            <button class="p-1.5 rounded-md text-text-tertiary hover:text-red-500 transition-colors" @click="removeEnvVar(index)">
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
          <div class="flex gap-2">
            <Button variant="outline" size="xs" @click="addEnvVar"><Plus class="w-3.5 h-3.5" /> Add Variable</Button>
            <Button variant="outline" size="xs" @click="bulkPasteMode = true"><FileText class="w-3.5 h-3.5" /> Bulk Paste</Button>
          </div>
          <p v-if="form.env_vars.length === 0" class="text-xs text-text-tertiary">No environment variables. Click "Bulk Paste" to paste an entire .env file.</p>
        </template>
      </div>
    </div>

    <!-- ─── Step 6: Review & Deploy ─── -->
    <div v-if="currentStep === 6" class="space-y-4">
      <h2 class="text-lg font-heading font-semibold text-text">Review & Deploy</h2>

      <!-- Summary -->
      <div class="card p-5">
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div><span class="text-text-tertiary text-xs">Type</span><p class="font-medium text-text">{{ form.project_type }}</p></div>
          <div><span class="text-text-tertiary text-xs">Name</span><p class="font-medium text-text">{{ form.name }}</p></div>
          <div><span class="text-text-tertiary text-xs">Domain</span><p class="font-medium text-text">{{ form.domain }}</p></div>
          <div><span class="text-text-tertiary text-xs">Database</span><p class="font-medium text-text">{{ form.create_database ? (form.database_name || form.name.replace(/-/g, '_')) : 'None' }}</p></div>
        </div>
      </div>

      <!-- Options row -->
      <div class="card p-5 space-y-3">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-medium text-text-secondary mb-1.5">Compose Filename</label>
            <select v-model="form.compose_filename"
              class="w-full h-9 px-3 text-sm rounded-lg border border-border bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent">
              <option value="docker-compose.yml">docker-compose.yml</option>
              <option value="docker-compose.prod.yml">docker-compose.prod.yml</option>
            </select>
          </div>
          <div class="flex items-end">
            <label class="flex items-center gap-2 cursor-pointer pb-2">
              <input v-model="form.first_deploy" type="checkbox" class="w-4 h-4 rounded border-border text-accent focus:ring-accent/20" />
              <span class="text-sm text-text">Pull & start containers after provisioning</span>
            </label>
          </div>
        </div>
      </div>

      <!-- Preview tabs -->
      <div v-if="previewData && !result" class="card overflow-hidden">
        <div class="flex border-b border-border">
          <button v-for="tab in (['compose', 'caddyfile', 'workflow'] as const)" :key="tab"
            class="px-4 py-2.5 text-xs font-medium transition-colors"
            :class="previewTab === tab ? 'text-accent border-b-2 border-accent bg-accent/5' : 'text-text-secondary hover:text-text'"
            @click="previewTab = tab">
            {{ tab === 'compose' ? form.compose_filename : tab === 'caddyfile' ? 'Caddyfile' : 'GitHub Actions' }}
          </button>
        </div>
        <div class="relative">
          <button class="absolute top-2 right-2 p-1.5 rounded-md text-text-tertiary hover:text-text hover:bg-surface-tertiary transition-colors z-10"
            @click="copyToClipboard(previewData[previewTab], previewTab)">
            <component :is="copied === previewTab ? Check : Copy" class="w-3.5 h-3.5" />
          </button>
          <pre class="p-4 text-xs font-mono text-text-secondary overflow-x-auto max-h-64 bg-surface-secondary">{{ previewData[previewTab] }}</pre>
        </div>
      </div>

      <!-- DNS Instructions -->
      <div v-if="!result" class="card p-4 flex items-start gap-3">
        <Info class="w-4 h-4 text-blue-500 mt-0.5 shrink-0" />
        <div class="text-xs text-text-secondary">
          <strong class="text-text">DNS:</strong> Point <code class="bg-surface-tertiary px-1 rounded">{{ form.domain }}</code> to <code class="bg-surface-tertiary px-1 rounded">{{ SERVER_IP }}</code> (A record).
          If <code class="bg-surface-tertiary px-1 rounded">*.paydlabs.com</code> wildcard exists, this is already covered.
        </div>
      </div>

      <!-- Loading preview -->
      <div v-if="loading" class="card p-8 text-center">
        <Loader2 class="w-6 h-6 mx-auto text-accent animate-spin mb-2" />
        <p class="text-sm text-text-secondary">Generating preview...</p>
      </div>

      <!-- Deploy result -->
      <div v-if="result" class="space-y-4">
        <!-- Steps progress -->
        <div class="card p-5 space-y-3">
          <h3 class="text-sm font-heading font-semibold text-text mb-3">Provisioning & Deployment Steps</h3>
          <div v-for="step in result.steps" :key="step.step" class="flex items-start gap-3">
            <div class="mt-0.5">
              <CheckCircle2 v-if="step.status === 'complete'" class="w-4 h-4 text-accent" />
              <XCircle v-else-if="step.status === 'error'" class="w-4 h-4 text-red-500" />
              <Clock v-else class="w-4 h-4 text-text-tertiary" />
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-text">{{ step.name }}</p>
              <p class="text-xs text-text-secondary break-all">{{ step.message }}</p>
            </div>
            <Badge :variant="step.status === 'complete' ? 'success' : step.status === 'error' ? 'error' : 'neutral'" size="sm">
              {{ step.status }}
            </Badge>
          </div>
        </div>

        <!-- GitHub Secrets -->
        <div class="card p-5 space-y-3">
          <h3 class="text-sm font-heading font-semibold text-text">GitHub Secrets</h3>
          <p class="text-xs text-text-secondary">Add these to your repo at <code class="bg-surface-tertiary px-1 rounded">github.com/{{ form.github_repo }}/settings/secrets/actions</code></p>
          <div class="space-y-2">
            <div v-for="secret in [
              { name: 'DROPLET_IP', value: SERVER_IP },
              { name: 'DROPLET_USER', value: 'deploy' },
              { name: 'DROPLET_SSH_KEY', value: '(same SSH private key as other Payd projects)' },
              { name: 'SENTINEL_WEBHOOK_SECRET', value: result.webhook_secret },
            ]" :key="secret.name" class="flex items-center gap-2 text-xs">
              <code class="w-48 shrink-0 text-accent font-mono bg-surface-tertiary px-2 py-1 rounded">{{ secret.name }}</code>
              <code class="flex-1 font-mono bg-surface-tertiary px-2 py-1 rounded text-text-secondary truncate">{{ secret.value }}</code>
              <button class="p-1 rounded text-text-tertiary hover:text-accent transition-colors shrink-0" @click="copyToClipboard(secret.value, secret.name)">
                <component :is="copied === secret.name ? Check : Copy" class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        <!-- GitHub Actions workflow -->
        <div class="card overflow-hidden">
          <div class="flex items-center justify-between px-4 py-3 border-b border-border">
            <h3 class="text-sm font-heading font-semibold text-text">GitHub Actions Workflow</h3>
            <button class="p-1.5 rounded-md text-text-tertiary hover:text-accent transition-colors"
              @click="copyToClipboard(result.workflow_preview, 'workflow-result')">
              <component :is="copied === 'workflow-result' ? Check : Copy" class="w-3.5 h-3.5" />
            </button>
          </div>
          <pre class="p-4 text-xs font-mono text-text-secondary overflow-x-auto max-h-48 bg-surface-secondary">{{ result.workflow_preview }}</pre>
          <div class="px-4 py-2 bg-surface-tertiary text-xs text-text-secondary">
            Copy this to <code>.github/workflows/deploy.yml</code> in your repo
          </div>
        </div>

        <div class="flex items-center gap-3">
          <Button variant="accent" size="sm" @click="router.push('/projects')">
            <Check class="w-4 h-4" /> Go to Projects
          </Button>
        </div>
      </div>

      <!-- Deploy button -->
      <div v-if="!result && previewData" class="flex justify-end">
        <Button variant="accent" size="md" :loading="deploying" @click="executeDeploy">
          <Rocket class="w-4 h-4" /> {{ form.first_deploy ? 'Provision & Deploy' : 'Provision Project' }}
        </Button>
      </div>
    </div>

    <!-- Navigation -->
    <div v-if="!result" class="flex items-center justify-between mt-8 pt-4 border-t border-border">
      <Button v-if="currentStep > 1" variant="outline" size="sm" @click="prevStep">
        <ArrowLeft class="w-4 h-4" /> Back
      </Button>
      <div v-else />
      <Button v-if="currentStep < totalSteps" variant="accent" size="sm" :disabled="!canProceed" @click="nextStep">
        Next <ArrowRight class="w-4 h-4" />
      </Button>
    </div>
  </div>
</template>
