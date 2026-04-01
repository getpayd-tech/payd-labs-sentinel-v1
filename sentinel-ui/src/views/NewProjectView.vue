<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { projectsService } from '@/services/projects'
import PageHeader from '@/components/ui/PageHeader.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import Input from '@/components/ui/Input.vue'
import { useToast } from 'vue-toastification'
import type { ProjectType } from '@/types'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  FolderGit2,
  Zap,
  Globe,
  Layers,
  FileCode,
  Blend,
  Plus,
  Trash2,
  Rocket,
} from 'lucide-vue-next'

const router = useRouter()
const queryClient = useQueryClient()
const toast = useToast()

const currentStep = ref(1)
const totalSteps = 4

const projectData = reactive({
  type: '' as ProjectType | '',
  name: '',
  display_name: '',
  domain: '',
  github_repo: '',
  ghcr_image: '',
  health_endpoint: '',
})

const envVars = ref<{ key: string; value: string }[]>([])

const errors = reactive({
  type: '',
  name: '',
  display_name: '',
})

const projectTypes: { type: ProjectType; label: string; description: string; icon: typeof Zap }[] = [
  { type: 'fastapi', label: 'FastAPI', description: 'Python REST API with uvicorn', icon: Zap },
  { type: 'vue', label: 'Vue', description: 'Vue.js SPA with Vite', icon: Globe },
  { type: 'laravel', label: 'Laravel', description: 'PHP framework with Nginx', icon: Layers },
  { type: 'static', label: 'Static', description: 'Static files served by Caddy', icon: FileCode },
  { type: 'blended', label: 'Blended', description: 'Multi-container compose setup', icon: Blend },
]

function selectType(type: ProjectType) {
  projectData.type = type
  errors.type = ''
}

function addEnvVar() {
  envVars.value.push({ key: '', value: '' })
}

function removeEnvVar(index: number) {
  envVars.value.splice(index, 1)
}

function validateStep(step: number): boolean {
  errors.type = ''
  errors.name = ''
  errors.display_name = ''

  if (step === 1) {
    if (!projectData.type) {
      errors.type = 'Please select a project type'
      return false
    }
  }

  if (step === 2) {
    let valid = true
    if (!projectData.name) {
      errors.name = 'Project slug is required'
      valid = false
    } else if (!/^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/.test(projectData.name)) {
      errors.name = 'Must be lowercase alphanumeric with hyphens only'
      valid = false
    }
    if (!projectData.display_name) {
      errors.display_name = 'Display name is required'
      valid = false
    }
    return valid
  }

  return true
}

function nextStep() {
  if (!validateStep(currentStep.value)) return
  if (currentStep.value < totalSteps) {
    currentStep.value++
  }
}

function prevStep() {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

const envVarsRecord = computed(() => {
  const record: Record<string, string> = {}
  for (const { key, value } of envVars.value) {
    if (key.trim()) {
      record[key.trim()] = value
    }
  }
  return record
})

const createMutation = useMutation({
  mutationFn: async () => {
    const payload = {
      name: projectData.name,
      display_name: projectData.display_name,
      type: projectData.type as ProjectType,
      domain: projectData.domain || undefined,
      github_repo: projectData.github_repo || undefined,
      ghcr_image: projectData.ghcr_image || undefined,
      health_endpoint: projectData.health_endpoint || undefined,
      env_vars: Object.keys(envVarsRecord.value).length > 0 ? envVarsRecord.value : undefined,
    }
    const project = await projectsService.create(payload)
    await projectsService.provision(project.id, {
      env_vars: Object.keys(envVarsRecord.value).length > 0 ? envVarsRecord.value : undefined,
    })
    return project
  },
  onSuccess: (project) => {
    toast.success(`Project "${project.display_name}" created and provisioned!`)
    queryClient.invalidateQueries({ queryKey: ['projects'] })
    router.push(`/projects/${project.id}`)
  },
  onError: (e: any) => {
    toast.error(e.response?.data?.detail || 'Failed to create project')
  },
})

const stepLabels = ['Type', 'Configure', 'Env Vars', 'Review']
</script>

<template>
  <div class="animate-fade-in">
    <!-- Back button -->
    <button
      class="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-kPrimary dark:hover:text-white transition-colors mb-4"
      @click="router.push('/projects')"
    >
      <ArrowLeft class="w-4 h-4" />
      Back to Projects
    </button>

    <PageHeader
      title="New Project"
      description="Create a new infrastructure project"
    />

    <!-- Step indicator -->
    <div class="flex items-center gap-2 mb-6">
      <template v-for="(label, index) in stepLabels" :key="index">
        <div class="flex items-center gap-2">
          <div
            :class="[
              'w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors',
              currentStep > index + 1
                ? 'bg-accent text-white'
                : currentStep === index + 1
                  ? 'bg-kPrimary dark:bg-white text-white dark:text-kPrimary'
                  : 'bg-gray-100 dark:bg-neutral-800 text-gray-400 dark:text-gray-500',
            ]"
          >
            <Check v-if="currentStep > index + 1" class="w-4 h-4" />
            <span v-else>{{ index + 1 }}</span>
          </div>
          <span
            :class="[
              'text-sm font-medium hidden sm:inline',
              currentStep >= index + 1
                ? 'text-kPrimary dark:text-white'
                : 'text-gray-400 dark:text-gray-500',
            ]"
          >
            {{ label }}
          </span>
        </div>
        <div
          v-if="index < stepLabels.length - 1"
          :class="[
            'flex-1 h-px max-w-16',
            currentStep > index + 1
              ? 'bg-accent'
              : 'bg-gray-200 dark:bg-neutral-700',
          ]"
        />
      </template>
    </div>

    <!-- Step 1: Select project type -->
    <div v-if="currentStep === 1" class="space-y-4">
      <h2 class="text-lg font-heading font-semibold text-kPrimary dark:text-white">
        Select Project Type
      </h2>
      <p v-if="errors.type" class="text-sm text-red-500 dark:text-red-400">{{ errors.type }}</p>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
        <div
          v-for="pt in projectTypes"
          :key="pt.type"
          :class="[
            'card-hover p-5 cursor-pointer',
            projectData.type === pt.type
              ? 'ring-2 ring-accent border-accent dark:border-accent'
              : '',
          ]"
          @click="selectType(pt.type)"
        >
          <div class="flex items-center gap-3 mb-2">
            <div
              :class="[
                'w-10 h-10 rounded-lg flex items-center justify-center shrink-0',
                projectData.type === pt.type
                  ? 'bg-accent/10'
                  : 'bg-kPrimary/5 dark:bg-neutral-800',
              ]"
            >
              <component
                :is="pt.icon"
                :class="[
                  'w-5 h-5',
                  projectData.type === pt.type
                    ? 'text-accent'
                    : 'text-kPrimary dark:text-gray-400',
                ]"
              />
            </div>
            <div>
              <h3 class="text-sm font-semibold font-heading text-kPrimary dark:text-white">
                {{ pt.label }}
              </h3>
              <p class="text-2xs text-gray-500 dark:text-gray-400">{{ pt.description }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Step 2: Configure -->
    <div v-if="currentStep === 2" class="space-y-4">
      <h2 class="text-lg font-heading font-semibold text-kPrimary dark:text-white">
        Configure Project
      </h2>
      <div class="card p-5 space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            v-model="projectData.name"
            label="Project Slug"
            placeholder="my-project"
            :error="errors.name"
          />
          <Input
            v-model="projectData.display_name"
            label="Display Name"
            placeholder="My Project"
            :error="errors.display_name"
          />
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            v-model="projectData.domain"
            label="Domain"
            placeholder="app.example.com"
          />
          <Input
            v-model="projectData.github_repo"
            label="GitHub Repository"
            placeholder="org/repo-name"
          />
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            v-model="projectData.ghcr_image"
            label="GHCR Image"
            placeholder="ghcr.io/org/image"
          />
          <Input
            v-model="projectData.health_endpoint"
            label="Health Endpoint"
            placeholder="/health"
          />
        </div>
      </div>
    </div>

    <!-- Step 3: Environment variables -->
    <div v-if="currentStep === 3" class="space-y-4">
      <h2 class="text-lg font-heading font-semibold text-kPrimary dark:text-white">
        Environment Variables
      </h2>
      <div class="card p-5">
        <div v-if="envVars.length === 0" class="text-center py-6">
          <p class="text-sm text-gray-500 dark:text-gray-400 mb-3">
            No environment variables configured. Add some if your project needs them.
          </p>
        </div>
        <div v-else class="space-y-3">
          <div
            v-for="(envVar, index) in envVars"
            :key="index"
            class="flex items-center gap-3"
          >
            <div class="flex-1">
              <input
                v-model="envVar.key"
                type="text"
                placeholder="KEY"
                class="w-full h-9 px-3 text-sm font-mono rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-kPrimary dark:text-white focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors placeholder:text-gray-400"
              />
            </div>
            <div class="flex-1">
              <input
                v-model="envVar.value"
                type="text"
                placeholder="value"
                class="w-full h-9 px-3 text-sm font-mono rounded-lg border border-kPrimary/15 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-kPrimary dark:text-white focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors placeholder:text-gray-400"
              />
            </div>
            <button
              class="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
              title="Remove"
              @click="removeEnvVar(index)"
            >
              <Trash2 class="w-4 h-4" />
            </button>
          </div>
        </div>
        <div class="mt-4">
          <Button variant="outline" size="sm" @click="addEnvVar">
            <Plus class="w-4 h-4" />
            Add Variable
          </Button>
        </div>
      </div>
    </div>

    <!-- Step 4: Review -->
    <div v-if="currentStep === 4" class="space-y-4">
      <h2 class="text-lg font-heading font-semibold text-kPrimary dark:text-white">
        Review & Create
      </h2>
      <div class="card p-5 space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Type</span>
            <p class="text-sm font-medium text-kPrimary dark:text-white mt-0.5">
              <Badge :variant="projectData.type === 'fastapi' ? 'success' : projectData.type === 'vue' ? 'info' : projectData.type === 'laravel' ? 'error' : projectData.type === 'blended' ? 'warning' : 'neutral'" size="sm">
                {{ projectData.type }}
              </Badge>
            </p>
          </div>
          <div>
            <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Slug</span>
            <p class="text-sm font-mono font-medium text-kPrimary dark:text-white mt-0.5">{{ projectData.name }}</p>
          </div>
          <div>
            <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Display Name</span>
            <p class="text-sm font-medium text-kPrimary dark:text-white mt-0.5">{{ projectData.display_name }}</p>
          </div>
          <div v-if="projectData.domain">
            <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Domain</span>
            <p class="text-sm font-medium text-kPrimary dark:text-white mt-0.5">{{ projectData.domain }}</p>
          </div>
          <div v-if="projectData.github_repo">
            <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">GitHub Repo</span>
            <p class="text-sm font-medium text-kPrimary dark:text-white mt-0.5">{{ projectData.github_repo }}</p>
          </div>
          <div v-if="projectData.ghcr_image">
            <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">GHCR Image</span>
            <p class="text-sm font-mono font-medium text-kPrimary dark:text-white mt-0.5">{{ projectData.ghcr_image }}</p>
          </div>
          <div v-if="projectData.health_endpoint">
            <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Health Endpoint</span>
            <p class="text-sm font-mono font-medium text-kPrimary dark:text-white mt-0.5">{{ projectData.health_endpoint }}</p>
          </div>
        </div>

        <!-- Env vars summary -->
        <div v-if="envVars.length > 0">
          <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Environment Variables</span>
          <div class="mt-2 space-y-1">
            <div
              v-for="(envVar, index) in envVars"
              :key="index"
              class="flex items-center gap-2 text-sm font-mono"
            >
              <span class="text-kPrimary dark:text-white">{{ envVar.key }}</span>
              <span class="text-gray-400">=</span>
              <span class="text-gray-500 dark:text-gray-400">{{ envVar.value ? '********' : '(empty)' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Navigation buttons -->
    <div class="flex items-center justify-between mt-6">
      <Button
        v-if="currentStep > 1"
        variant="outline"
        size="sm"
        @click="prevStep"
      >
        <ArrowLeft class="w-4 h-4" />
        Back
      </Button>
      <div v-else />

      <div class="flex items-center gap-2">
        <Button
          v-if="currentStep < totalSteps"
          variant="accent"
          size="sm"
          @click="nextStep"
        >
          Next
          <ArrowRight class="w-4 h-4" />
        </Button>
        <Button
          v-if="currentStep === totalSteps"
          variant="accent"
          size="sm"
          :loading="createMutation.isPending.value"
          @click="createMutation.mutate()"
        >
          <Rocket class="w-4 h-4" />
          Create & Provision
        </Button>
      </div>
    </div>
  </div>
</template>
