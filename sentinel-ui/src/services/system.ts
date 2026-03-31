import api from './api'
import type { SystemMetrics, MetricsHistoryPoint } from '@/types'

export const systemService = {
  async getMetrics(): Promise<SystemMetrics> {
    const { data } = await api.get<SystemMetrics>('/system/metrics')
    return data
  },

  async getMetricsHistory(hours?: number): Promise<MetricsHistoryPoint[]> {
    const params: Record<string, number> = {}
    if (hours) params.hours = hours

    const { data } = await api.get<MetricsHistoryPoint[]>('/system/metrics/history', { params })
    return data
  },
}
