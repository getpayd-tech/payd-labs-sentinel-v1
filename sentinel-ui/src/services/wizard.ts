import api from './api'

export interface TypeDefaults {
  port: number
  health_endpoint: string
  suggested_env: string[]
  description: string
  container_count: number
}

export interface WizardPreview {
  compose: string
  caddyfile: string
  workflow: string
}

export interface WizardStep {
  step: number
  name: string
  status: 'pending' | 'complete' | 'error'
  message: string
}

export interface WizardResponse {
  project_id: string
  webhook_secret: string
  compose_preview: string
  caddyfile_preview: string
  workflow_preview: string
  steps: WizardStep[]
}

export const wizardService = {
  async getDefaults(projectType: string): Promise<TypeDefaults> {
    const { data } = await api.get(`/projects/wizard/defaults/${projectType}`)
    return data
  },

  async preview(request: {
    name: string
    display_name?: string
    project_type: string
    github_repo: string
    domain?: string
    tls_mode?: string
    health_endpoint?: string
  }): Promise<WizardPreview> {
    const { data } = await api.post('/projects/wizard/preview', request)
    return data
  },

  async execute(request: {
    name: string
    display_name: string
    project_type: string
    github_repo: string
    domain: string
    tls_mode?: string
    create_database?: boolean
    database_name?: string
    env_vars?: Record<string, string>
    health_endpoint?: string
  }): Promise<WizardResponse> {
    const { data } = await api.post('/projects/wizard', request)
    return data
  },
}
