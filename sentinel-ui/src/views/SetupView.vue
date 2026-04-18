<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { setupService } from '@/services/setup'
import { useSetupStore } from '@/stores/setup'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import { useToast } from 'vue-toastification'
import { Rocket, CheckCircle2 } from 'lucide-vue-next'

const router = useRouter()
const toast = useToast()
const setupStore = useSetupStore()

const form = reactive({
  sentinel_url: '',
  cors_origins: '',
  caddy_container: 'caddy-proxy',
  proxy_network: 'proxy',
  catchall_upstream: '',
  server_ip: '',
  allowed_usernames: '',
  ghcr_user: '',
})

const submitting = ref(false)
const alreadyComplete = ref(false)

onMounted(async () => {
  const status = await setupStore.fetchStatus()
  if (!status) return
  if (status.setup_complete) {
    alreadyComplete.value = true
    return
  }
  // Pre-fill from current effective config (env defaults)
  form.sentinel_url = status.sentinel_url || window.location.origin
  form.cors_origins = window.location.origin
  form.caddy_container = status.caddy_container || 'caddy-proxy'
  form.proxy_network = status.proxy_network || 'proxy'
  form.catchall_upstream = status.catchall_upstream || ''
  form.server_ip = status.server_ip || ''
  form.allowed_usernames = status.allowed_usernames || ''
  form.ghcr_user = status.ghcr_user || ''
})

async function submit() {
  if (!form.sentinel_url) {
    toast.error('Sentinel URL is required')
    return
  }
  submitting.value = true
  try {
    await setupService.submit({
      sentinel_url: form.sentinel_url,
      cors_origins: form.cors_origins,
      caddy_container: form.caddy_container,
      proxy_network: form.proxy_network,
      catchall_upstream: form.catchall_upstream,
      server_ip: form.server_ip,
      allowed_usernames: form.allowed_usernames,
      ghcr_user: form.ghcr_user,
    })
    setupStore.markComplete()
    toast.success('Setup complete')
    router.push('/')
  } catch (e: any) {
    toast.error(e.response?.data?.detail || 'Setup failed')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-6 bg-gray-50 dark:bg-neutral-950">
    <div class="max-w-2xl w-full">
      <!-- Already complete -->
      <div v-if="alreadyComplete" class="card p-8 text-center">
        <CheckCircle2 class="w-12 h-12 mx-auto mb-4 text-accent" />
        <h1 class="text-xl font-heading font-semibold text-text mb-2">Setup already complete</h1>
        <p class="text-sm text-text-secondary mb-6">
          This Sentinel instance has already been configured. Visit the dashboard to continue.
        </p>
        <Button variant="accent" size="md" @click="router.push('/')">
          Go to Dashboard
        </Button>
      </div>

      <!-- Setup form -->
      <div v-else>
        <div class="text-center mb-6">
          <Rocket class="w-12 h-12 mx-auto mb-3 text-accent" />
          <h1 class="text-2xl font-heading font-bold text-text">Welcome to Sentinel</h1>
          <p class="text-sm text-text-secondary mt-2">
            Quick one-time setup. You can change these later via env vars + restart.
          </p>
        </div>

        <div class="card p-6 space-y-5">
          <div>
            <Input
              v-model="form.sentinel_url"
              label="Sentinel public URL"
              placeholder="https://sentinel.yourteam.com"
            />
            <p class="text-xs text-text-tertiary mt-1">
              Used in generated CI workflows. Include the scheme (http:// or https://).
            </p>
          </div>

          <div>
            <Input
              v-model="form.cors_origins"
              label="CORS origins"
              placeholder="https://sentinel.yourteam.com"
            />
            <p class="text-xs text-text-tertiary mt-1">Comma-separated. Usually just the Sentinel URL.</p>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input v-model="form.caddy_container" label="Caddy container name" placeholder="caddy-proxy" />
            <Input v-model="form.proxy_network" label="Docker network" placeholder="proxy" />
          </div>

          <div>
            <Input
              v-model="form.catchall_upstream"
              label="On-demand TLS catch-all upstream (optional)"
              placeholder="my-service:8000"
            />
            <p class="text-xs text-text-tertiary mt-1">
              Where unregistered custom domains should route. Leave blank for 404s.
            </p>
          </div>

          <div>
            <Input v-model="form.server_ip" label="Server IP (informational)" placeholder="1.2.3.4" />
            <p class="text-xs text-text-tertiary mt-1">
              Shown to users in DNS instructions when they add custom domains.
            </p>
          </div>

          <div>
            <Input
              v-model="form.allowed_usernames"
              label="Allowed usernames"
              placeholder="alice,bob,carol"
            />
            <p class="text-xs text-text-tertiary mt-1">
              Comma-separated Payd Auth usernames. Blank = any admin can log in.
            </p>
          </div>

          <div>
            <Input v-model="form.ghcr_user" label="GHCR org/user" placeholder="getpayd-tech" />
            <p class="text-xs text-text-tertiary mt-1">
              The GitHub org or user whose GHCR images will be pulled during deploys.
            </p>
          </div>

          <div class="flex justify-end pt-2">
            <Button variant="accent" size="md" :loading="submitting" @click="submit">
              Complete Setup
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
