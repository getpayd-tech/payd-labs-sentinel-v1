import axios from 'axios'
import { authService } from './auth'

const TOKEN_KEY = 'sentinel_admin_token'
const REFRESH_KEY = 'sentinel_admin_refresh'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: add x-auth-token header (Payd Auth pattern)
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      config.headers['x-auth-token'] = token
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Track in-flight refresh to prevent concurrent refresh attempts
let refreshPromise: Promise<boolean> | null = null

async function attemptTokenRefresh(): Promise<boolean> {
  const refreshToken = localStorage.getItem(REFRESH_KEY)
  if (!refreshToken) return false

  try {
    const response = await authService.refresh(refreshToken)
    const newAuth = response.authToken || (response as any).auth_token || ''
    const newRefresh = response.refreshToken || (response as any).refresh_token || ''
    if (newAuth) {
      localStorage.setItem(TOKEN_KEY, newAuth)
      if (newRefresh) localStorage.setItem(REFRESH_KEY, newRefresh)
      return true
    }
  } catch {
    // Refresh failed — token is truly expired
  }
  return false
}

// Response interceptor: attempt refresh on 401/403, logout if refresh fails
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status
    const originalRequest = error.config

    // Only attempt refresh on 401/403, and only once per request
    if ((status === 401 || status === 403) && !originalRequest._retried) {
      originalRequest._retried = true

      // Deduplicate concurrent refresh calls
      if (!refreshPromise) {
        refreshPromise = attemptTokenRefresh().finally(() => {
          refreshPromise = null
        })
      }

      const refreshed = await refreshPromise
      if (refreshed) {
        // Retry the original request with the new token
        originalRequest.headers['x-auth-token'] = localStorage.getItem(TOKEN_KEY)
        return api(originalRequest)
      }

      // Refresh failed — clear everything and redirect to login
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_KEY)
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  }
)

export default api
