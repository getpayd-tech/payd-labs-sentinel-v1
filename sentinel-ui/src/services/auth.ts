import api from './api'
import type {
  LoginResponse,
  OtpResponse,
  VerifyOtpResponse,
  RefreshResponse,
  User,
} from '@/types'

export const authService = {
  /** Step 1: Login with username + password, returns session_token */
  async login(username: string, password: string): Promise<LoginResponse> {
    const { data } = await api.post<LoginResponse>('/auth/login', {
      username,
      password,
    })
    return data
  },

  /** Step 2: Request OTP to be sent (requires session_token) */
  async requestOtp(sessionToken: string): Promise<OtpResponse> {
    const { data } = await api.post<OtpResponse>(
      '/auth/request-otp',
      {},
      { headers: { 'x-session-token': sessionToken } }
    )
    return data
  },

  /** Step 3: Verify OTP code, returns auth_token + refresh_token */
  async verifyOtp(otp: string, sessionToken: string): Promise<VerifyOtpResponse> {
    const { data } = await api.post<VerifyOtpResponse>('/auth/verify-otp', {
      otp,
      session_token: sessionToken,
    })
    return data
  },

  /** Refresh auth_token using refresh_token */
  async refresh(refreshToken: string): Promise<RefreshResponse> {
    const { data } = await api.post<RefreshResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    })
    return data
  },

  /** Get current user profile */
  async getMe(token: string): Promise<User> {
    const { data } = await api.get<User>('/auth/me', {
      headers: { 'x-auth-token': token },
    })
    return data
  },
}
