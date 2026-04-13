<script setup lang="ts">
import { ref } from 'vue'
import { Menu, Sun, Moon } from 'lucide-vue-next'
import { useDarkMode } from '../../composables/useDarkMode'
import DocsSidebar from './DocsSidebar.vue'

const LOGO_LIGHT = 'https://res.cloudinary.com/dadkir6u2/image/upload/v1767808544/payd_logo_for_light_mode_scwwdc.png'
const LOGO_DARK = 'https://res.cloudinary.com/dadkir6u2/image/upload/v1767808543/payd_logo_for_dark_mode_otv7uv.png'

const { isDark, toggle } = useDarkMode()
const sidebarOpen = ref(false)
</script>

<template>
  <div class="min-h-screen bg-surface">
    <!-- Header -->
    <header class="fixed top-0 left-0 right-0 z-40 h-16 bg-surface/80 backdrop-blur-xl border-b border-border flex items-center px-4 sm:px-6">
      <button
        @click="sidebarOpen = !sidebarOpen"
        class="lg:hidden p-2 -ml-2 rounded-lg text-text-secondary hover:text-text hover:bg-surface-tertiary transition-colors"
      >
        <Menu :size="20" />
      </button>

      <div class="flex items-center gap-2.5 ml-2 lg:ml-0">
        <img :src="isDark ? LOGO_DARK : LOGO_LIGHT" alt="Payd" class="h-7 w-auto" />
        <span class="bg-accent/10 text-accent px-2 py-0.5 rounded-md text-xs font-semibold font-heading">
          Sentinel Docs
        </span>
      </div>

      <div class="flex-1" />

      <button
        @click="toggle"
        class="p-2 rounded-lg text-text-tertiary hover:text-text hover:bg-surface-tertiary transition-colors"
        :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
      >
        <Moon v-if="!isDark" :size="18" />
        <Sun v-else :size="18" />
      </button>

      <a href="https://sentinel.paydlabs.com" class="hidden sm:inline-flex items-center gap-1.5 text-sm font-semibold text-white bg-accent px-3 py-1.5 rounded-lg ml-2 hover:opacity-90 transition-opacity">
        Open Sentinel
      </a>
    </header>

    <!-- Sidebar -->
    <DocsSidebar :open="sidebarOpen" @close="sidebarOpen = false" />

    <!-- Content -->
    <main class="pt-16 lg:pl-[280px]">
      <div class="max-w-5xl px-4 sm:px-6 lg:px-10 py-8 lg:py-10">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>

        <!-- Footer -->
        <footer class="mt-16 pt-6 border-t border-border text-center">
          <p class="text-xs text-text-tertiary">
            Sentinel - Payd Labs Server Management Platform
          </p>
        </footer>
      </div>
    </main>
  </div>
</template>
