import api from './api'
import type { LoginResponse, User } from '@/types'

export const authService = {
  async login(username: string, password: string): Promise<LoginResponse> {
    const { data } = await api.post<LoginResponse>('/auth/login', {
      username,
      password,
    })
    return data
  },

  async refresh(refreshToken: string): Promise<LoginResponse> {
    const { data } = await api.post<LoginResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    })
    return data
  },

  async getMe(): Promise<User> {
    const { data } = await api.get<User>('/auth/me')
    return data
  },
}
