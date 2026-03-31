import api from './api'
import type { DashboardStats, HealthOverview } from '@/types'

export const dashboardService = {
  async getStats(): Promise<DashboardStats> {
    const { data } = await api.get<DashboardStats>('/dashboard/stats')
    return data
  },

  async getHealth(): Promise<HealthOverview> {
    const { data } = await api.get<HealthOverview>('/dashboard/health')
    return data
  },
}
