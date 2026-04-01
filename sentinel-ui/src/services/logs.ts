import api from './api'
import type { AggregatedLogs, LogsParams } from '@/types'

export const logsService = {
  async getAggregatedLogs(params?: LogsParams): Promise<AggregatedLogs> {
    const queryParams: Record<string, string | number> = {}

    if (params?.containers && params.containers.length > 0) {
      queryParams.containers = params.containers.join(',')
    }
    if (params?.search) queryParams.search = params.search
    if (params?.stream && params.stream !== 'all') queryParams.stream = params.stream
    if (params?.tail) queryParams.tail = params.tail

    const { data } = await api.get<AggregatedLogs>('/logs', { params: queryParams })
    return data
  },
}
