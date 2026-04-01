<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import AppLayout from '@/components/layout/AppLayout.vue'

const route = useRoute()
const authStore = useAuthStore()
const themeStore = useThemeStore()

const isRouteLoading = ref(false)

// Initialize theme
themeStore.initialize()

// Hydrate auth on mount
onMounted(async () => {
  await authStore.hydrate()
})

// Route loading bar
watch(
  () => route.path,
  () => {
    isRouteLoading.value = true
    setTimeout(() => {
      isRouteLoading.value = false
    }, 500)
  }
)
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-neutral-950">
    <!-- Route loading bar -->
    <div v-if="isRouteLoading" class="route-loading-bar" />

    <!-- Blank layout (login, 404) -->
    <template v-if="route.meta.layout === 'blank'">
      <router-view />
    </template>

    <!-- Authenticated layout with header + sidebar -->
    <template v-else>
      <AppLayout>
        <router-view />
      </AppLayout>
    </template>
  </div>
</template>
