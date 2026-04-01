import api from './api'

export const authService = {
  /** Step 1: Login with username + password, returns sessionToken */
  async login(username: string, password: string) {
    const { data } = await api.post('/auth/login', { username, password })
    return data as { sessionToken: string; [key: string]: unknown }
  },

  /** Step 2: Request OTP to be sent (requires session token in header) */
  async requestOtp(sessionToken: string) {
    const { data } = await api.post('/auth/request-otp', {}, {
      headers: { 'x-session-token': sessionToken },
    })
    return data as { sessionToken?: string; message?: string; [key: string]: unknown }
  },

  /** Step 3: Verify OTP code (session token in header, otp in body) */
  async verifyOtp(otp: string, sessionToken: string) {
    const { data } = await api.post('/auth/verify-otp', { otp }, {
      headers: { 'x-session-token': sessionToken },
    })
    return data as { authToken: string; refreshToken: string; [key: string]: unknown }
  },

  /** Refresh auth token using refresh token */
  async refresh(refreshToken: string) {
    const { data } = await api.post('/auth/refresh', { refresh_token: refreshToken })
    return data as { authToken: string; refreshToken: string; [key: string]: unknown }
  },

  /** Get current user profile (token in header) */
  async getMe(token: string) {
    const { data } = await api.get('/auth/me', {
      headers: { 'x-auth-token': token },
    })
    return data as {
      user_id: string
      username: string
      email: string
      is_admin: boolean
      first_name: string
      last_name: string
    }
  },
}
