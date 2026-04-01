<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { ContainerInfo } from '@/types'
import { truncate } from '@/utils/formatters'
import Badge from '@/components/ui/Badge.vue'
import { Container } from 'lucide-vue-next'

interface Props {
  container: ContainerInfo
}

const props = defineProps<Props>()
const router = useRouter()

const statusVariant = computed(() => {
  const status = props.container.status
  if (status === 'running') return 'success'
  if (status === 'stopped' || status === 'exited') return 'error'
  if (status === 'restarting') return 'warning'
  if (status === 'paused') return 'info'
  return 'neutral'
})

const statusLabel = computed(() => {
  const health = props.container.health
  if (health === 'unhealthy') return 'unhealthy'
  return props.container.status
})

const statusVariantForHealth = computed(() => {
  if (props.container.health === 'unhealthy') return 'warning'
  return statusVariant.value
})

function navigateToDetail() {
  router.push(`/services/${props.container.name}`)
}
</script>

<template>
  <div
    class="card-hover p-4 cursor-pointer"
    @click="navigateToDetail"
  >
    <div class="flex items-start justify-between gap-3 mb-3">
      <div class="flex items-center gap-2.5 min-w-0">
        <div class="w-9 h-9 rounded-lg bg-surface-tertiary flex items-center justify-center shrink-0">
          <Container class="w-4 h-4 text-text-secondary" />
        </div>
        <div class="min-w-0">
          <h3 class="text-sm font-semibold font-heading text-text truncate">
            {{ container.name }}
          </h3>
          <p class="text-2xs text-gray-400 truncate">
            {{ truncate(container.image, 35) }}
          </p>
        </div>
      </div>
      <Badge :variant="statusVariantForHealth" size="sm">
        {{ statusLabel }}
      </Badge>
    </div>

    <div class="flex items-center gap-3 mt-1">
      <div v-if="container.memory_usage_mb > 0" class="flex items-center gap-1 text-2xs text-gray-400">
        <span>{{ container.memory_usage_mb.toFixed(0) }}MB</span>
      </div>
      <div v-if="container.cpu_percent > 0" class="flex items-center gap-1 text-2xs text-gray-400">
        <span>{{ container.cpu_percent.toFixed(1) }}% CPU</span>
      </div>
    </div>
  </div>
</template>
