import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useRouter } from 'vue-router'
import { authService } from '@/services/auth'
import type { User, JwtPayload } from '@/types'

function decodeJwt(token: string): JwtPayload | null {
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(decoded) as JwtPayload
  } catch {
    return null
  }
}

function isTokenExpired(token: string): boolean {
  const payload = decodeJwt(token)
  if (!payload?.exp) return true
  return Date.now() >= payload.exp * 1000
}

export const useAuthStore = defineStore('auth', () => {
  const router = useRouter()
  const user = ref<User | null>(null)
  const isLoading = ref(false)
  const sessionToken = ref<string | null>(null)
  const authStep = ref<'login' | 'otp'>('login')

  const isAuthenticated = computed(() => !!user.value)

  /** Step 1: Login with username + password */
  async function login(username: string, password: string): Promise<void> {
    isLoading.value = true
    try {
      const response = await authService.login(username, password)
      sessionToken.value = response.session_token
      // Automatically request OTP after successful login
      await authService.requestOtp(response.session_token)
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
      await authService.requestOtp(sessionToken.value)
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
      localStorage.setItem('sentinel_admin_token', response.auth_token)
      localStorage.setItem('sentinel_admin_refresh', response.refresh_token)

      // Decode JWT and check is_admin
      const payload = decodeJwt(response.auth_token)
      if (!payload?.is_admin) {
        localStorage.removeItem('sentinel_admin_token')
        localStorage.removeItem('sentinel_admin_refresh')
        throw new Error('Access denied. Admin privileges required.')
      }

      // Fetch full user profile
      await fetchUser()
      sessionToken.value = null
      authStep.value = 'login'
      router.push('/')
    } finally {
      isLoading.value = false
    }
  }

  async function logout(): Promise<void> {
    user.value = null
    sessionToken.value = null
    authStep.value = 'login'
    localStorage.removeItem('sentinel_admin_token')
    localStorage.removeItem('sentinel_admin_refresh')
    router.push('/login')
  }

  async function fetchUser(): Promise<void> {
    const token = localStorage.getItem('sentinel_admin_token')
    if (!token) {
      user.value = null
      return
    }
    try {
      user.value = await authService.getMe(token)
    } catch {
      user.value = null
      localStorage.removeItem('sentinel_admin_token')
      localStorage.removeItem('sentinel_admin_refresh')
    }
  }

  async function hydrate(): Promise<void> {
    const token = localStorage.getItem('sentinel_admin_token')
    if (!token) return

    // Check if token is expired
    if (isTokenExpired(token)) {
      const refreshToken = localStorage.getItem('sentinel_admin_refresh')
      if (refreshToken) {
        try {
          const response = await authService.refresh(refreshToken)
          localStorage.setItem('sentinel_admin_token', response.auth_token)
          localStorage.setItem('sentinel_admin_refresh', response.refresh_token)
        } catch {
          localStorage.removeItem('sentinel_admin_token')
          localStorage.removeItem('sentinel_admin_refresh')
          return
        }
      } else {
        localStorage.removeItem('sentinel_admin_token')
        return
      }
    }

    // Verify is_admin claim
    const currentToken = localStorage.getItem('sentinel_admin_token')
    if (currentToken) {
      const payload = decodeJwt(currentToken)
      if (!payload?.is_admin) {
        localStorage.removeItem('sentinel_admin_token')
        localStorage.removeItem('sentinel_admin_refresh')
        return
      }
    }

    await fetchUser()
  }

  /** Reset to login step (e.g., when user wants to go back from OTP) */
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
