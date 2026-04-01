<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import SideNavbar from './SideNavbar.vue'
import { Menu, X, Sun, Moon, LogOut } from 'lucide-vue-next'

const LOGO_LIGHT = 'https://res.cloudinary.com/dadkir6u2/image/upload/v1767808544/payd_logo_for_light_mode_scwwdc.png'
const LOGO_DARK = 'https://res.cloudinary.com/dadkir6u2/image/upload/v1767808543/payd_logo_for_dark_mode_otv7uv.png'

const authStore = useAuthStore()
const themeStore = useThemeStore()
const mobileMenuOpen = ref(false)

function toggleMobile() {
  mobileMenuOpen.value = !mobileMenuOpen.value
}

function closeMobile() {
  mobileMenuOpen.value = false
}

function handleLogout() {
  authStore.logout()
}
</script>

<template>
  <div class="min-h-screen bg-[var(--color-surface)]">
    <!-- Fixed Header (h-14) -->
    <header class="fixed top-0 left-0 right-0 z-40 h-14 bg-white/80 dark:bg-[#0f1419]/80 backdrop-blur-md border-b border-[var(--color-border)] flex items-center px-4 lg:px-6">
      <!-- Left: hamburger (mobile) + logo + "Sentinel" + "Admin" badge -->
      <button
        class="lg:hidden p-2 -ml-2 rounded-lg text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-tertiary)]"
        @click="toggleMobile"
      >
        <Menu v-if="!mobileMenuOpen" :size="20" />
        <X v-else :size="20" />
      </button>

      <img
        :src="themeStore.isDark ? LOGO_DARK : LOGO_LIGHT"
        alt="Payd"
        class="h-5 w-auto ml-2 lg:ml-0"
      />

      <span class="font-heading font-semibold text-[var(--color-text)] ml-2">
        Sentinel
      </span>

      <span class="hidden sm:inline-flex items-center bg-accent/10 text-accent-dark dark:text-accent-light px-2 py-0.5 rounded-md text-[10px] font-semibold font-heading ml-2">
        Admin
      </span>

      <div class="flex-1" />

      <!-- Right: theme toggle + logout -->
      <button
        class="p-2 rounded-lg text-[var(--color-text-tertiary)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-tertiary)]"
        title="Toggle theme"
        @click="themeStore.toggle()"
      >
        <Moon v-if="!themeStore.isDark" :size="16" />
        <Sun v-else :size="16" />
      </button>
      <button
        class="p-2 rounded-lg text-[var(--color-text-tertiary)] hover:text-red-500 hover:bg-[var(--color-surface-tertiary)] ml-1"
        title="Logout"
        @click="handleLogout"
      >
        <LogOut :size="16" />
      </button>
    </header>

    <!-- Fixed Sidebar (w-56, desktop only) -->
    <aside
      class="fixed top-0 bottom-0 left-0 w-56 pt-14 bg-[var(--color-surface)] border-r border-[var(--color-border)] z-30 transition-transform duration-200 hidden lg:block"
    >
      <SideNavbar @navigate="closeMobile" />
    </aside>

    <!-- Mobile sidebar overlay -->
    <Transition
      enter-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-150"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="mobileMenuOpen"
        class="fixed inset-0 z-50 lg:hidden"
      >
        <!-- Backdrop -->
        <div
          class="absolute inset-0 bg-black/30 dark:bg-black/50 backdrop-blur-sm"
          @click="closeMobile"
        />
        <!-- Sidebar panel -->
        <div class="relative z-50 h-full w-56 pt-14 bg-[var(--color-surface)] border-r border-[var(--color-border)] animate-slide-in-left">
          <SideNavbar @navigate="closeMobile" />
        </div>
      </div>
    </Transition>

    <!-- Main content area -->
    <main class="pt-14 lg:pl-56 min-h-screen">
      <div class="p-4 lg:p-6">
        <div class="max-w-7xl mx-auto">
          <slot />
        </div>
      </div>
    </main>
  </div>
</template>
