<script setup lang="ts">
import { useRoute } from 'vue-router'
import { ChevronRight, X } from 'lucide-vue-next'

defineProps<{ open: boolean }>()
defineEmits<{ close: [] }>()

const route = useRoute()

const sections = [
  {
    title: 'Getting Started',
    items: [
      { label: 'Overview', to: '/public/docs' },
      { label: 'Deploy Guide', to: '/public/docs/deploy-guide' },
    ],
  },
  {
    title: 'Tools',
    items: [
      { label: 'CLI', to: '/public/docs/cli' },
      { label: 'MCP Server', to: '/public/docs/mcp' },
    ],
  },
  {
    title: 'Features',
    items: [
      { label: 'Custom Domains', to: '/public/docs/custom-domains' },
    ],
  },
  {
    title: 'Reference',
    items: [
      { label: 'API Reference', to: '/public/docs/api' },
    ],
  },
]
</script>

<template>
  <Teleport to="body">
    <transition name="fade">
      <div v-if="open" @click="$emit('close')" class="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm lg:hidden" />
    </transition>
  </Teleport>

  <aside
    class="fixed top-0 lg:top-16 bottom-0 left-0 w-[280px] bg-surface border-r border-border z-50 lg:z-30 transition-transform duration-300 ease-out flex flex-col"
    :class="open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'"
  >
    <div class="flex items-center justify-between px-4 py-3 border-b border-border lg:hidden">
      <div class="flex items-center gap-2">
        <div class="w-6 h-6 bg-accent rounded-md flex items-center justify-center">
          <span class="text-white font-bold text-[10px] font-heading">S</span>
        </div>
        <span class="text-text font-heading font-semibold text-sm">Sentinel</span>
      </div>
      <button @click="$emit('close')" class="p-1.5 rounded-lg text-text-secondary hover:text-text hover:bg-surface-tertiary transition-colors">
        <X :size="18" />
      </button>
    </div>

    <nav class="flex-1 overflow-y-auto px-3 py-4 lg:py-6 space-y-5">
      <div v-for="section in sections" :key="section.title">
        <h4 class="px-3 mb-1 text-[10px] font-heading font-semibold uppercase tracking-widest text-text-tertiary">
          {{ section.title }}
        </h4>
        <ul class="space-y-0.5">
          <li v-for="item in section.items" :key="item.to">
            <router-link
              :to="item.to"
              @click="$emit('close')"
              class="group flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all duration-150"
              :class="route.path === item.to
                ? 'bg-accent/10 text-accent font-semibold'
                : 'text-text-secondary hover:text-text hover:bg-surface-tertiary'"
            >
              <span class="flex-1">{{ item.label }}</span>
              <ChevronRight
                :size="12"
                class="transition-all duration-150"
                :class="route.path === item.to
                  ? 'opacity-100 translate-x-0 text-accent'
                  : 'opacity-0 -translate-x-1 group-hover:opacity-60 group-hover:translate-x-0'"
              />
            </router-link>
          </li>
        </ul>
      </div>
    </nav>

    <div class="border-t border-border px-5 py-3 flex items-center gap-2">
      <span class="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
      <span class="text-[11px] text-text-tertiary">Sentinel v0.1</span>
    </div>
  </aside>
</template>
