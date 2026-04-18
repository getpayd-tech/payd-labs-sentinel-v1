import api from './api'
import type {
  AuthEvent,
  AuthEventType,
  AuthStats,
  Fail2banEvent,
  IpHistory,
  JailList,
  JailStatus,
} from '@/types'

export const securityService = {
  async listJails(): Promise<JailList> {
    const { data } = await api.get<JailList>('/security/jails')
    return data
  },

  async getJail(jail: string): Promise<JailStatus> {
    const { data } = await api.get<JailStatus>(`/security/jails/${encodeURIComponent(jail)}`)
    return data
  },

  async banIp(jail: string, ip: string): Promise<void> {
    await api.post(`/security/jails/${encodeURIComponent(jail)}/ban`, { ip })
  },

  async unbanIp(jail: string, ip: string): Promise<void> {
    await api.delete(`/security/jails/${encodeURIComponent(jail)}/banned/${encodeURIComponent(ip)}`)
  },

  async activity(limit = 100, onlyActions = true): Promise<Fail2banEvent[]> {
    const { data } = await api.get<Fail2banEvent[]>('/security/activity', {
      params: { limit, only_actions: onlyActions },
    })
    return data
  },

  async ipHistory(ip: string): Promise<IpHistory> {
    const { data } = await api.get<IpHistory>(`/security/ips/${encodeURIComponent(ip)}/history`)
    return data
  },

  async authLog(limit = 100, eventType?: AuthEventType): Promise<AuthEvent[]> {
    const params: Record<string, string | number> = { limit }
    if (eventType) params.event_type = eventType
    const { data } = await api.get<AuthEvent[]>('/security/auth-log', { params })
    return data
  },

  async authStats(hours = 24): Promise<AuthStats> {
    const { data } = await api.get<AuthStats>('/security/auth-stats', { params: { hours } })
    return data
  },
}
