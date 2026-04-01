import api from './api'
import type { AuditList, AuditParams } from '@/types'

export const auditService = {
  async list(params?: AuditParams): Promise<AuditList> {
    const { data } = await api.get<AuditList>('/audit', { params })
    return data
  },
}
