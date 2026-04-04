<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import {
  LayoutDashboard,
  Container,
  Rocket,
  FolderGit2,
  Database,
  Globe,
  ScrollText,
  Activity,
  ClipboardList,
  BookOpen,
} from 'lucide-vue-next'

const emit = defineEmits<{
  navigate: []
}>()

const route = useRoute()
const router = useRouter()

const navItems = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Services', path: '/services', icon: Container },
  { name: 'Deployments', path: '/deployments', icon: Rocket },
  { name: 'Projects', path: '/projects', icon: FolderGit2 },
  { name: 'Database', path: '/database', icon: Database },
  { name: 'Domains', path: '/domains', icon: Globe },
  { name: 'Logs', path: '/logs', icon: ScrollText },
  { name: 'System', path: '/system', icon: Activity },
  { name: 'Audit', path: '/audit', icon: ClipboardList },
  { name: 'Deploy Guide', path: '/docs', icon: BookOpen },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

function navigate(path: string) {
  router.push(path)
  emit('navigate')
}
</script>

<template>
  <nav class="h-full overflow-y-auto custom-scrollbar">
    <div class="p-3 space-y-0.5 mt-2">
      <button
        v-for="item in navItems"
        :key="item.path"
        :class="[
          'w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-all',
          isActive(item.path)
            ? 'bg-accent/10 text-accent dark:text-accent-light'
            : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-tertiary)]',
        ]"
        @click="navigate(item.path)"
      >
        <component :is="item.icon" class="w-[18px] h-[18px] shrink-0" />
        <span class="truncate">{{ item.name }}</span>
      </button>
    </div>
  </nav>
</template>
