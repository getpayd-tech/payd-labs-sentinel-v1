import api from './api'
import type { CustomDomainList } from '@/types'

export const customDomainsService = {
  async listAll(projectId?: string): Promise<CustomDomainList> {
    const params: Record<string, string> = {}
    if (projectId) params.project_id = projectId
    const { data } = await api.get<CustomDomainList>('/custom-domains/all', { params })
    return data
  },

  async adminRemove(domain: string): Promise<void> {
    await api.delete(`/custom-domains/admin/${encodeURIComponent(domain)}`)
  },

  async generateServiceKey(projectId: string): Promise<{ service_api_key: string }> {
    const { data } = await api.post<{ service_api_key: string }>(`/projects/${projectId}/generate-service-key`)
    return data
  },
}
