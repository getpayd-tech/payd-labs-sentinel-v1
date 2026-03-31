import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useRouter } from 'vue-router'
import { authService } from '@/services/auth'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const router = useRouter()
  const user = ref<User | null>(null)
  const isLoading = ref(false)

  const isAuthenticated = computed(() => !!user.value)

  async function login(username: string, password: string): Promise<void> {
    isLoading.value = true
    try {
      const response = await authService.login(username, password)
      localStorage.setItem('access_token', response.access_token)
      localStorage.setItem('refresh_token', response.refresh_token)
      await fetchUser()
      router.push('/')
    } finally {
      isLoading.value = false
    }
  }

  async function logout(): Promise<void> {
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    router.push('/login')
  }

  async function fetchUser(): Promise<void> {
    try {
      user.value = await authService.getMe()
    } catch {
      user.value = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  }

  async function hydrate(): Promise<void> {
    const token = localStorage.getItem('access_token')
    if (token) {
      await fetchUser()
    }
  }

  return {
    user,
    isLoading,
    isAuthenticated,
    login,
    logout,
    fetchUser,
    hydrate,
  }
})
