import { defineStore } from 'pinia'
import { ref } from 'vue'
import { setupService } from '@/services/setup'
import type { SetupStatus } from '@/types'

export const useSetupStore = defineStore('setup', () => {
  const isSetupComplete = ref<boolean | null>(null)
  const status = ref<SetupStatus | null>(null)
  const loading = ref(false)

  async function fetchStatus(): Promise<SetupStatus | null> {
    if (loading.value) return status.value
    loading.value = true
    try {
      const s = await setupService.status()
      status.value = s
      isSetupComplete.value = s.setup_complete
      return s
    } catch {
      // If the endpoint is unreachable (e.g. older backend), assume setup is
      // complete so we do not block the UI for an existing deployment.
      isSetupComplete.value = true
      return null
    } finally {
      loading.value = false
    }
  }

  function markComplete() {
    isSetupComplete.value = true
    if (status.value) status.value.setup_complete = true
  }

  return { isSetupComplete, status, loading, fetchStatus, markComplete }
})
