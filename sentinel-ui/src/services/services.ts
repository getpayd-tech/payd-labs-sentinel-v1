import api from './api'
import type { ContainerInfo, ContainerDetail, ContainerAction, ContainerLogs } from '@/types'

export const servicesService = {
  async listContainers(): Promise<ContainerInfo[]> {
    const { data } = await api.get<ContainerInfo[]>('/services')
    return data
  },

  async getContainer(name: string): Promise<ContainerDetail> {
    const { data } = await api.get<ContainerDetail>(`/services/${name}`)
    return data
  },

  async restartContainer(name: string): Promise<ContainerAction> {
    const { data } = await api.post<ContainerAction>(`/services/${name}/restart`)
    return data
  },

  async stopContainer(name: string): Promise<ContainerAction> {
    const { data } = await api.post<ContainerAction>(`/services/${name}/stop`)
    return data
  },

  async startContainer(name: string): Promise<ContainerAction> {
    const { data } = await api.post<ContainerAction>(`/services/${name}/start`)
    return data
  },

  async getContainerLogs(
    name: string,
    tail?: number,
    since?: string
  ): Promise<ContainerLogs> {
    const params: Record<string, string | number> = {}
    if (tail) params.tail = tail
    if (since) params.since = since

    const { data } = await api.get<ContainerLogs>(`/services/${name}/logs`, { params })
    return data
  },
}
