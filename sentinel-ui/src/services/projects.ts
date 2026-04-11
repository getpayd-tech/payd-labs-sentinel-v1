import api from './api'
import type {
  ProjectInfo,
  ProjectCreate,
  ProjectUpdate,
  TemplateInfo,
  EnvVar,
  ProvisionRequest,
  ScanResult,
} from '@/types'

function normalizeProject(p: any): ProjectInfo {
  return {
    ...p,
    type: p.type || p.project_type || 'custom',
    container_count: p.container_count ?? (p.container_names ? Object.keys(p.container_names).length : 0),
    github_repo: p.github_repo || '',
    domain: p.domain || null,
  }
}

export const projectsService = {
  async list(): Promise<ProjectInfo[]> {
    const { data } = await api.get('/projects')
    const items = data.items ?? data
    return items.map(normalizeProject)
  },

  async get(id: string): Promise<ProjectInfo> {
    const { data } = await api.get(`/projects/${id}`)
    return normalizeProject(data)
  },

  async create(payload: ProjectCreate): Promise<ProjectInfo> {
    const { data } = await api.post<ProjectInfo>('/projects', payload)
    return data
  },

  async update(id: string, payload: ProjectUpdate): Promise<ProjectInfo> {
    const { data } = await api.put<ProjectInfo>(`/projects/${id}`, payload)
    return data
  },

  async remove(id: string): Promise<void> {
    await api.delete(`/projects/${id}`)
  },

  async provision(id: string, payload: ProvisionRequest): Promise<ProjectInfo> {
    const { data } = await api.post<ProjectInfo>(`/projects/${id}/provision`, payload)
    return data
  },

  async getEnv(id: string, reveal = false): Promise<EnvVar[]> {
    const { data } = await api.get<EnvVar[]>(`/projects/${id}/env`, { params: { reveal } })
    return data
  },

  async updateEnv(id: string, vars: Record<string, string>): Promise<void> {
    await api.put(`/projects/${id}/env`, { variables: vars })
  },

  async getTemplates(): Promise<TemplateInfo[]> {
    const { data } = await api.get<TemplateInfo[]>('/projects/templates')
    return data
  },

  async scan(): Promise<ScanResult> {
    const { data } = await api.post<ScanResult>('/projects/scan')
    return data
  },
}
