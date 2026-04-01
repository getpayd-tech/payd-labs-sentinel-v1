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

export const projectsService = {
  async list(): Promise<ProjectInfo[]> {
    const { data } = await api.get<ProjectInfo[]>('/projects')
    return data
  },

  async get(id: string): Promise<ProjectInfo> {
    const { data } = await api.get<ProjectInfo>(`/projects/${id}`)
    return data
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

  async getEnv(id: string): Promise<EnvVar[]> {
    const { data } = await api.get<EnvVar[]>(`/projects/${id}/env`)
    return data
  },

  async updateEnv(id: string, vars: Record<string, string>): Promise<void> {
    await api.put(`/projects/${id}/env`, vars)
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
