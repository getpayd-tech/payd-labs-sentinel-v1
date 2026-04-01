<script setup lang="ts">
import { computed, type Component } from 'vue'
import { cn } from '@/utils/formatters'
import { TrendingUp, TrendingDown, Minus } from 'lucide-vue-next'

interface Props {
  label: string
  value: string | number
  icon?: Component
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  class?: string
}

const props = withDefaults(defineProps<Props>(), {
  trend: 'neutral',
})

const trendIcon = computed(() => {
  if (props.trend === 'up') return TrendingUp
  if (props.trend === 'down') return TrendingDown
  return Minus
})

const trendColor = computed(() => {
  if (props.trend === 'up') return 'text-accent'
  if (props.trend === 'down') return 'text-red-500'
  return 'text-gray-400'
})
</script>

<template>
  <div :class="cn('card p-4', props.class)">
    <div class="flex items-center justify-between mb-2">
      <span class="text-xs font-medium text-text-secondary uppercase tracking-wide">
        {{ label }}
      </span>
      <div
        v-if="icon"
        class="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center"
      >
        <component :is="icon" class="w-4 h-4 text-accent" />
      </div>
    </div>
    <div class="flex items-end gap-2">
      <span class="text-2xl font-heading font-bold text-text">
        {{ value }}
      </span>
      <div v-if="trendValue" :class="['flex items-center gap-0.5 text-xs mb-0.5', trendColor]">
        <component :is="trendIcon" class="w-3 h-3" />
        <span>{{ trendValue }}</span>
      </div>
    </div>
  </div>
</template>
