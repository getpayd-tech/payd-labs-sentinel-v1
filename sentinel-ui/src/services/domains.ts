import api from './api'
import type { DomainInfo, DomainCreate, DomainUpdate } from '@/types'

export const domainsService = {
  async list(): Promise<DomainInfo[]> {
    const { data } = await api.get<DomainInfo[]>('/domains')
    return data
  },

  async create(payload: DomainCreate): Promise<DomainInfo> {
    const { data } = await api.post<DomainInfo>('/domains', payload)
    return data
  },

  async update(domain: string, payload: DomainUpdate): Promise<DomainInfo> {
    const { data } = await api.put<DomainInfo>(
      `/domains/${encodeURIComponent(domain)}`,
      payload
    )
    return data
  },

  async remove(domain: string): Promise<void> {
    await api.delete(`/domains/${encodeURIComponent(domain)}`)
  },

  async reload(): Promise<{ success: boolean; message: string }> {
    const { data } = await api.post<{ success: boolean; message: string }>('/domains/reload')
    return data
  },
}
