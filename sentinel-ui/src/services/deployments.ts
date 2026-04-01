import api from './api'
import type { DeploymentInfo, DeploymentList, DeployRequest } from '@/types'

export const deploymentsService = {
  async list(params?: {
    project_id?: string
    page?: number
    per_page?: number
  }): Promise<DeploymentList> {
    const { data } = await api.get<DeploymentList>('/deployments', { params })
    return data
  },

  async get(id: string): Promise<DeploymentInfo> {
    const { data } = await api.get<DeploymentInfo>(`/deployments/${id}`)
    return data
  },

  async deploy(projectId: string, request?: DeployRequest): Promise<DeploymentInfo> {
    const { data } = await api.post<DeploymentInfo>(
      `/deployments/${projectId}/deploy`,
      request ?? {}
    )
    return data
  },

  async rollback(projectId: string, deploymentId: string): Promise<DeploymentInfo> {
    const { data } = await api.post<DeploymentInfo>(
      `/deployments/${projectId}/rollback/${deploymentId}`
    )
    return data
  },
}
