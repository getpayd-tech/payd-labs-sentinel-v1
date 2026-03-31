<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import { Shield, AlertCircle } from 'lucide-vue-next'

const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')

async function handleLogin() {
  error.value = ''

  if (!username.value || !password.value) {
    error.value = 'Please enter both username and password'
    return
  }

  try {
    await authStore.login(username.value, password.value)
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Invalid credentials. Please try again.'
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-kPrimary dark:bg-neutral-950 relative overflow-hidden">
    <!-- Background pattern -->
    <div class="absolute inset-0 opacity-5">
      <div class="absolute inset-0" style="background-image: radial-gradient(circle at 25px 25px, rgba(255,255,255,0.15) 1px, transparent 0); background-size: 50px 50px;" />
    </div>

    <!-- Gradient accents -->
    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-96 bg-accent/20 rounded-full blur-3xl" />
    <div class="absolute bottom-0 right-0 w-72 h-72 bg-accent/10 rounded-full blur-3xl" />

    <div class="relative z-10 w-full max-w-md mx-4">
      <div class="bg-white dark:bg-neutral-900 rounded-2xl shadow-strong border border-white/10 dark:border-neutral-800 p-8">
        <!-- Header -->
        <div class="text-center mb-8">
          <div class="w-14 h-14 mx-auto mb-4 rounded-xl bg-accent flex items-center justify-center shadow-glow-accent">
            <Shield class="w-7 h-7 text-white" />
          </div>
          <h1 class="text-2xl font-heading font-bold text-kPrimary dark:text-white">
            Sentinel
          </h1>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Payd Labs Infrastructure
          </p>
        </div>

        <!-- Error message -->
        <div
          v-if="error"
          class="mb-4 flex items-center gap-2 px-3 py-2.5 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800"
        >
          <AlertCircle class="w-4 h-4 text-red-500 shrink-0" />
          <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
        </div>

        <!-- Login form -->
        <form class="space-y-4" @submit.prevent="handleLogin">
          <Input
            v-model="username"
            label="Username"
            placeholder="Enter your username"
            type="text"
            size="lg"
          />
          <Input
            v-model="password"
            label="Password"
            placeholder="Enter your password"
            type="password"
            size="lg"
          />
          <Button
            type="submit"
            variant="accent"
            size="lg"
            class="w-full"
            :loading="authStore.isLoading"
          >
            Sign In
          </Button>
        </form>

        <!-- Footer -->
        <p class="mt-6 text-center text-xs text-gray-400 dark:text-gray-500">
          Secured by Payd Labs
        </p>
      </div>
    </div>
  </div>
</template>
