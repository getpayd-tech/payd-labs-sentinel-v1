<script setup lang="ts">
import { ref } from 'vue'
import { Menu, X } from 'lucide-vue-next'
import SideNavbar from './SideNavbar.vue'

const sidebarCollapsed = ref(false)
const mobileMenuOpen = ref(false)

function toggleCollapse() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function toggleMobile() {
  mobileMenuOpen.value = !mobileMenuOpen.value
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-gray-50 dark:bg-neutral-950">
    <!-- Desktop sidebar -->
    <div class="hidden lg:flex">
      <SideNavbar
        :collapsed="sidebarCollapsed"
        @toggle-collapse="toggleCollapse"
      />
    </div>

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
        class="fixed inset-0 z-40 lg:hidden"
      >
        <div class="absolute inset-0 bg-kPrimary/30 dark:bg-black/50 backdrop-blur-sm" @click="toggleMobile" />
        <div class="relative z-50 h-full w-60 animate-slide-in-left">
          <SideNavbar @toggle-collapse="toggleMobile" />
        </div>
      </div>
    </Transition>

    <!-- Main content -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Mobile header -->
      <header class="lg:hidden flex items-center justify-between h-14 px-4 bg-white dark:bg-neutral-950 border-b border-kPrimary/10 dark:border-neutral-800 shrink-0">
        <button
          class="p-2 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors"
          @click="toggleMobile"
        >
          <Menu v-if="!mobileMenuOpen" class="w-5 h-5" />
          <X v-else class="w-5 h-5" />
        </button>
        <span class="font-heading font-semibold text-kPrimary dark:text-white">Sentinel</span>
        <div class="w-9" />
      </header>

      <!-- Scrollable page content -->
      <main class="flex-1 overflow-y-auto custom-scrollbar">
        <div class="page-container">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>
