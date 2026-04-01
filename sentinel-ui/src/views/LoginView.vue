<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { AlertCircle, ArrowLeft, RefreshCw } from 'lucide-vue-next'

const LOGO_LIGHT = 'https://res.cloudinary.com/dadkir6u2/image/upload/v1767808544/payd_logo_for_light_mode_scwwdc.png'
const LOGO_DARK = 'https://res.cloudinary.com/dadkir6u2/image/upload/v1767808543/payd_logo_for_dark_mode_otv7uv.png'

const authStore = useAuthStore()
const themeStore = useThemeStore()

const username = ref('')
const password = ref('')
const otpDigits = ref<string[]>(['', '', '', '', ''])
const otpInputRefs = ref<HTMLInputElement[]>([])
const error = ref('')
const resendCooldown = ref(0)
let cooldownTimer: ReturnType<typeof setInterval> | null = null

async function handleLogin() {
  error.value = ''
  if (!username.value || !password.value) {
    error.value = 'Please enter both username and password'
    return
  }
  try {
    await authStore.login(username.value, password.value)
    startResendCooldown()
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Invalid credentials. Please try again.'
  }
}

async function handleVerifyOtp() {
  error.value = ''
  const code = otpDigits.value.join('')
  if (code.length !== 5) {
    error.value = 'Please enter the complete 5-digit code'
    return
  }
  try {
    await authStore.verifyOtp(code)
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || 'OTP verification failed. Please try again.'
  }
}

function handleOtpInput(index: number, event: Event) {
  const input = event.target as HTMLInputElement
  const value = input.value.replace(/\D/g, '')

  if (value.length > 1) {
    // Handle paste: distribute digits across inputs
    const digits = value.split('')
    for (let i = 0; i < 5; i++) {
      otpDigits.value[i] = digits[i] || ''
    }
    const lastFilledIndex = Math.min(digits.length - 1, 4)
    nextTick(() => {
      if (lastFilledIndex === 4) {
        otpInputRefs.value[4]?.focus()
        // Auto-submit when all digits are filled
        if (otpDigits.value.every(d => d !== '')) {
          handleVerifyOtp()
        }
      } else {
        otpInputRefs.value[lastFilledIndex + 1]?.focus()
      }
    })
    return
  }

  otpDigits.value[index] = value
  if (value && index < 4) {
    nextTick(() => {
      otpInputRefs.value[index + 1]?.focus()
    })
  }

  // Auto-submit when all digits are filled
  if (value && index === 4 && otpDigits.value.every(d => d !== '')) {
    nextTick(() => handleVerifyOtp())
  }
}

function handleOtpKeydown(index: number, event: KeyboardEvent) {
  if (event.key === 'Backspace' && !otpDigits.value[index] && index > 0) {
    otpDigits.value[index - 1] = ''
    nextTick(() => {
      otpInputRefs.value[index - 1]?.focus()
    })
  }
}

function handleBack() {
  error.value = ''
  otpDigits.value = ['', '', '', '', '']
  authStore.resetToLogin()
}

function startResendCooldown() {
  resendCooldown.value = 60
  if (cooldownTimer) clearInterval(cooldownTimer)
  cooldownTimer = setInterval(() => {
    resendCooldown.value--
    if (resendCooldown.value <= 0 && cooldownTimer) {
      clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

async function handleResendOtp() {
  if (resendCooldown.value > 0) return
  error.value = ''
  try {
    await authStore.resendOtp()
    startResendCooldown()
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to resend OTP.'
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-[var(--color-surface-secondary)] dark:bg-[#0a0f14] p-4">
    <div class="w-full max-w-sm">
      <!-- Header -->
      <div class="text-center mb-8">
        <img
          :src="themeStore.isDark ? LOGO_DARK : LOGO_LIGHT"
          alt="Payd"
          class="h-7 w-auto mx-auto mb-3"
        />
        <div class="flex items-center justify-center gap-2 mb-1">
          <h1 class="text-lg font-heading font-semibold text-[var(--color-text)]">
            Sentinel
          </h1>
          <span class="bg-accent/10 text-accent-dark dark:text-accent-light px-2 py-0.5 rounded-md text-[10px] font-semibold font-heading">
            Admin
          </span>
        </div>
        <p class="text-sm text-[var(--color-text-secondary)]">Infrastructure Management</p>
      </div>

      <!-- Error message -->
      <div
        v-if="error"
        class="mb-4 flex items-center gap-2 px-3 py-2.5 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-xl"
      >
        <AlertCircle class="w-4 h-4 text-red-500 shrink-0" />
        <p class="text-xs text-red-600 dark:text-red-400 font-medium">{{ error }}</p>
      </div>

      <!-- Card -->
      <div class="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] p-6 shadow-[var(--shadow-soft)]">
        <!-- Step 1: Username + Password -->
        <form
          v-if="authStore.authStep === 'login'"
          class="space-y-4"
          @submit.prevent="handleLogin"
        >
          <div>
            <label class="block text-xs font-semibold text-[var(--color-text-secondary)] mb-1.5">Username</label>
            <input
              v-model="username"
              type="text"
              required
              autofocus
              class="w-full px-3 py-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] text-sm
                     focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition"
              placeholder="Enter your username"
            />
          </div>
          <div>
            <label class="block text-xs font-semibold text-[var(--color-text-secondary)] mb-1.5">Password</label>
            <input
              v-model="password"
              type="password"
              required
              class="w-full px-3 py-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] text-sm
                     focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition"
              placeholder="Enter your password"
            />
          </div>
          <button
            type="submit"
            :disabled="authStore.isLoading || !username || !password"
            class="w-full py-2.5 bg-accent text-white font-semibold rounded-lg hover:opacity-90 text-sm transition disabled:opacity-60"
          >
            {{ authStore.isLoading ? 'Signing in...' : 'Sign In' }}
          </button>
          <p class="text-xs text-[var(--color-text-tertiary)] text-center">Admin access only</p>
        </form>

        <!-- Step 2: OTP Verification -->
        <form
          v-else
          class="space-y-6"
          @submit.prevent="handleVerifyOtp"
        >
          <!-- Back button -->
          <button
            type="button"
            class="flex items-center gap-1.5 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors"
            @click="handleBack"
          >
            <ArrowLeft class="w-4 h-4" />
            Back to login
          </button>

          <div class="text-center mb-2">
            <h2 class="text-sm font-heading font-semibold text-[var(--color-text)]">Verify OTP</h2>
            <p class="text-xs text-[var(--color-text-secondary)] mt-1">Enter the code sent to your device</p>
          </div>

          <!-- OTP input boxes -->
          <div class="flex items-center justify-center gap-3">
            <input
              v-for="(_, index) in otpDigits"
              :key="index"
              :ref="(el) => { if (el) otpInputRefs[index] = el as HTMLInputElement }"
              type="text"
              inputmode="numeric"
              maxlength="5"
              :value="otpDigits[index]"
              class="w-12 h-14 text-center text-xl font-heading font-bold rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] transition-all duration-200
                     focus:outline-none focus:ring-1 focus:ring-accent/30 focus:border-accent"
              @input="handleOtpInput(index, $event)"
              @keydown="handleOtpKeydown(index, $event)"
            />
          </div>

          <button
            type="submit"
            :disabled="authStore.isLoading"
            class="w-full py-2.5 bg-accent text-white font-semibold rounded-lg hover:opacity-90 text-sm transition disabled:opacity-60"
          >
            {{ authStore.isLoading ? 'Verifying...' : 'Verify Code' }}
          </button>

          <!-- Resend OTP -->
          <div class="text-center">
            <button
              type="button"
              :disabled="resendCooldown > 0"
              :class="[
                'inline-flex items-center gap-1.5 text-sm transition-colors',
                resendCooldown > 0
                  ? 'text-[var(--color-text-tertiary)] cursor-not-allowed'
                  : 'text-accent hover:text-accent-dark cursor-pointer',
              ]"
              @click="handleResendOtp"
            >
              <RefreshCw class="w-3.5 h-3.5" />
              {{ resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code' }}
            </button>
          </div>
        </form>
      </div>

      <!-- Footer -->
      <p class="mt-6 text-center text-xs text-[var(--color-text-tertiary)]">
        Secured by Payd Labs
      </p>
    </div>
  </div>
</template>
