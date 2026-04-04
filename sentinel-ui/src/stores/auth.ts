import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useRouter } from 'vue-router'
import { authService } from '@/services/auth'

const TOKEN_KEY = 'sentinel_admin_token'
const REFRESH_KEY = 'sentinel_admin_refresh'

function decodeJwt(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    const padded = payload + '='.repeat(4 - (payload.length % 4))
    const decoded = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(decoded)
  } catch {
    return null
  }
}

function isTokenExpired(token: string): boolean {
  const payload = decodeJwt(token)
  if (!payload?.exp) return true
  return Date.now() >= (payload.exp as number) * 1000
}

export const useAuthStore = defineStore('auth', () => {
  const router = useRouter()
  const user = ref<Record<string, unknown> | null>(null)
  const isLoading = ref(false)
  const sessionToken = ref<string | null>(null)
  const authStep = ref<'login' | 'otp'>('login')

  const isAuthenticated = computed(() => !!user.value)

  /** Step 1: Login with username + password */
  async function login(username: string, password: string): Promise<void> {
    isLoading.value = true
    try {
      const response = await authService.login(username, password)
      // sessionToken comes as camelCase from backend (matching Stables)
      sessionToken.value = response.sessionToken || (response as any).session_token || ''
      // Automatically request OTP after successful login
      if (sessionToken.value) {
        const otpResp = await authService.requestOtp(sessionToken.value)
        // Updated session token may come back
        if (otpResp.sessionToken) {
          sessionToken.value = otpResp.sessionToken
        }
      }
      authStep.value = 'otp'
    } finally {
      isLoading.value = false
    }
  }

  /** Step 2: Resend OTP */
  async function resendOtp(): Promise<void> {
    if (!sessionToken.value) throw new Error('No session token')
    isLoading.value = true
    try {
      const resp = await authService.requestOtp(sessionToken.value)
      if (resp.sessionToken) {
        sessionToken.value = resp.sessionToken
      }
    } finally {
      isLoading.value = false
    }
  }

  /** Step 3: Verify OTP code */
  async function verifyOtp(code: string): Promise<void> {
    if (!sessionToken.value) throw new Error('No session token')
    isLoading.value = true
    try {
      const response = await authService.verifyOtp(code, sessionToken.value)
      // Tokens come as camelCase from backend (matching Stables)
      const authToken = response.authToken || (response as any).auth_token || ''
      const refreshToken = response.refreshToken || (response as any).refresh_token || ''

      if (!authToken) {
        throw new Error('No auth token received')
      }

      localStorage.setItem(TOKEN_KEY, authToken)
      if (refreshToken) {
        localStorage.setItem(REFRESH_KEY, refreshToken)
      }

      // Decode JWT and check is_admin
      const payload = decodeJwt(authToken)
      if (!payload?.is_admin) {
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem(REFRESH_KEY)
        throw new Error('Access denied. Admin privileges required.')
      }

      // Fetch full user profile
      await fetchUser()
      startExpiryCheck()
      sessionToken.value = null
      authStep.value = 'login'
      router.push('/')
    } finally {
      isLoading.value = false
    }
  }

  async function logout(): Promise<void> {
    stopExpiryCheck()
    user.value = null
    sessionToken.value = null
    authStep.value = 'login'
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
    router.push('/login')
  }

  async function fetchUser(): Promise<void> {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) {
      user.value = null
      return
    }
    try {
      user.value = await authService.getMe(token)
    } catch {
      user.value = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_KEY)
    }
  }

  async function hydrate(): Promise<void> {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) return

    // Check if token is expired
    if (isTokenExpired(token)) {
      const refreshToken = localStorage.getItem(REFRESH_KEY)
      if (refreshToken) {
        try {
          const response = await authService.refresh(refreshToken)
          const newAuth = response.authToken || (response as any).auth_token || ''
          const newRefresh = response.refreshToken || (response as any).refresh_token || ''
          if (newAuth) {
            localStorage.setItem(TOKEN_KEY, newAuth)
            if (newRefresh) {
              localStorage.setItem(REFRESH_KEY, newRefresh)
            }
          } else {
            localStorage.removeItem(TOKEN_KEY)
            localStorage.removeItem(REFRESH_KEY)
            return
          }
        } catch {
          localStorage.removeItem(TOKEN_KEY)
          localStorage.removeItem(REFRESH_KEY)
          return
        }
      } else {
        localStorage.removeItem(TOKEN_KEY)
        return
      }
    }

    // Verify is_admin claim
    const currentToken = localStorage.getItem(TOKEN_KEY)
    if (currentToken) {
      const payload = decodeJwt(currentToken)
      if (!payload?.is_admin) {
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem(REFRESH_KEY)
        return
      }
    }

    await fetchUser()
    startExpiryCheck()
  }

  // Auto-logout: check token expiry every 60 seconds
  let expiryCheckInterval: ReturnType<typeof setInterval> | null = null

  function startExpiryCheck() {
    if (expiryCheckInterval) return
    expiryCheckInterval = setInterval(async () => {
      const token = localStorage.getItem(TOKEN_KEY)
      if (!token || !isTokenExpired(token)) return

      // Token expired — try refresh
      const refreshToken = localStorage.getItem(REFRESH_KEY)
      if (refreshToken) {
        try {
          const response = await authService.refresh(refreshToken)
          const newAuth = response.authToken || (response as any).auth_token || ''
          if (newAuth) {
            localStorage.setItem(TOKEN_KEY, newAuth)
            const newRefresh = response.refreshToken || (response as any).refresh_token || ''
            if (newRefresh) localStorage.setItem(REFRESH_KEY, newRefresh)
            return
          }
        } catch { /* refresh failed */ }
      }

      // Refresh failed — logout
      logout()
    }, 60_000)
  }

  function stopExpiryCheck() {
    if (expiryCheckInterval) {
      clearInterval(expiryCheckInterval)
      expiryCheckInterval = null
    }
  }

  function resetToLogin(): void {
    sessionToken.value = null
    authStep.value = 'login'
  }

  return {
    user,
    isLoading,
    isAuthenticated,
    sessionToken,
    authStep,
    login,
    resendOtp,
    verifyOtp,
    logout,
    fetchUser,
    hydrate,
    resetToLogin,
  }
})
