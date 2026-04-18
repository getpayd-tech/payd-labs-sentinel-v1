import api from './api'
import type { SetupRequest, SetupStatus } from '@/types'

export const setupService = {
  async status(): Promise<SetupStatus> {
    const { data } = await api.get<SetupStatus>('/setup/status')
    return data
  },

  async submit(body: SetupRequest): Promise<void> {
    await api.post('/setup', body)
  },
}
